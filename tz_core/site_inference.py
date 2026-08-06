"""
TZ-Analyzer — Inferencia de identidad analítica de sitio (Hito 1).

Cuando una bitácora trae coordenadas válidas pero no un nombre/código de
antena utilizable, este módulo construye un identificador técnico estable
a partir de las coordenadas normalizadas, para poder agrupar activaciones
del mismo punto geográfico aunque la fuente no reporte el nombre del sitio.

El identificador inferido representa una agrupación técnica por coordenadas
normalizadas y no corresponde necesariamente a la nomenclatura oficial del
operador. No es una antena real, ni una BTS confirmada, ni una torre
identificada: es un rótulo derivado únicamente de latitud/longitud.

Alcance de este hito (deliberadamente NO incluido):
- clustering por distancia o tolerancia de 10-20 metros;
- geocodificación o búsqueda de nombres reales;
- numeración secuencial tipo SITIO_001;
- uso de azimut/celda dentro del identificador.

Funciones puras: no reciben ni producen efectos secundarios, no mutan
DataFrames de entrada, no leen globals ni hacen I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

import pandas as pd

from tz_core.bitacora_normalization import (
    coalesce_cols,
    es_valor_significativo,
    sanitize_latlon,
    validate_latlon,
)

MOTIVO_ANTENA_ORIGINAL = "antena_original"
MOTIVO_SITIO_INFERIDO = "sitio_inferido_por_coordenadas"
MOTIVO_SIN_DATOS = "sin_antena_ni_coordenadas_validas"


@dataclass(frozen=True)
class SiteResolution:
    """Resultado de resolver la identidad analítica de sitio de una fila."""

    valor: Optional[str]
    inferido: bool
    latitud_normalizada: Optional[str]
    longitud_normalizada: Optional[str]
    motivo: str


def normalizar_coordenada_sitio(valor: object, decimales: int = 6) -> Optional[str]:
    """Normaliza una coordenada a string de punto fijo con ``decimales`` posiciones.

    Acepta int, float, str o Decimal. Devuelve None si ``valor`` no puede
    interpretarse como número finito (None, NaN, texto no numérico, infinito).
    Los valores que redondean a cero se formatean sin signo, para evitar el
    caso "-0.000000".
    """
    if valor is None:
        return None
    try:
        if isinstance(valor, float) and pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    try:
        d = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return None

    if not d.is_finite():
        return None

    quantizador = Decimal(1).scaleb(-decimales)
    try:
        redondeado = d.quantize(quantizador, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None

    if redondeado == 0:
        redondeado = abs(redondeado)

    return format(redondeado, "f")


def construir_identificador_sitio(
    latitud: object,
    longitud: object,
    *,
    decimales: int = 6,
) -> Optional[str]:
    """Construye ``SITIO_<lat>_<long>`` a partir de coordenadas normalizadas.

    Devuelve None si alguna de las dos coordenadas no puede normalizarse.
    """
    lat_norm = normalizar_coordenada_sitio(latitud, decimales)
    lon_norm = normalizar_coordenada_sitio(longitud, decimales)
    if lat_norm is None or lon_norm is None:
        return None
    return f"SITIO_{lat_norm}_{lon_norm}"


def _coordenadas_validas(latitud: object, longitud: object, *, bbox: Optional[dict] = None) -> bool:
    """Reutiliza ``validate_latlon`` (bitacora_normalization) sobre una fila
    única, para aplicar el mismo criterio de validez (bbox de El Salvador,
    par 0,0 inválido) que ya usa el resto del pipeline, sin reimplementar
    la lógica de rango aquí.
    """
    fila = pd.DataFrame({"lat": [latitud], "long": [longitud]})
    return validate_latlon(fila, lat_col="lat", lon_cols=("long",), bbox=bbox)


def resolver_sitio_analitico(
    antena: object,
    latitud: object,
    longitud: object,
    *,
    decimales: int = 6,
    bbox: Optional[dict] = None,
) -> SiteResolution:
    """Resuelve la identidad analítica de sitio para una fila (o valores sueltos).

    Prioridad: antena real reportada > sitio inferido por coordenadas > nulo.
    Nunca sobrescribe la antena original: solo la reporta tal cual llegó.
    """
    if es_valor_significativo(antena):
        return SiteResolution(
            valor=str(antena).strip(),
            inferido=False,
            latitud_normalizada=None,
            longitud_normalizada=None,
            motivo=MOTIVO_ANTENA_ORIGINAL,
        )

    if _coordenadas_validas(latitud, longitud, bbox=bbox):
        lat_norm = normalizar_coordenada_sitio(latitud, decimales)
        lon_norm = normalizar_coordenada_sitio(longitud, decimales)
        identificador = construir_identificador_sitio(latitud, longitud, decimales=decimales)
        if identificador is not None:
            return SiteResolution(
                valor=identificador,
                inferido=True,
                latitud_normalizada=lat_norm,
                longitud_normalizada=lon_norm,
                motivo=MOTIVO_SITIO_INFERIDO,
            )

    return SiteResolution(
        valor=None,
        inferido=False,
        latitud_normalizada=None,
        longitud_normalizada=None,
        motivo=MOTIVO_SIN_DATOS,
    )


def agregar_sitio_analitico(
    df: pd.DataFrame,
    *,
    col_antena: Optional[str] = None,
    col_lat: Optional[str] = None,
    col_long: Optional[str] = None,
    decimales: int = 6,
    bbox: Optional[dict] = None,
) -> pd.DataFrame:
    """Devuelve una copia de ``df`` enriquecida con la identidad analítica de sitio.

    Columnas agregadas:
      - antena_analitica: antena real si es significativa, si no el
        identificador SITIO_<lat>_<long> inferido, si no NA.
      - sitio_inferido: True cuando antena_analitica proviene de coordenadas.
      - sitio_inferencia_motivo: uno de MOTIVO_ANTENA_ORIGINAL,
        MOTIVO_SITIO_INFERIDO, MOTIVO_SIN_DATOS.
      - sitio_lat_normalizada / sitio_long_normalizada: coordenadas
        normalizadas a ``decimales`` posiciones, solo cuando el sitio fue
        inferido (NA en cualquier otro caso).

    No muta ``df``; la columna de antena original nunca se sobrescribe.
    """
    out = df.copy()

    antena_col = col_antena if col_antena else coalesce_cols(df, "antena")
    lat_col = col_lat if col_lat else coalesce_cols(df, "lat", "latitud")
    lon_col = col_long if col_long else coalesce_cols(df, "long", "lon", "longitud")

    if antena_col and antena_col in df.columns:
        antena_ok = df[antena_col].map(es_valor_significativo)
    else:
        antena_ok = pd.Series(False, index=df.index)

    if lat_col and lon_col and lat_col in df.columns and lon_col in df.columns:
        saneado = sanitize_latlon(df, lat_col=lat_col, lon_col=lon_col, bbox=bbox)
        lat_saneada = saneado[lat_col]
        lon_saneada = saneado[lon_col]
        coords_ok = lat_saneada.notna() & lon_saneada.notna()
    else:
        lat_saneada = pd.Series(float("nan"), index=df.index, dtype="float64")
        lon_saneada = pd.Series(float("nan"), index=df.index, dtype="float64")
        coords_ok = pd.Series(False, index=df.index)

    antena_analitica = pd.Series(pd.NA, index=df.index, dtype="object")
    sitio_inferido = pd.Series(False, index=df.index)
    motivo = pd.Series(MOTIVO_SIN_DATOS, index=df.index, dtype="object")
    lat_normalizada = pd.Series(pd.NA, index=df.index, dtype="object")
    lon_normalizada = pd.Series(pd.NA, index=df.index, dtype="object")

    if antena_ok.any():
        antena_analitica.loc[antena_ok] = df.loc[antena_ok, antena_col].astype(str).str.strip()
        motivo.loc[antena_ok] = MOTIVO_ANTENA_ORIGINAL

    infer_mask = (~antena_ok) & coords_ok
    if infer_mask.any():
        lat_norm = lat_saneada.loc[infer_mask].map(lambda v: normalizar_coordenada_sitio(v, decimales))
        lon_norm = lon_saneada.loc[infer_mask].map(lambda v: normalizar_coordenada_sitio(v, decimales))
        identificadores = lat_norm.combine(lon_norm, lambda la, lo: f"SITIO_{la}_{lo}" if la is not None and lo is not None else None)

        exitosos = identificadores.notna()
        idx_exitosos = identificadores[exitosos].index

        antena_analitica.loc[idx_exitosos] = identificadores.loc[idx_exitosos]
        sitio_inferido.loc[idx_exitosos] = True
        motivo.loc[idx_exitosos] = MOTIVO_SITIO_INFERIDO
        lat_normalizada.loc[idx_exitosos] = lat_norm.loc[idx_exitosos]
        lon_normalizada.loc[idx_exitosos] = lon_norm.loc[idx_exitosos]

    out["antena_analitica"] = antena_analitica
    out["sitio_inferido"] = sitio_inferido
    out["sitio_inferencia_motivo"] = motivo
    out["sitio_lat_normalizada"] = lat_normalizada
    out["sitio_long_normalizada"] = lon_normalizada
    return out


__all__ = [
    "SiteResolution",
    "MOTIVO_ANTENA_ORIGINAL",
    "MOTIVO_SITIO_INFERIDO",
    "MOTIVO_SIN_DATOS",
    "normalizar_coordenada_sitio",
    "construir_identificador_sitio",
    "resolver_sitio_analitico",
    "agregar_sitio_analitico",
]
