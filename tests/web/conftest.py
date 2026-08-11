"""Fixtures compartidos para las pruebas de tz_web (Fase 2 Web)."""
from __future__ import annotations

import io
import os

import pytest

from tz_web import state as tz_web_state
from tz_web.app import create_app

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "bitacora_test.tsv.xlsx"
)
SHEET_NAME = "CASO_860766049463800_PROCESADA"

# Mapeo completo válido para el fixture real, usando los nombres de columna
# EXACTOS que produce cargar_excel_con_normalizacion para esta hoja (en
# mayúsculas) — los mismos que vería un usuario real en el selector de la
# pantalla de mapeo.
REAL_MAPPING_FORM = {
    "tipo_fecha": "col", "col_fecha": "FECHA_INICIAL",
    "tipo_hora": "col", "col_hora": "HORA_INICIAL",
    "tipo_lat": "col", "col_lat": "LATITUD_INICIAL",
    "tipo_long": "col", "col_long": "LONGITUD_INICIAL",
    "tipo_azimut": "col", "col_azimut": "AZIMUT_INICIAL",
    "tipo_antena": "col", "col_antena": "UBICACION_INICIO",
    "tipo_celda": "col", "col_celda": "COD_CELDA_INICIAL",
    "tipo_imei": "col", "col_imei": "IMEI_ORIGEN",
    "tipo_tel": "col", "col_tel": "NUMERO_ORIGEN",
    "tipo_contacto": "col", "col_contacto": "NUMERO_DESTINO",
    "tipo_interaccion": "col", "col_interaccion": "TIPO_LLAMADA",
    "tipo_duracion": "col", "col_duracion": "DURACION_SEG",
}


@pytest.fixture()
def app(tmp_path, monkeypatch):
    # Aísla cada prueba en su propia carpeta de subidas/logs temporales,
    # fuera del repositorio y sin interferir entre pruebas.
    monkeypatch.setattr(tz_web_state, "UPLOAD_ROOT", str(tmp_path / "uploads"))
    application = create_app()
    application.config.update(TESTING=True)
    yield application
    # Ninguna sesión de una prueba debe filtrarse a la siguiente.
    with tz_web_state._SESSIONS_LOCK:
        tz_web_state._SESSIONS.clear()
    with tz_web_state._RUNNING_LOCK:
        tz_web_state._RUNNING_SESSION_ID = None


@pytest.fixture()
def client(app):
    return app.test_client()


def upload_file_from_path(client, path: str, filename: str):
    # La selección de modo es la única entrada que crea un caso. Los tests
    # que ya eligieron Modo 2 conservan ese modo; solo se inicia Modo 1 cuando
    # el cliente aún no tiene una sesión válida.
    with client.session_transaction() as browser_session:
        case = tz_web_state.get_session(browser_session.get("case_id"))
    if case is None:
        client.post("/modo/1")
    with open(path, "rb") as fh:
        payload = fh.read()
    data = {"archivo": (io.BytesIO(payload), filename)}
    return client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)


def upload_real_file(client, filename: str = "bitacora_test.tsv.xlsx"):
    return upload_file_from_path(client, DATA_PATH, filename)


# ---------------------------------------------------------------------------
# Fixture de regresión — encabezados "humanos" (no normalizados: mayúsculas
# con espacios, guiones y acentos), construido a partir de los mismos datos
# del fixture real de arriba renombrando columnas. Reproduce el defecto
# corregido en tz_web.services.process_case(): antes de la corrección,
# process_case() recargaba el archivo con gather_dataset_metadata(), que
# renombra encabezados a minúsculas_con_guion_bajo (colapsando espacios/
# guiones/puntos), rompiendo la correspondencia con los nombres de columna
# que la UI mostró y que quedaron guardados en el mapeo (p. ej.
# "NUMERO DE ORIGEN" ya no existía como tal en ese DataFrame).
# ---------------------------------------------------------------------------

HUMAN_SHEET_NAME = "Hoja1"

# Encabezado real del archivo (tal como lo produce el fixture original,
# limpio de espacios sobrantes) -> encabezado "humano" no normalizado que
# usará este fixture de regresión.
HUMAN_HEADER_RENAMES = {
    "FECHA_INICIAL": "FECHA INICIAL",
    "HORA_INICIAL": "HORA INICIAL",
    "NUMERO_ORIGEN": "NUMERO DE ORIGEN",
    "IMEI_ORIGEN": "IMEI-ORIGEN",
    "NUMERO_DESTINO": "NÚMERO DESTINO",
    "LATITUD_INICIAL": "LATITUD INICIAL",
    "LONGITUD_INICIAL": "LONGITUD INICIAL",
    "AZIMUT_INICIAL": "AZIMUT INICIAL",
    "UBICACION_INICIO": "UBICACION INICIO",
    "COD_CELDA_INICIAL": "COD CELDA INICIAL",
    "TIPO_LLAMADA": "TIPO LLAMADA",
    "DURACION_SEG": "DURACION SEG",
}

# Mapeo de formulario equivalente a REAL_MAPPING_FORM, pero apuntando a los
# encabezados humanos (no normalizados) de HUMAN_HEADER_RENAMES — es
# exactamente lo que un usuario real vería y elegiría en el selector de la
# pantalla de mapeo para este archivo.
HUMAN_MAPPING_FORM = {
    "tipo_fecha": "col", "col_fecha": "FECHA INICIAL",
    "tipo_hora": "col", "col_hora": "HORA INICIAL",
    "tipo_lat": "col", "col_lat": "LATITUD INICIAL",
    "tipo_long": "col", "col_long": "LONGITUD INICIAL",
    "tipo_azimut": "col", "col_azimut": "AZIMUT INICIAL",
    "tipo_antena": "col", "col_antena": "UBICACION INICIO",
    "tipo_celda": "col", "col_celda": "COD CELDA INICIAL",
    "tipo_imei": "col", "col_imei": "IMEI-ORIGEN",
    "tipo_tel": "col", "col_tel": "NUMERO DE ORIGEN",
    "tipo_contacto": "col", "col_contacto": "NÚMERO DESTINO",
    "tipo_interaccion": "col", "col_interaccion": "TIPO LLAMADA",
    "tipo_duracion": "col", "col_duracion": "DURACION SEG",
}


def build_human_headers_xlsx(dest_path: str) -> None:
    """Genera, a partir del fixture real existente, un .xlsx con los mismos
    datos pero encabezados 'humanos' (mayúsculas, espacios, un guion y un
    acento) — ver HUMAN_HEADER_RENAMES. No sustituye el fixture original."""
    import pandas as pd

    df = pd.read_excel(DATA_PATH, sheet_name=SHEET_NAME)
    df = df.rename(columns=HUMAN_HEADER_RENAMES)
    df.to_excel(dest_path, sheet_name=HUMAN_SHEET_NAME, index=False)


@pytest.fixture()
def human_headers_file(tmp_path):
    """Ruta a un .xlsx temporal con encabezados humanos (no normalizados),
    generado por prueba (no versionado en tests/data)."""
    dest = tmp_path / "bitacora_encabezados_humanos.xlsx"
    build_human_headers_xlsx(str(dest))
    return str(dest)


def advance_to_configure(client):
    """Sube el fixture real, elige hoja, mapea y confirma — deja la sesión
    lista justo antes de la pantalla de configuración."""
    upload_real_file(client)
    client.post("/sheet", data={"hoja": SHEET_NAME}, follow_redirects=True)
    client.post("/mapping", data=dict(REAL_MAPPING_FORM), follow_redirects=True)
    return client.post("/mapping/confirm", follow_redirects=True)


def wait_for_terminal_status(client, timeout: float = 30.0):
    import time

    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get("/status")
        last = resp.get_json()
        if last["status"] in ("success", "partial", "failed"):
            return last
        time.sleep(0.2)
    raise AssertionError(f"El análisis no terminó a tiempo; último estado: {last}")
