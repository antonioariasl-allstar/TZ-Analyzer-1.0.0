"""FX-02 — Pruebas rojas de auditoría: bitácora de antenas sin contacto ni tipo de interacción.

Cubre hallazgos H-A a H-F y las inconsistencias H-H1/H-H2 documentados en la
auditoría de la sección "Filtrar interacciones por fecha"
(tz_core/interacciones_builder.py). No modifica producción; estas pruebas
deben fallar con el código actual por razones semánticas, no de fixture.
"""
import re
from pathlib import Path

import pandas as pd

from tz_core.interacciones_builder import construir_seccion_interacciones
from tz_core.logging_utils import write_minimal_filter_log


def _df_fx02() -> pd.DataFrame:
    """Bitácora sintética de navegación/antenas: sin columna de contacto ni de
    tipo de interacción, con duraciones enteras de unidad ambigua, 3 días distintos.
    """
    return pd.DataFrame(
        {
            "fecha": [
                "2026-08-01", "2026-08-01", "2026-08-01",
                "2026-08-02", "2026-08-02",
                "2026-08-03", "2026-08-03",
            ],
            "hora": [
                "08:15:00", "09:40:00", "12:05:00",
                "07:00:00", "14:20:00",
                "06:10:00", "18:50:00",
            ],
            "tel_investigado": ["70011111"] * 7,
            "antena": ["ANT-A", "ANT-B", "ANT-A", "ANT-C", "ANT-B", "ANT-C", "ANT-A"],
            "lat": [13.6929, 13.7000, 13.6929, 13.7100, 13.7000, 13.7100, 13.6929],
            "long": [-89.2182, -89.2100, -89.2182, -89.2300, -89.2100, -89.2300, -89.2182],
            "azimut": [45, 90, 45, 180, 90, 180, 45],
            "duracion": [30, 5400, 120, 3, 7200, 45, 900],
        }
    )


# ── H-A / H-B: placeholder de contacto contado como contacto único ─────────

def test_sin_columna_contacto_reporta_cero_contactos_validos():
    df = _df_fx02()
    html = construir_seccion_interacciones(df, config={})

    assert "Contactos únicos: 1" not in html, (
        "El placeholder 'SIN DETERMINAR' se está contando como un contacto único válido "
        "(regla: SIN DETERMINAR/NaN/vacío nunca cuenta como contacto)."
    )

    declara_cero_o_equivalente = (
        "Contactos únicos: 0" in html
        or re.search(
            r"sin contactos? v[aá]lidos?|contacto no disponible|no se identific(?:o|ó) contacto",
            html,
            re.I,
        )
        is not None
    )
    assert declara_cero_o_equivalente, (
        "Sin columna de contacto en la bitácora, el informe debe declarar 0 contactos "
        "válidos o una nota declarativa equivalente, no fabricar un conteo."
    )


# ── H-A / H-F: placeholder usado como entidad analítica (alertas de concentración) ──

def test_placeholder_no_se_usa_como_entidad_analitica():
    df = _df_fx02()
    html = construir_seccion_interacciones(df, config={})

    assert "Concentración (interacciones): SIN DETERMINAR" not in html, (
        "SIN DETERMINAR no puede presentarse como el contacto dominante de una alerta "
        "de concentración por interacciones."
    )
    assert "Concentración (duración): SIN DETERMINAR" not in html, (
        "SIN DETERMINAR no puede presentarse como el contacto dominante de una alerta "
        "de concentración por duración."
    )

    # No se exige que la cadena desaparezca del HTML por completo (podría aparecer en una
    # celda de tabla); lo que no puede ocurrir es que sea sujeto de una afirmación analítica.
    assert not re.search(r"SIN DETERMINAR\s+(acumula|concentra)", html), (
        "SIN DETERMINAR aparece como sujeto de una afirmación analítica; debe tratarse "
        "como dato no disponible, no como una entidad con comportamiento propio."
    )


# ── H-C: lenguaje de "interacciones"/comunicación clasificada sin columna de tipo ──

def test_sin_tipo_evento_no_afirma_comunicacion_clasificada():
    df = _df_fx02()
    html = construir_seccion_interacciones(df, config={})

    assert re.search(
        r"tipo de (evento|interacci[oó]n) no (est[aá] )?disponible|no se determin[oó] el tipo",
        html,
        re.I,
    ), "El informe debe declarar explícitamente que el tipo de evento/interacción no está disponible."

    for frase in (
        "LLAMADA ENTRANTE", "LLAMADA SALIENTE",
        "SMS ENTRANTE", "SMS SALIENTE",
        "MENSAJE ENTRANTE", "MENSAJE SALIENTE",
    ):
        assert frase not in html.upper(), (
            f"No debe afirmarse '{frase}' cuando no existe columna de tipo de interacción."
        )

    # La descripción diaria (encabezado h3 de cada día) debe usar lenguaje neutral
    # ("registros"/"eventos") en vez de dar por hecho que son "interacciones" clasificadas.
    # No se prohíbe la palabra en IDs internos, navegación o el nombre histórico de la sección.
    descripciones_dia = re.findall(r"<h3>(.*?)</h3>", html)
    assert descripciones_dia, "No se encontró el encabezado de descripción diaria (h3)."
    for desc in descripciones_dia:
        assert "interacciones" not in desc.lower(), (
            f"La descripción diaria debe usar lenguaje neutral (registros/eventos "
            f"disponibles), no dar por hecho 'interacciones': {desc!r}"
        )


# ── H-D / H-E: duración numérica convertida a HH:MM:SS sin unidad confirmada ──

def test_duracion_numerica_sin_unidad_no_se_presenta_como_hecho_confirmado():
    df = _df_fx02()
    html = construir_seccion_interacciones(df, config={})

    declara_unidad_incierta = re.search(
        r"unidad de duraci[oó]n[^.<]{0,80}no (?:pudo|se pudo|est[aá])[^.<]{0,40}(?:determinad|confirmad)",
        html,
        re.I,
    ) is not None

    if not declara_unidad_incierta:
        assert not re.search(r"<strong>Duraci[oó]n:</strong>\s*\d{2}:\d{2}:\d{2}", html), (
            "Se presenta una duración acumulada en formato HH:MM:SS como si fuera un hecho "
            "confirmado, sin declarar que la unidad de los valores de origen (columna "
            "'duracion' con enteros ambiguos) no está confirmada. Esta prueba no exige una "
            "heurística de segundos/minutos/milisegundos: exige que no se afirme sin base."
        )


# ── Control de no regresión: ausencia de contacto no debe bloquear antenas ──

def test_sin_contacto_no_bloquea_analisis_de_antenas():
    df = _df_fx02()
    html = construir_seccion_interacciones(df, config={})

    assert "No se registraron eventos en esta bitácora" not in html
    assert "Filtro por fecha no generado" not in html
    assert re.search(r"Antenas únicas:</strong>\s*[1-9]", html), (
        "Debe reportarse al menos una antena única pese a la ausencia de contacto/interacción."
    )
    assert re.search(r"\d+\s*antena\(s\)", html), (
        "El mini-mapa de calor diario debe reportar antenas válidas mapeadas."
    )


# ── H-H2: la sección de Limitaciones no declara los campos analíticos ausentes ──

def test_limitaciones_declaran_campos_analiticos_ausentes(tmp_path):
    from tz_core.html.assembler import generar_informe_html

    df = _df_fx02()
    kml_path = tmp_path / "caso.kml"
    kml_path.write_text("kml", encoding="utf-8")

    html_path = generar_informe_html(
        df=df,
        archivo_kml=str(kml_path),
        carpeta_salida=str(tmp_path),
        nombre_salida="fx02",
        hoja=None,
        nombre_bitacora=None,
        config={},
    )
    assert html_path, "generar_informe_html no produjo salida."
    contenido = Path(html_path).read_text(encoding="utf-8")

    m = re.search(r'<section id="limitaciones-analisis">(.*?)</section>', contenido, re.S)
    assert m, "No se encontró la sección 'Limitaciones del análisis' en el HTML."
    limitaciones = m.group(1)

    assert re.search(r"contacto[s]?[^.<]{0,40}(ausente|no disponible|no identificad)", limitaciones, re.I), (
        "Limitaciones debe declarar la ausencia de columna de contacto."
    )
    assert re.search(r"tipo de (interacci[oó]n|evento)[^.<]{0,40}(ausente|no disponible)", limitaciones, re.I), (
        "Limitaciones debe declarar la ausencia de tipo de interacción/evento."
    )
    assert re.search(r"unidad de duraci[oó]n[^.<]{0,60}no (confirmad|determinad)", limitaciones, re.I), (
        "Limitaciones debe declarar que la unidad de duración no está confirmada."
    )


# ── H-H1: criterio de "contactos únicos" incompatible entre HTML y log_minimo.txt ──

def test_contactos_unicos_consistente_entre_html_y_log_minimo(tmp_path):
    df = _df_fx02()

    html = construir_seccion_interacciones(df, config={})
    m_html = re.search(r"Contactos únicos:</strong>\s*(\d+)", html)
    assert m_html, "No se encontró el KPI 'Contactos únicos' en el HTML."
    contactos_html = int(m_html.group(1))

    log_path = tmp_path / "log_minimo.txt"
    write_minimal_filter_log(df, "FX-02", log_path)
    contenido_log = log_path.read_text(encoding="utf-8")
    m_log = re.search(r"Contactos únicos:\s*(\d+)", contenido_log)
    assert m_log, "No se encontró 'Contactos únicos' en log_minimo.txt."
    contactos_log = int(m_log.group(1))

    assert contactos_html == 0 and contactos_log == 0, (
        "Ambos productos deben coincidir en 0 contactos válidos para la misma bitácora "
        f"sin columna de contacto; obtenido HTML={contactos_html}, log_minimo={contactos_log}. "
        "Cualquier diferencia deliberada requiere un contrato explícito, hoy inexistente."
    )
