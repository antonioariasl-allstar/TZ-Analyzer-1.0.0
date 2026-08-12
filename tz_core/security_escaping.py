"""
tz_core.security_escaping — Helpers centrales de escape contextual.

Objetivo (AUD-07): ningún dato proveniente de la bitácora o de entradas
manuales del usuario debe interpretarse como HTML/JS/XML activo al insertarse
en el informe HTML, en el JSON embebido en <script>, o en las burbujas
KML/KMZ. El markup que TZ Analyzer construye deliberadamente (<b>, <br>,
<hr>, <table>, etc.) NUNCA pasa por estos helpers: solo los valores
derivados de datos.

Contextos cubiertos:
- esc_html(): texto HTML y atributos HTML (basta un único conjunto de
  entidades - & < > " ' - para ambos contextos cuando el atributo va entre
  comillas dobles, que es como este proyecto siempre los emite).
- esc_kml_value(): mismo contrato que esc_html(), documentado aparte porque
  el sink es distinto (burbuja <description> de KML/KMZ, ver nota abajo).
- safe_json_for_script(): JSON embebido dentro de un bloque <script> del
  informe HTML, a salvo de cierres prematuros de </script> y de U+2028/2029.

Nota sobre KML - por qué un único esc_html() basta y no hace falta CDATA:
simplekml (ver tz_core/kml_generator.py) escapa con html.escape() el
contenido COMPLETO de <name>/<description> salvo que dicho contenido
contenga un bloque `<![CDATA[...]]>` explícito (que este proyecto no usa).
Un visor KML realista que renderiza la burbuja como HTML hace dos pasadas de
decodificación: (1) el parser XML deshace el escape de simplekml al leer el
archivo, y (2) el motor de render HTML del visor interpreta el texto
resultante como marcado. Escapar los valores de datos UNA vez aquí, antes de
insertarlos en el HTML de la burbuja que arma TZ Analyzer, produce el efecto
correcto: tras (1) el dato queda con una capa de escape residual (texto
inerte), mientras que el markup propio de TZ Analyzer (nunca pasado por este
helper) queda crudo tras (1) y se renderiza como HTML real en (2). Escapar
aquí Y ADEMÁS envolver en CDATA sería trabajo redundante (ver sección 6 de
la auditoría: "si simplekml ya escapa un contexto, no duplicar").
"""

from __future__ import annotations

import html
import json
from typing import Any


def esc_html(value: Any) -> str:
    """Escapa un valor para texto HTML o atributo HTML entre comillas dobles.

    None y NaN se normalizan a cadena vacía. Cualquier otro valor se
    convierte a texto y se escapan & < > " ' (html.escape con quote=True).
    Nunca debe aplicarse al markup que TZ Analyzer construye deliberadamente
    (tags, separadores, estilos): solo a los valores derivados de datos.
    """
    if value is None:
        return ""
    try:
        if isinstance(value, float) and value != value:  # NaN
            return ""
    except Exception:
        pass
    return html.escape(str(value), quote=True)


def esc_html_or_none(value: Any):
    """Como esc_html(), pero preserva None para no alterar checks `if x:` aguas abajo."""
    if value is None:
        return None
    return esc_html(value)


# Alias documental: mismo contrato, sink distinto (burbuja KML). Ver docstring
# del módulo para la justificación de por qué basta un único nivel de escape.
esc_kml_value = esc_html


# U+2028 (LINE SEPARATOR) y U+2029 (PARAGRAPH SEPARATOR): válidos dentro de un
# string JSON pero, sin escapar, son terminadores de línea para el parser de
# JavaScript en motores/contextos que no soportan JSON completo como literal
# de programa - se escapan por robustez.
_LINE_SEPARATOR = " "
_PARAGRAPH_SEPARATOR = " "

_JSON_SCRIPT_ESCAPES = {
    ord("&"): "\\u0026",
    ord("<"): "\\u003c",
    ord(">"): "\\u003e",
    ord(_LINE_SEPARATOR): "\\u2028",
    ord(_PARAGRAPH_SEPARATOR): "\\u2029",
}


def safe_json_for_script(obj: Any, **json_kwargs: Any) -> str:
    """Serializa `obj` a JSON seguro para insertar dentro de un <script>.

    Neutraliza '<', '>', '&' (evita que un valor de datos contenga
    literalmente "</script>" y cierre el bloque de forma prematura) y los
    separadores de línea U+2028/U+2029. No cambia la estructura de los
    datos: al parsear con JSON.parse() en el navegador se obtiene el mismo
    objeto que produce json.dumps().
    """
    json_kwargs.setdefault("ensure_ascii", False)
    raw = json.dumps(obj, **json_kwargs)
    return raw.translate(_JSON_SCRIPT_ESCAPES)
