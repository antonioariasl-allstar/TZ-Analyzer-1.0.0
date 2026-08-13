"""FASE 1 WEB — prueba E2E de ``tz_web.services.process_case()``.

Ejecuta el servicio de punta a punta con el fixture real de
``tests/data/bitacora_test.tsv.xlsx`` (el mismo dataset que usa el golden
E2E del motor) y demuestra el flujo completo pedido en el encargo:

    archivo + hoja + mapeo + opciones + carpeta de salida
                             -> HTML + KMZ + hashes + logs

sin consola, sin Tkinter, sin monkeypatching de ``run_tz_analysis()`` ni de
``main()``. Los canarios sobre ``builtins.input``, ``safe_input`` y Tkinter
fallan con ``pytest.fail()`` si algo los invoca — no dependen únicamente de
``assert_not_called()`` (ver justificación en los tests FASE 0 WEB
existentes: un mock no parcheado en su punto de uso real "no es llamado"
trivialmente aunque el símbolo real sí se use).
"""
from __future__ import annotations

import builtins
import hashlib
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tz_web.services import CaseRequest, CaseResult, ProgressUpdate, process_case

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "bitacora_test.tsv.xlsx"
)
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config.json",
)

_MAPEO_COMPLETO = {
    "fecha": ("col", "fecha_inicial"),
    "hora": ("col", "hora_inicial"),
    "lat": ("col", "latitud_inicial"),
    "long": ("col", "longitud_inicial"),
    "azimut": ("col", "azimut_inicial"),
    "antena": ("col", "ubicacion_inicio"),
    "celda": ("col", "cod_celda_inicial"),
    "imei": ("col", "imei_origen"),
    "tel": ("col", "numero_origen"),
    "contacto": ("col", "numero_destino"),
    "interaccion": ("col", "tipo_llamada"),
    "duracion": ("col", "duracion_seg"),
}


def _config_hash() -> str:
    with open(CONFIG_PATH, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _canary_input(*_args, **_kwargs):
    pytest.fail("process_case() invocó builtins.input() — debe ser 100% no interactivo")


def _canary_safe_input(*_args, **_kwargs):
    pytest.fail("process_case() invocó tz_core.ingestion_pipeline.safe_input()")


def _canary_tkinter_tk(*_args, **_kwargs):
    pytest.fail("process_case() intentó abrir Tkinter (Tk())")


@pytest.fixture
def output_dir(tmp_path):
    return str(tmp_path / "salida")


@pytest.fixture
def base_request(output_dir):
    return CaseRequest(
        ruta_archivo=DATA_PATH,
        carpeta_salida=output_dir,
        mapeo=dict(_MAPEO_COMPLETO),
        duration_unit_decision="segundos",
    )


def _run_with_canaries(monkeypatch, request: CaseRequest) -> CaseResult:
    monkeypatch.setattr(builtins, "input", _canary_input)
    monkeypatch.setattr("tz_core.ingestion_pipeline.safe_input", _canary_safe_input)
    monkeypatch.setattr("tkinter.Tk", _canary_tkinter_tk, raising=False)
    return process_case(request)


def test_process_case_completo_sin_interaccion_genera_productos_reales(monkeypatch, base_request):
    """Caso feliz de punta a punta: HTML, KMZ y hashes generados y verificados
    físicamente, con ningún punto de entrada interactivo invocado."""

    result = _run_with_canaries(monkeypatch, base_request)

    assert result.success is True
    assert result.errors == []

    assert result.html_path and os.path.isfile(result.html_path)
    assert result.kmz_path and os.path.isfile(result.kmz_path)
    assert result.hashes_path and os.path.isfile(result.hashes_path)
    assert result.log_path and os.path.isfile(result.log_path)

    assert result.output_dir and os.path.isdir(result.output_dir)
    assert os.path.dirname(result.html_path) == result.output_dir
    assert os.path.dirname(result.kmz_path) == result.output_dir

    with open(result.html_path, "r", encoding="utf-8", errors="ignore") as fh:
        html_contenido = fh.read()
    assert "<html" in html_contenido.lower()

    with open(result.hashes_path, "r", encoding="utf-8") as fh:
        hashes_contenido = fh.read()
    assert "SHA256" in hashes_contenido

    assert result.summary["filas_totales"] == 50
    assert result.summary["capacidades_procesable"] is True


def test_process_case_nombre_de_salida_sin_sufijo_tecnico(monkeypatch, output_dir):
    """Corrección UX de nombre de carpeta: el nombre visible final es
    exactamente el candidato saneado (caso/alias/fecha/hora), sin ningún
    sufijo técnico añadido (ver eliminación de ``_generate_unique_case_name``
    en ``tz_web.services`` — la unicidad la resuelve por completo
    ``OutputTransaction.reserve``, que sigue intacto)."""

    request = CaseRequest(
        ruta_archivo=DATA_PATH,
        carpeta_salida=output_dir,
        mapeo=dict(_MAPEO_COMPLETO),
        duration_unit_decision="segundos",
        output_base_name="TEL_61758498_chepe_20260812_0641",
    )
    resultado = _run_with_canaries(monkeypatch, request)

    assert resultado.success is True
    assert os.path.basename(resultado.output_dir) == "TEL_61758498_chepe_20260812_0641"


def test_process_case_segunda_ejecucion_mismo_nombre_no_sobrescribe(monkeypatch, output_dir):
    """Una segunda ejecución con el mismo nombre explícito no pisa la
    primera: OutputTransaction.reserve aplica el sufijo incremental
    (contrato MB3 ya existente, sin overwrite) sobre el nombre visible
    limpio."""

    def _make_request() -> CaseRequest:
        return CaseRequest(
            ruta_archivo=DATA_PATH,
            carpeta_salida=output_dir,
            mapeo=dict(_MAPEO_COMPLETO),
            duration_unit_decision="segundos",
            output_base_name="TEL_61758498_chepe_20260812_0641",
        )

    resultado1 = _run_with_canaries(monkeypatch, _make_request())
    resultado2 = _run_with_canaries(monkeypatch, _make_request())
    resultado3 = _run_with_canaries(monkeypatch, _make_request())

    assert resultado1.success and resultado2.success and resultado3.success
    assert os.path.basename(resultado1.output_dir) == "TEL_61758498_chepe_20260812_0641"
    assert os.path.basename(resultado2.output_dir) == "TEL_61758498_chepe_20260812_0641_02"
    assert os.path.basename(resultado3.output_dir) == "TEL_61758498_chepe_20260812_0641_03"
    assert os.path.isdir(resultado1.output_dir)
    assert os.path.isdir(resultado2.output_dir)
    assert os.path.isdir(resultado3.output_dir)
    # Ninguna ejecución posterior pisó los productos de la anterior.
    assert set(os.listdir(resultado1.output_dir)).isdisjoint(os.listdir(resultado2.output_dir))


def test_process_case_nombre_con_espacios_y_acentos_queda_saneado_y_sin_sufijo(monkeypatch, output_dir):
    """Un nombre de caso con espacios/acentos se limpia (misma sanitización
    existente, ``sanear_nombre_archivo``) y tampoco lleva sufijo técnico."""

    request = CaseRequest(
        ruta_archivo=DATA_PATH,
        carpeta_salida=output_dir,
        mapeo=dict(_MAPEO_COMPLETO),
        duration_unit_decision="segundos",
        output_base_name="Caso José Peña 2026",
    )
    resultado = _run_with_canaries(monkeypatch, request)

    assert resultado.success is True
    nombre = os.path.basename(resultado.output_dir)
    assert nombre == "Caso_Jose_Pena_2026"
    assert " " not in nombre


def test_process_case_ningun_systemexit_escapa(monkeypatch, base_request):
    """Ninguna ruta de process_case() debe dejar escapar SystemExit hacia el
    llamador (a diferencia de main(), que históricamente usaba sys.exit(0))."""

    try:
        result = _run_with_canaries(monkeypatch, base_request)
    except SystemExit:
        pytest.fail("SystemExit escapó de process_case()")

    assert result.success is True


def test_process_case_progreso_emitido_en_orden(monkeypatch, base_request):
    """El callback on_progress recibe las 8 transiciones reales, en orden,
    con secuencia 1..8 sin huecos."""

    eventos: list[ProgressUpdate] = []
    base_request.on_progress = eventos.append

    _run_with_canaries(monkeypatch, base_request)

    stages = [e.stage for e in eventos]
    assert stages == [
        "validando_entrada",
        "cargando_archivo",
        "aplicando_mapeo",
        "normalizando_y_qc",
        "aplicando_filtros",
        "generando_productos",
        "verificando_resultados",
        "finalizado",
    ]
    assert [e.sequence for e in eventos] == list(range(1, 9))


def test_process_case_funciona_sin_callback_de_progreso(monkeypatch, base_request):
    """on_progress=None (default) no debe requerirse ni fallar."""

    assert base_request.on_progress is None
    result = _run_with_canaries(monkeypatch, base_request)
    assert result.success is True


def test_process_case_no_muta_config_json_en_disco(monkeypatch, base_request):
    """config.json no debe modificarse en disco por ejecutar process_case()."""

    hash_antes = _config_hash()
    _run_with_canaries(monkeypatch, base_request)
    hash_despues = _config_hash()

    assert hash_antes == hash_despues


def test_process_case_dos_ejecuciones_consecutivas_no_mezclan_logs(monkeypatch, output_dir, base_request):
    """Dos llamadas consecutivas deben completarse correctamente y cada una
    debe devolver únicamente sus propios logs (sin arrastrar los de la corrida
    anterior ni compartir estado global)."""

    req1 = base_request
    resultado1 = _run_with_canaries(monkeypatch, req1)
    assert resultado1.success is True

    req2 = CaseRequest(
        ruta_archivo=DATA_PATH,
        carpeta_salida=output_dir,
        mapeo=dict(_MAPEO_COMPLETO),
        duration_unit_decision="segundos",
    )
    resultado2 = _run_with_canaries(monkeypatch, req2)
    assert resultado2.success is True

    assert resultado1.logs is not resultado2.logs
    assert resultado1.logs != []
    assert resultado2.logs != []
    # Cada corrida arranca su logger desde una lista vacía propia: si los
    # logs se compartieran entre ejecuciones, la segunda corrida acumularía
    # más de un marcador "finalizado" (uno de la primera + uno propio).
    assert resultado1.logs[0].startswith("[validando_entrada]")
    assert resultado2.logs[0].startswith("[validando_entrada]")
    assert sum(1 for l in resultado1.logs if "[finalizado]" in l) == 1
    assert sum(1 for l in resultado2.logs if "[finalizado]" in l) == 1


def test_process_case_dos_ejecuciones_mismo_minuto_sin_nombre_no_colisionan(
    monkeypatch, output_dir
):
    """Corrección precommit — unicidad de carpeta de salida.

    Dos ``process_case()`` consecutivos, sin ``output_base_name``, con el
    reloj congelado al mismo instante (peor caso: mismo minuto Y mismo
    microsegundo) deben producir carpetas de salida distintas y cada uno sus
    propios productos, sin mezclarlos ni sobrescribirlos. El reloj se congela
    parcheando ``tz_web.services.datetime`` (no ``tz_core``): la unicidad se
    resuelve enteramente en la capa web, sin tocar ``suggest_case_name`` ni
    ``prompt_case_identity``.
    """

    instante_congelado = datetime(2026, 8, 6, 17, 30, 0, 123456)
    reloj_congelado = MagicMock(wraps=datetime)
    reloj_congelado.now.return_value = instante_congelado

    def _make_request() -> CaseRequest:
        return CaseRequest(
            ruta_archivo=DATA_PATH,
            carpeta_salida=output_dir,
            mapeo=dict(_MAPEO_COMPLETO),
            duration_unit_decision="segundos",
        )

    with patch("tz_web.services.datetime", reloj_congelado):
        resultado1 = _run_with_canaries(monkeypatch, _make_request())
        resultado2 = _run_with_canaries(monkeypatch, _make_request())

    assert resultado1.success is True
    assert resultado2.success is True

    # Carpetas de salida distintas pese al reloj idéntico.
    assert resultado1.output_dir != resultado2.output_dir
    assert resultado1.output_dir is not None and resultado2.output_dir is not None

    # Ninguna corrida pisó/mezcló los productos de la otra: cada carpeta de
    # salida contiene únicamente los archivos de su propia ejecución.
    assert os.path.isdir(resultado1.output_dir)
    assert os.path.isdir(resultado2.output_dir)
    archivos1 = set(os.listdir(resultado1.output_dir))
    archivos2 = set(os.listdir(resultado2.output_dir))
    assert archivos1, "La primera ejecución no dejó productos en su carpeta"
    assert archivos2, "La segunda ejecución no dejó productos en su carpeta"
    assert archivos1.isdisjoint(archivos2)

    # Productos de cada ejecución físicamente dentro de su propia carpeta.
    for resultado in (resultado1, resultado2):
        assert os.path.dirname(resultado.html_path) == resultado.output_dir
        assert os.path.dirname(resultado.kmz_path) == resultado.output_dir
        assert os.path.dirname(resultado.hashes_path) == resultado.output_dir
        assert os.path.isfile(resultado.html_path)
        assert os.path.isfile(resultado.kmz_path)
        assert os.path.isfile(resultado.hashes_path)

    # La segunda carpeta debe llevar el sufijo incremental de la red de
    # seguridad (_02), evidencia de que se detectó y resolvió la colisión
    # del sufijo de alta resolución (idéntico por el reloj congelado).
    assert os.path.basename(resultado2.output_dir).endswith("_02")
