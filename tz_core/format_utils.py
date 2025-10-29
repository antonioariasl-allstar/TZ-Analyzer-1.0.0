"""
tz_core.format_utils - UTILIDADES DE FORMATEO DE VALORES
========================================================

✅ ESTADO: MIGRACIÓN DESDE MONOLITO - FUNCIONES DE FORMATEO
🎯 PROPÓSITO: Formateo específico de valores para diferentes contextos (KML, HTML, etc.)
📍 DIFERENCIACIÓN: Formateo especializado sin dependencias de UI o I/O

RESPONSABILIDADES ESPECÍFICAS:
- _formatear_valor_para_burbuja(): Formateo específico para burbujas KML/HTML
- armar_descripcion_compacta(): Construcción de descripciones HTML para KML (NUEVA - 29-oct-2025)
- Reglas por tipo de columna: lat/long (decimales), azimut/lac (enteros), etc.
- Manejo de casos especiales: IMEI (sin notación científica), duración (HH:MM:SS)

DEPENDENCIAS:
- re: Expresiones regulares para validación y formateo
- tz_core.validation_utils: Para función _a_float()

MIGRADO DESDE: script_principal_bitacoras_refactory.py líneas 1311-1375, 933-1100  
FECHA MIGRACIÓN: 27 octubre 2025 (formateo), 29 octubre 2025 (descripción compacta)
"""

import re
from decimal import Decimal
from typing import Any, Optional

# Import de validation_utils para _a_float
try:
    from .validation_utils import _a_float
except ImportError:
    # Fallback si validation_utils no está disponible
    def _a_float(val) -> Optional[float]:
        """Fallback básico para convertir a float"""
        try:
            return float(val)
        except (ValueError, TypeError):
            return None


def _formatear_valor_para_burbuja(col: str, val: Any) -> str:
    """
    Formatear valores según reglas específicas para burbujas KML/HTML.
    
    Reglas por tipo de columna:
    - lat/long: 6 decimales de precisión
    - azimut/lac: enteros (sin .0) si son numéricos; texto si no
    - celda: entero si es numérica; texto si es alfanumérica (ej: "C102")
    - imei: limpieza de .0 y notación científica
    - duracion: conversión segundos -> HH:MM:SS; preserva formato existente
    - demás: string tal cual
    
    Args:
        col: Nombre de la columna (usado para determinar reglas)
        val: Valor a formatear
        
    Returns:
        str: Valor formateado según las reglas específicas
        
    Examples:
        >>> _formatear_valor_para_burbuja("lat", 13.123456789)
        '13.123457'
        >>> _formatear_valor_para_burbuja("azimut", 45.0)
        '45'
        >>> _formatear_valor_para_burbuja("celda", "C102")
        'C102'
        >>> _formatear_valor_para_burbuja("duracion", 3661)
        '01:01:01'
    """
    col = (col or "").strip().lower()
    s = str(val).strip()

    # lat/long -> 6 decimales
    if col in {"lat", "long"}:
        f = _a_float(val)
        return None if f is None else f"{f:.6f}"

    # azimut / lac -> enteros si son numéricos; si no, se deja el texto
    if col in {"azimut", "lac"}:
        f = _a_float(val)
        return s if f is None else str(int(round(f)))

    # celda -> entero si es numérico; si no, se deja el texto (p.ej., "C102")
    if col == "celda":
        f = _a_float(val)
        return s if f is None else str(int(round(f)))

    # imei -> cadena limpia sin .0 ni notación científica
    if col == "imei":
        s_clean = str(val).strip()
        try:
            # caso 123456789012345.0 -> 123456789012345
            m = re.fullmatch(r'(\d+)\.0+', s_clean)
            if m:
                return m.group(1)
            # caso notación científica: 3.579E14 -> 357900000000000
            if re.fullmatch(r'\d+(?:\.\d+)?[eE][+-]?\d+', s_clean):
                d = Decimal(s_clean)
                s_clean = format(d, 'f').rstrip('0').rstrip('.')
                return s_clean
            # si ya son solo dígitos, devolver tal cual
            if re.fullmatch(r'\d+', s_clean):
                return s_clean
        except Exception:
            # ante cualquier cosa rara, devuelve lo que venga
            return s_clean
        return s_clean

    # duracion -> si es numérica (segundos) => HH:MM:SS; si ya trae "HH:MM[:SS]" se deja
    if col == "duracion":
        if ":" in s:
            return s
        f = _a_float(val)
        if f is None:
            return s
        f = int(round(f))
        h = f // 3600
        m = (f % 3600) // 60
        sec = f % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    # default: como string
    return s


# Backwards compatibility alias
formatear_valor_para_burbuja = _formatear_valor_para_burbuja


def armar_descripcion_compacta(campos: dict, count_azimut=None, suprimir_direccion_si_igual=True, 
                              config=None, hr_compact='<div style="border-top:1px solid #bbb; margin:1px 0; height:0;"></div>') -> str:
    """
    Construye descripción HTML compacta para burbujas KML.
    
    MIGRADA DESDE: script_principal_bitacoras_refactory.py líneas 933-1100
    
    Args:
        campos: Diccionario con datos del registro (antena, fecha, hora, etc.)
        count_azimut: Contador de activaciones para ese azimut (opcional)
        suprimir_direccion_si_igual: Si True, oculta línea "Direccion" cuando es idéntica a "Antena" (normalizado)
        config: Diccionario de configuración (opcional, para etiquetas personalizadas)
        hr_compact: Separador HTML horizontal
        
    Returns:
        String HTML formateado para <description> del Placemark
    """
    import unicodedata
    import re
    
    # Import de validation_utils
    try:
        from .validation_utils import tiene_valor
    except ImportError:
        def tiene_valor(v):
            return v is not None and str(v).strip() not in ("", "nan", "None", "—")
    
    P = []
    
    # Función helper para formatear campos
    def fmt(col):
        v = campos.get(col, None)
        if not tiene_valor(v):
            return None
        return _formatear_valor_para_burbuja(col, v)

    # Fila 1: Fecha · Hora
    f = fmt("fecha"); h = fmt("hora")
    if f or h:
        l1 = []
        if f: l1.append(f"<b>Fecha:</b> {f}")
        if h: l1.append(f"<b>Hora:</b> {h}")
        P.append(" &middot; ".join(l1))
        P.append(hr_compact)

    # Fila 2 + 3a + 3b: Número/IMEI + Alias/Usuario + Abonado
    grupo_identidad_tuvo_datos = False

    # Fila 2: Número, IMEI
    tel = campos.get("tel", None)
    imei_fmt = fmt("imei")
    l2 = []
    if tiene_valor(tel):
        l2.append(f"<b>Número:</b> {str(tel).strip()}")
    if imei_fmt:
        l2.append(f"registrado en <b>IMEI:</b> {imei_fmt}")
    if l2:
        P.append(", ".join(l2))
        grupo_identidad_tuvo_datos = True

    # Fila 3a: Alias · Usuario
    alias = campos.get("alias", None)
    nombre_usuario = campos.get("usuario", None)
    l3a = []
    if tiene_valor(alias):
        l3a.append(f"<b>Alias:</b> {str(alias).strip()}")
    if tiene_valor(nombre_usuario):
        l3a.append(f"<b>Usuario:</b> {str(nombre_usuario).strip()}")
    if l3a:
        P.append(" &middot; ".join(l3a))
        grupo_identidad_tuvo_datos = True

    # Fila 3b: Abonado
    abon = campos.get("abonado", None)
    if tiene_valor(abon):
        P.append(f"<b>Abonado:</b> {str(abon).strip()}")
        grupo_identidad_tuvo_datos = True

    # Separador del grupo identidad
    if grupo_identidad_tuvo_datos:
        P.append(hr_compact)

    # Fila 4: Antena + Ubicación + Radio
    ant_full = campos.get("antena_completa", None)
    ant_titulo = campos.get("antena", None)
    ant_line = ant_full if tiene_valor(ant_full) else ant_titulo

    lat = fmt("lat"); lon = fmt("long")
    az = fmt("azimut")
    # Fallback para azimut
    if not az and campos.get("azimut_i") is not None:
        try:
            az = str(int(campos["azimut_i"]))
        except Exception:
            az = str(campos["azimut_i"])
    celda = fmt("celda"); lac = fmt("lac")

    l4 = []
    if tiene_valor(ant_line):
        l4.append(f"<b>Antena:</b> {str(ant_line).strip()}")
    if lat: l4.append(f"<b>Lat:</b> {lat}")
    if lon: l4.append(f"<b>Long:</b> {lon}")
    if az:
        az_txt = f"<b>Azimut:</b> {az}°"
        if count_azimut is not None:
            try:
                nveces = int(count_azimut)
            except Exception:
                nveces = count_azimut
            az_txt += f" (<b>{nveces} veces</b>)"
        l4.append(az_txt)      
    if celda: l4.append(f"<b>Celda:</b> {celda}")
    if lac: l4.append(f"<b>LAC:</b> {lac}")
    
    seccion_ubicacion_tuvo_datos = False
    if l4:
        P.append(", ".join(l4))
        seccion_ubicacion_tuvo_datos = True

    # Dirección (opcional)
    direccion = fmt("direccion")
    # Etiqueta configurable
    try:
        _label_dir = config.get("kml", {}).get("labels", {}).get("direccion", "Direccion") if config else "Direccion"
    except Exception:
        _label_dir = "Direccion"

    # Normalizador para comparar direccion vs antena
    def _norm_text(s):
        if s is None:
            return ""
        try:
            s = str(s)
            s = unicodedata.normalize("NFKD", s)
            s = "".join(ch for ch in s if not unicodedata.combining(ch))
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s
        except Exception:
            return str(s).strip().lower()

    if direccion is not None:
        mostrar_dir = True
        if suprimir_direccion_si_igual:
            # Omitir si direccion es igual a antena
            if _norm_text(direccion) and _norm_text(ant_line) and _norm_text(direccion) == _norm_text(ant_line):
                mostrar_dir = False
        if mostrar_dir:
            P.append(f"<b>{_label_dir}:</b> {direccion}")
            seccion_ubicacion_tuvo_datos = True

    # Separador tras ubicación
    if seccion_ubicacion_tuvo_datos:
        P.append(hr_compact)

    # Fila 5: Interacción — contacto · Duración
    inter = fmt("interaccion")
    telc = fmt("tel_contacto")
    dur = fmt("duracion")
    l5 = []

    if inter is not None:
        t = f"<b>Interacción:</b> {inter}"
        # Solo agregar tel_contacto si NO es "—"
        if (telc is not None) and (str(telc).strip() != "—"):
            t += f" — {str(telc).strip()}"
        l5.append(t)

    if dur:
        l5.append(f"<b>Duración:</b> {dur}")

    if l5:
        P.append(" &middot; ".join(l5))

    return "<br>".join(P)


# Alias para compatibilidad
_armar_descripcion_compacta = armar_descripcion_compacta