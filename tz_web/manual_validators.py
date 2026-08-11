"""tz_web.manual_validators — validaciones de entrada para el Modo 3 (mapeo
manual de antenas/ubicaciones, sección 4/5/6 del microbloque).

Los límites y rangos replican el contrato real ya usado por
``tz_core.manual_mode`` (wizard CLI) y ``tz_core.kml_generator``
(``generar_kml``/``generar_kml_puntos_libres``), verificado directamente en
esos módulos — no se inventan límites nuevos ni se reduce artificialmente la
precisión del azimut, que ``generar_kml`` admite en punto flotante (a
diferencia del wizard CLI, que solo pide enteros).

Una validación aquí evita descubrir coordenadas inválidas recién al generar
el KMZ (fuera de alcance de este microbloque): cada registro se valida al
agregarlo/editarlo.
"""

from __future__ import annotations

from typing import Optional, Tuple

# Antenas/Celdas — mismo límite que ``antena`` en tz_core.manual_mode.
MAX_NOMBRE_ANTENA = 120
MAX_CELDA = 50
MAX_DIRECCION_ANTENA = 500
MAX_DETALLE_ANTENA = 500

# Puntos libres — mismos límites que ``nombre``/``direccion``/``comentarios``
# en tz_core.manual_mode (nombre 160, no 120: no es el mismo campo que el de
# antena aunque el enunciado general hable de "120" para nombres).
MAX_NOMBRE_PUNTO = 160
MAX_DIRECCION_PUNTO = 500
MAX_DETALLE_PUNTO = 800

LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0
AZIMUT_MIN, AZIMUT_MAX = 0.0, 360.0  # rango [0, 360)


def _to_float(raw: str) -> Optional[float]:
    try:
        return float((raw or "").strip().replace(",", "."))
    except ValueError:
        return None


def parse_nombre(raw: Optional[str], maxlen: int, etiqueta: str) -> Tuple[Optional[str], Optional[str]]:
    valor = (raw or "").strip()
    if not valor:
        return None, f"{etiqueta} es obligatorio."
    if len(valor) > maxlen:
        return None, f"{etiqueta} no puede superar {maxlen} caracteres."
    return valor, None


def parse_texto_opcional(raw: Optional[str], maxlen: int, etiqueta: str) -> Tuple[Optional[str], Optional[str]]:
    valor = (raw or "").strip()
    if not valor:
        return None, None
    if len(valor) > maxlen:
        return None, f"{etiqueta} no puede superar {maxlen} caracteres."
    return valor, None


def parse_lat_lon(
    lat_raw: Optional[str], lon_raw: Optional[str], permitir_cero_cero: bool
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Valida latitud/longitud obligatorias.

    ``permitir_cero_cero`` distingue el contrato real de cada generador:
    ``generar_kml`` (antenas) descarta (0, 0) explícitamente;
    ``generar_kml_puntos_libres`` no lo hace (solo valida el rango), así que
    esa coordenada es válida para puntos libres.
    """
    lat = _to_float(lat_raw)
    if lat_raw is None or not str(lat_raw).strip():
        return None, None, "La latitud es obligatoria."
    if lat is None:
        return None, None, "La latitud debe ser un número válido."
    if not (LAT_MIN <= lat <= LAT_MAX):
        return None, None, f"La latitud debe estar entre {LAT_MIN:g} y {LAT_MAX:g}."

    lon = _to_float(lon_raw)
    if lon_raw is None or not str(lon_raw).strip():
        return None, None, "La longitud es obligatoria."
    if lon is None:
        return None, None, "La longitud debe ser un número válido."
    if not (LON_MIN <= lon <= LON_MAX):
        return None, None, f"La longitud debe estar entre {LON_MIN:g} y {LON_MAX:g}."

    if not permitir_cero_cero and abs(lat) < 1e-9 and abs(lon) < 1e-9:
        return None, None, "La coordenada (0, 0) no es una ubicación válida."

    return lat, lon, None


def parse_azimut(raw: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """Azimut opcional; conserva decimales (p. ej. 22.5) tal como los admite
    ``generar_kml``. Rango [0, 360), coherente con ``_coerce_azimut`` en
    ``tz_core.validation_utils``."""
    valor = (raw or "").strip()
    if not valor:
        return None, None
    numero = _to_float(valor)
    if numero is None:
        return None, "El azimut debe ser un número válido."
    if not (AZIMUT_MIN <= numero < AZIMUT_MAX):
        return None, "El azimut debe estar entre 0 y 360 (sin incluir 360)."
    return numero, None
