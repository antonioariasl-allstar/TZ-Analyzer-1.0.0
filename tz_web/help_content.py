"""tz_web.help_content — datos estáticos para /help (Manual de Usuario).

Separado de ``tz_web.routes`` para no mezclar contenido de documentación
(texto largo, aprobado editorialmente) con lógica de rutas. No importa nada
de ``tz_web.state`` ni depende de una sesión: el manual (MICROBLOQUE 6-2,
reestructurado en FASE 4B) es completamente independiente del caso en
curso — ver la sección de seguridad del encargo, AYUDA es documentación
estática/local.
"""

from __future__ import annotations

from typing import Tuple

# Única fuente de verdad para el índice/barra lateral del manual: id de
# ancla + título visible, en el orden en que deben aparecer. El contenido de
# cada sección vive en help.html; este módulo solo fija el orden y los
# rótulos que también reutiliza la barra lateral, para que ambos no puedan
# desincronizarse.
HELP_SECTIONS: Tuple[Tuple[str, str], ...] = (
    ("acerca", "¿Qué es TZ Analyzer?"),
    ("antes-de-comenzar", "Antes de comenzar"),
    ("inicio-rapido", "Inicio rápido"),
    ("preparacion-bitacora", "Preparación de la bitácora"),
    ("modo-1", "Modo 1 — Análisis completo"),
    ("modo-2", "Modo 2 — Análisis con filtro temporal"),
    ("modo-3", "Modo 3 — Mapeo manual"),
    ("campos", "Campos y su significado"),
    ("cobertura", "Interpretación de antenas, cobertura y azimut"),
    ("productos", "Carpeta de salida y productos generados"),
    ("privacidad", "Uso local, privacidad y conexión a Internet"),
    ("problemas-frecuentes", "Problemas frecuentes"),
    ("complementariedad", "Complementariedad con otras herramientas"),
    ("beta-autoria", "Versión Beta, autoría y uso de IA"),
)
