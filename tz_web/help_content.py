"""tz_web.help_content — datos estáticos para /help (Manual de Usuario).

Separado de ``tz_web.routes`` para no mezclar contenido de documentación
(texto largo, aprobado editorialmente) con lógica de rutas. No importa nada
de ``tz_web.state`` ni depende de una sesión: el manual (MICROBLOQUE 6-2) es
completamente independiente del caso en curso — ver la sección de seguridad
del encargo, AYUDA es documentación estática/local.
"""

from __future__ import annotations

from typing import Tuple

# Única fuente de verdad para el índice/barra lateral del manual: id de
# ancla + título visible, en el orden en que deben aparecer. El contenido de
# cada sección vive en help.html; este módulo solo fija el orden y los
# rótulos que también reutiliza la barra lateral, para que ambos no puedan
# desincronizarse.
HELP_SECTIONS: Tuple[Tuple[str, str], ...] = (
    ("acerca", "Acerca de TZ Analyzer"),
    ("antes-de-comenzar", "Antes de comenzar"),
    ("inicio-rapido", "Inicio rápido"),
    ("modos", "Modos de análisis"),
    ("carpeta-salida", "Carpeta de salida"),
    ("resultados", "Resultados generados"),
    ("offline", "Uso sin conexión a Internet"),
    ("problemas-frecuentes", "Problemas frecuentes"),
    ("consideraciones", "Consideraciones de uso"),
    ("acerca-version", "Acerca de / Versión"),
    ("pendientes", "Pendiente de confirmar para la distribución Beta"),
)

# Placeholder técnico de la versión del MANUAL (no confundir con
# tz_web.app.APP_VERSION, la del shell de la aplicación): única fuente para
# que la cabecera del manual y la subsección "Versión" (10.3) muestren
# siempre el mismo texto, hasta que exista una versión Beta definitiva. No
# fijar aquí un número de versión — ver sección 10.3 del encargo MB6-2.
HELP_VERSION_LABEL = "Versión Beta: pendiente de confirmación para la primera distribución."
