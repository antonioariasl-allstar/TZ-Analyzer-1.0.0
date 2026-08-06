"""
Modelo puro de capacidades analíticas disponibles en un DataFrame de bitácora.

``detectar_capacidades`` inspecciona un DataFrame ya cargado (post-ingesta,
con encabezados normalizados a nombres canónicos por el wizard/pipeline
existente) y determina qué secciones/análisis del informe pueden producirse
con los datos presentes, sin bloquear ni modificar el flujo actual.

Aplica a bitácoras/DataFrames. El modo manual (``manual_mode.py``) sigue una
ruta independiente que no se detecta a partir de un DataFrame — este módulo
no lo cubre.

Reglas de pureza:
- función pura, determinista para la misma entrada;
- no ``input()``, no ``print()``, no ``sys.exit()``;
- no modifica ``df`` ni usa ``df.attrs``;
- no depende de la CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

import pandas as pd

from tz_core.bitacora_normalization import (
    DuracionEstado,
    clasificar_confiabilidad_duracion,
    coalesce_cols,
    es_valor_significativo,
    parse_date_series,
    validate_latlon,
)


@dataclass(frozen=True)
class Capacidad:
    """Estado de una capacidad analítica individual.

    ``disponible`` es True tanto para "disponible" como para "parcial"
    (el análisis puede producir algo, aunque degradado); es False para
    "no_disponible" y "bloqueada". ``estado`` distingue las cuatro
    situaciones con precisión.
    """

    disponible: bool
    estado: str  # "disponible" | "parcial" | "no_disponible" | "bloqueada"
    faltantes: Tuple[str, ...]
    motivo: str


@dataclass(frozen=True)
class CapabilitiesReport:
    """Resultado inmutable de ``detectar_capacidades``."""

    procesable: bool
    bloqueos_globales: Tuple[str, ...]
    capacidades: Mapping[str, "Capacidad"]

    def capacidad(self, nombre: str) -> Capacidad:
        return self.capacidades[nombre]


_NOMBRES_CAPACIDADES: Tuple[str, ...] = (
    "identificacion",
    "cronologia",
    "filtros_temporales",
    "antenas",
    "antenas_por_horario",
    "kml",
    "heatmap",
    "contactos",
    "tipo_evento",
    "duracion",
    "orientacion",
    "metadatos",
    "hashes",
)


# ─────────────────────────────────────────────────────────────────────────
# Helpers de lectura (solo lectura, sin efectos secundarios)
# ─────────────────────────────────────────────────────────────────────────

def _columna_tiene_valor_significativo(df: pd.DataFrame, columna: str) -> bool:
    if columna not in df.columns:
        return False
    serie = df[columna]
    if serie.empty:
        return False
    return bool(serie.map(es_valor_significativo).any())


def _bool_col_any_true(df: pd.DataFrame, columna: str) -> bool:
    if columna not in df.columns:
        return False
    serie = df[columna]
    if serie.empty:
        return False
    try:
        return bool(serie.fillna(False).astype(bool).any())
    except (TypeError, ValueError):
        return bool(serie.map(lambda v: bool(v) if v is not None else False).any())


def _fecha_valida_presente(df: pd.DataFrame) -> bool:
    if "fecha" not in df.columns or df["fecha"].empty:
        return False
    try:
        parsed = parse_date_series(df["fecha"])
        return bool(parsed.notna().any())
    except Exception:
        return False


def _hora_valida_presente(df: pd.DataFrame) -> bool:
    return _columna_tiene_valor_significativo(df, "hora")


def _datetime_evento_usable(df: pd.DataFrame) -> bool:
    if "datetime_evento" not in df.columns:
        return False
    serie = df["datetime_evento"]
    if serie.empty:
        return False
    try:
        if pd.api.types.is_datetime64_any_dtype(serie):
            return bool(serie.notna().any())
        parsed = pd.to_datetime(serie, errors="coerce")
        return bool(parsed.notna().any())
    except Exception:
        return False


def _azimut_utilizable(df: pd.DataFrame) -> bool:
    if "azimut" not in df.columns or df["azimut"].empty:
        return False
    try:
        serie = pd.to_numeric(df["azimut"], errors="coerce")
        return bool(serie.notna().any())
    except Exception:
        return False


def _coordenadas_estado(df: pd.DataFrame) -> Tuple[bool, bool]:
    """Devuelve (columnas_presentes, valores_validos_por_fila)."""
    lon_col = coalesce_cols(df, "long", "lon")
    columnas_presentes = "lat" in df.columns and lon_col is not None
    if not columnas_presentes:
        return False, False
    return True, validate_latlon(df, lon_cols=("long", "lon"))


def _extraer_columnas_config(config: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    if not config:
        return None
    try:
        columnas = config.get("columnas")
    except AttributeError:
        return None
    if isinstance(columnas, dict):
        return columnas
    return None


def _capacidad_bloqueada(razon: str) -> Capacidad:
    return Capacidad(disponible=False, estado="bloqueada", faltantes=(), motivo=f"bloqueo_global:{razon}")


# Columnas diagnósticas/derivadas que agregan normalize_contact_fields,
# normalize_event_fields y normalize_temporal_fields (bitacora_normalization.py)
# aguas arriba, antes de que detectar_capacidades reciba el DataFrame. Son
# etiquetas técnicas sobre los datos de origen (p.ej. "sin_columna_contacto",
# "DESCONOCIDO", False) — no datos analíticos en sí. Si se cuentan en el
# barrido de "algún valor significativo", un archivo real vacío/con solo
# placeholders deja de detectarse como sin_datos_procesables una vez
# enriquecido, porque el propio diagnóstico ya "tiene texto". Estas mismas
# columnas ya se referencian por nombre en los detectores de más abajo
# (_detectar_contactos, _detectar_tipo_evento) — aquí solo se excluyen del
# barrido de bloqueo global, no se usan para nada más.
_COLUMNAS_DIAGNOSTICO_DERIVADAS: frozenset[str] = frozenset({
    "tel_limpio",
    "contacto_limpio",
    "contacto_valido",
    "contacto_categoria",
    "contacto_motivo",
    "tipo_evento_normalizado",
    "evento_valido_analisis",
    "datetime_evento",
    "antena_analitica",
    "sitio_inferido",
    "sitio_inferencia_motivo",
    "sitio_lat_normalizada",
    "sitio_long_normalizada",
})


def _detectar_bloqueo_global(df: Any) -> Optional[str]:
    """Bloqueantes globales: DataFrame inválido/vacío o sin ningún dato procesable.

    No detecta "archivo ilegible" — eso ocurre antes de que exista un
    DataFrame y corresponde a una capa anterior (carga/ingesta). El barrido
    de "algún valor significativo" ignora las columnas diagnósticas
    derivadas (ver ``_COLUMNAS_DIAGNOSTICO_DERIVADAS``): deben evaluarse los
    datos de origen, no las etiquetas que la normalización agrega sobre
    ellos.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        return "dataframe_invalido"
    if df.shape[0] == 0 or df.shape[1] == 0:
        return "dataframe_vacio"
    columnas_fuente = [c for c in df.columns if c not in _COLUMNAS_DIAGNOSTICO_DERIVADAS]
    df_fuente = df[columnas_fuente] if columnas_fuente else df.iloc[:, 0:0]
    if df_fuente.shape[1] == 0 or not bool(df_fuente.map(es_valor_significativo).any().any()):
        return "sin_datos_procesables"
    return None


# ─────────────────────────────────────────────────────────────────────────
# Detectores por capacidad
# ─────────────────────────────────────────────────────────────────────────

def _detectar_identificacion(df: pd.DataFrame) -> Capacidad:
    tel_ok = _columna_tiene_valor_significativo(df, "tel")
    imei_ok = _columna_tiene_valor_significativo(df, "imei")
    if tel_ok or imei_ok:
        presentes = "+".join(n for n, ok in (("tel", tel_ok), ("imei", imei_ok)) if ok)
        return Capacidad(True, "disponible", (), f"identificador_presente:{presentes}")
    return Capacidad(False, "no_disponible", ("tel", "imei"), "sin_tel_ni_imei_con_valor_significativo")


def _detectar_cronologia(df: pd.DataFrame) -> Capacidad:
    fecha_ok = _fecha_valida_presente(df)
    if not fecha_ok:
        return Capacidad(False, "no_disponible", ("fecha",), "sin_fecha_parseable")
    if _hora_valida_presente(df):
        return Capacidad(True, "disponible", (), "fecha_y_hora_disponibles")
    return Capacidad(True, "parcial", ("hora",), "fecha_disponible_sin_hora_detalle_horario_limitado")


def _detectar_filtros_temporales(df: pd.DataFrame) -> Capacidad:
    fecha_ok = _fecha_valida_presente(df)
    if not fecha_ok:
        return Capacidad(False, "no_disponible", ("fecha",), "sin_fecha_parseable")
    if _hora_valida_presente(df):
        return Capacidad(True, "disponible", (), "filtros_por_dia_y_hora_disponibles")
    return Capacidad(True, "parcial", ("hora",), "solo_filtros_por_dia_subtipos_horarios_no_disponibles")


def _detectar_antenas(df: pd.DataFrame) -> Capacidad:
    """A. Antena original con valor significativo: disponible (nomenclatura oficial).

    B. Sin antena original pero con ``antena_analitica`` inferida por
    coordenadas (HITO 2A — ver ``tz_core.site_inference``): disponible,
    pero en estado "parcial" — el identificador de sitio no es la
    nomenclatura oficial del operador, solo agrupa por coordenadas.

    C. Ninguna de las dos: no disponible. ``antena_analitica`` solo se
    inspecciona si ya existe en ``df`` (el enriquecimiento es responsabilidad
    de ``run_ingestion_pipeline``, no de este detector).
    """
    if _columna_tiene_valor_significativo(df, "antena"):
        return Capacidad(True, "disponible", (), "antena_original_presente")
    if _columna_tiene_valor_significativo(df, "antena_analitica"):
        return Capacidad(
            True, "parcial", ("antena",), "sitios_inferidos_por_coordenadas"
        )
    return Capacidad(False, "no_disponible", ("antena",), "sin_antena_con_valor_significativo")


def _detectar_antenas_por_horario(df: pd.DataFrame) -> Capacidad:
    antena_ok = _columna_tiene_valor_significativo(df, "antena")
    antena_analitica_ok = _columna_tiene_valor_significativo(df, "antena_analitica")
    hora_ok = _hora_valida_presente(df)
    dt_ok = _datetime_evento_usable(df)

    if antena_ok:
        if hora_ok or dt_ok:
            motivo = "antena_y_hora_disponibles" if hora_ok else "antena_y_datetime_evento_disponibles"
            return Capacidad(True, "disponible", (), motivo)
        return Capacidad(False, "no_disponible", ("hora",), "antena_presente_sin_hora_ni_datetime_evento")

    if antena_analitica_ok:
        if hora_ok or dt_ok:
            return Capacidad(
                True, "parcial", ("antena",), "sitios_inferidos_por_coordenadas_con_hora"
            )
        return Capacidad(False, "no_disponible", ("hora",), "sitio_inferido_sin_hora_ni_datetime_evento")

    faltantes = ("antena",) if (hora_ok or dt_ok) else ("antena", "hora")
    return Capacidad(False, "no_disponible", faltantes, "sin_antena")


def _detectar_kml(df: pd.DataFrame) -> Capacidad:
    columnas_presentes, validas = _coordenadas_estado(df)
    if not columnas_presentes:
        return Capacidad(False, "no_disponible", ("lat", "long"), "sin_columnas_lat_long")
    if not validas:
        return Capacidad(False, "no_disponible", ("lat_long_validos",), "coordenadas_presentes_pero_invalidas")
    return Capacidad(True, "disponible", (), "coordenadas_validas_por_fila")


def _detectar_heatmap(df: pd.DataFrame) -> Capacidad:
    columnas_presentes, validas = _coordenadas_estado(df)
    if not columnas_presentes:
        return Capacidad(False, "no_disponible", ("lat", "long"), "sin_columnas_lat_long")
    if not validas:
        return Capacidad(False, "no_disponible", ("lat_long_validos",), "coordenadas_presentes_pero_invalidas")
    return Capacidad(True, "disponible", (), "coordenadas_validas_por_fila")


def _detectar_contactos(df: pd.DataFrame) -> Capacidad:
    if "contacto_valido" in df.columns:
        ok = _bool_col_any_true(df, "contacto_valido")
        motivo_ok = "contacto_valido_derivado_presente"
    elif "contacto" in df.columns:
        ok = _columna_tiene_valor_significativo(df, "contacto")
        motivo_ok = "contacto_con_valor_significativo"
    else:
        ok = False
        motivo_ok = ""
    if ok:
        return Capacidad(True, "disponible", (), motivo_ok)
    return Capacidad(False, "no_disponible", ("contacto",), "sin_contacto_valido")


def _detectar_tipo_evento(df: pd.DataFrame) -> Capacidad:
    if "evento_valido_analisis" in df.columns:
        ok = _bool_col_any_true(df, "evento_valido_analisis")
        motivo_ok = "evento_valido_analisis_derivado_presente"
    elif "tipo_evento_normalizado" in df.columns:
        serie = df["tipo_evento_normalizado"].astype(str).str.upper()
        ok = bool((serie != "DESCONOCIDO").any())
        motivo_ok = "tipo_evento_normalizado_derivado_presente"
    elif "interaccion" in df.columns:
        ok = _columna_tiene_valor_significativo(df, "interaccion")
        motivo_ok = "interaccion_con_valor_significativo"
    else:
        ok = False
        motivo_ok = ""
    if ok:
        return Capacidad(True, "disponible", (), motivo_ok)
    return Capacidad(False, "no_disponible", ("interaccion",), "sin_interaccion_significativa")


def _detectar_duracion(
    df: pd.DataFrame,
    *,
    duracion_estado: Optional[DuracionEstado],
    config: Optional[Mapping[str, Any]],
) -> Capacidad:
    estado = duracion_estado or clasificar_confiabilidad_duracion(
        df, columnas_config=_extraer_columnas_config(config)
    )
    columna = estado.columna or "duracion"
    if estado.estado == "segura":
        return Capacidad(True, "disponible", (), f"duracion_segura:{estado.unidad}:{estado.motivo}")
    if estado.estado == "ambigua":
        return Capacidad(False, "no_disponible", (columna,), f"unidad_no_confirmada:{estado.motivo}")
    return Capacidad(False, "no_disponible", (columna,), f"duracion_ausente:{estado.motivo}")


def _detectar_orientacion(df: pd.DataFrame) -> Capacidad:
    if not _azimut_utilizable(df):
        return Capacidad(False, "no_disponible", ("azimut",), "sin_azimut_utilizable")
    if not _columna_tiene_valor_significativo(df, "antena"):
        return Capacidad(True, "parcial", ("antena",), "azimut_disponible_sin_antena_asociada")
    return Capacidad(True, "disponible", (), "antena_y_azimut_disponibles")


def _detectar_metadatos(df: pd.DataFrame) -> Capacidad:
    campos_enriquecimiento = ("tel", "imei", "imsi", "alias", "nombre_usuario", "abonado")
    presentes = tuple(c for c in campos_enriquecimiento if _columna_tiene_valor_significativo(df, c))
    faltantes = tuple(c for c in campos_enriquecimiento if c not in presentes)
    motivo = "metadatos_enriquecidos" if presentes else "metadatos_minimos_sin_enriquecimiento"
    return Capacidad(True, "disponible", faltantes, motivo)


def _detectar_hashes(_df: pd.DataFrame) -> Capacidad:
    return Capacidad(True, "disponible", (), "no_depende_de_campos_analiticos")


# ─────────────────────────────────────────────────────────────────────────
# Punto de entrada
# ─────────────────────────────────────────────────────────────────────────

def detectar_capacidades(
    df: pd.DataFrame,
    *,
    duracion_estado: Optional[DuracionEstado] = None,
    config: Optional[Mapping[str, Any]] = None,
) -> CapabilitiesReport:
    """Determina qué capacidades analíticas puede producir ``df``.

    Función pura: no modifica ``df``, no imprime, no pregunta, no sale del
    proceso. El resultado es determinista para la misma entrada.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame de bitácora ya cargado, con encabezados en nombres
        canónicos (el mapeo/normalización de encabezados es responsabilidad
        de capas anteriores — este detector no busca sinónimos).
    duracion_estado : DuracionEstado | None
        Si ya fue calculado (p.ej. por QC), se reutiliza en lugar de
        recalcularlo vía ``clasificar_confiabilidad_duracion``.
    config : Mapping | None
        Config opcional; solo se usa (si trae una llave ``"columnas"`` con
        un mapeo) para localizar la columna de duración configurada. No es
        obligatorio y no requiere cambios en config.json.
    """
    razon_bloqueo = _detectar_bloqueo_global(df)
    if razon_bloqueo is not None:
        capacidades = {nombre: _capacidad_bloqueada(razon_bloqueo) for nombre in _NOMBRES_CAPACIDADES}
        return CapabilitiesReport(procesable=False, bloqueos_globales=(razon_bloqueo,), capacidades=capacidades)

    capacidades = {
        "identificacion": _detectar_identificacion(df),
        "cronologia": _detectar_cronologia(df),
        "filtros_temporales": _detectar_filtros_temporales(df),
        "antenas": _detectar_antenas(df),
        "antenas_por_horario": _detectar_antenas_por_horario(df),
        "kml": _detectar_kml(df),
        "heatmap": _detectar_heatmap(df),
        "contactos": _detectar_contactos(df),
        "tipo_evento": _detectar_tipo_evento(df),
        "duracion": _detectar_duracion(df, duracion_estado=duracion_estado, config=config),
        "orientacion": _detectar_orientacion(df),
        "metadatos": _detectar_metadatos(df),
        "hashes": _detectar_hashes(df),
    }
    return CapabilitiesReport(procesable=True, bloqueos_globales=(), capacidades=capacidades)


__all__ = [
    "Capacidad",
    "CapabilitiesReport",
    "detectar_capacidades",
]
