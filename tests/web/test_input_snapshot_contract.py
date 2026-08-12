"""MB3: contrato web de entrada aceptada y snapshot por ejecucion."""
from __future__ import annotations

import hashlib
import io
import os

from tests.web.conftest import DATA_PATH, upload_real_file
from tz_web import routes, state
from tz_web.services import CaseResult


def _current_case(client):
    with client.session_transaction() as browser_session:
        return state.get_session(browser_session["case_id"])


class _DeferredThread:
    target = None

    def __init__(self, *, target, daemon):
        self.__class__.target = target
        self.daemon = daemon

    def start(self):
        return None


def test_B_reemplazo_no_cambia_los_bytes_del_worker_activo(client, tmp_path, monkeypatch):
    with open(DATA_PATH, "rb") as original_fixture:
        original_digest = hashlib.sha256(original_fixture.read()).hexdigest()
    upload_real_file(client)
    case = _current_case(client)
    case.carpeta_salida = str(tmp_path / "salida")
    case.mapping = {"fecha": ("col", "FECHA_INICIAL")}

    with open(case.temp_path, "rb") as accepted:
        accepted_bytes = accepted.read()

    captured = {}

    def _process(request_obj):
        captured["path"] = request_obj.ruta_archivo
        with open(request_obj.ruta_archivo, "rb") as snapshot:
            captured["bytes"] = snapshot.read()
        return CaseResult(success=True, output_dir=str(tmp_path / "resultado"))

    monkeypatch.setattr(routes.threading, "Thread", _DeferredThread)
    monkeypatch.setattr(routes, "process_case", _process)

    assert routes._start_task(case) == (True, None)
    snapshot_path = case.input_snapshot_path
    assert snapshot_path != case.temp_path
    assert os.path.isfile(snapshot_path)
    assert case.input_snapshot_sha256 == case.upload_sha256

    # Una nueva subida HTTP queda bloqueada por MB2 mientras la reserva esta
    # activa y no sustituye ni el staging aceptado ni el snapshot del worker.
    response = client.post(
        "/upload",
        data={"archivo": (io.BytesIO(b"reemplazo"), "otro.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert state.MSG_ANALYSIS_IN_PROGRESS.encode("utf-8") in response.data

    # Incluso una alteracion externa de la ruta mutable ya no afecta a la
    # solicitud capturada: el worker consume exclusivamente su copia UUID.
    with open(case.temp_path, "wb") as mutable_upload:
        mutable_upload.write(b"bytes mutados fuera del flujo web")

    _DeferredThread.target()

    assert captured["path"] == snapshot_path
    assert captured["bytes"] == accepted_bytes
    assert case.status == state.STATUS_SUCCESS
    assert state.is_any_run_active() is False
    with open(DATA_PATH, "rb") as original_fixture:
        assert hashlib.sha256(original_fixture.read()).hexdigest() == original_digest
