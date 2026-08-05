"""Pruebas del clasificador puro de confiabilidad de duración (FX-02, Hito 1).

Cubre el modelo `DuracionEstado` y `clasificar_confiabilidad_duracion()` de
tz_core/bitacora_normalization.py. No ejercita consumidores (interacciones_builder,
html/assembler, etc.) — esa integración queda para un hito posterior.
"""
import pandas as pd
import pandas.testing as pdt

from tz_core.bitacora_normalization import (
    DuracionEstado,
    clasificar_confiabilidad_duracion,
    preguntar_unidad_duracion_qc,
    requiere_pregunta_qc_duracion,
)


def _df(valores, columna="duracion"):
    return pd.DataFrame({columna: valores})


# 1. Columna ausente
def test_columna_ausente_reporta_estado_ausente():
    df = pd.DataFrame({"otra_col": [1, 2, 3]})
    estado = clasificar_confiabilidad_duracion(df)
    assert estado.estado == "ausente"
    assert estado.unidad is None
    assert estado.columna is None
    assert estado.motivo == "sin_columna"
    assert estado.confiable is False


# 2. Columna vacía (todo NaN o placeholders vacíos)
def test_columna_vacia_reporta_estado_ausente():
    df = _df([None, None, None])
    estado = clasificar_confiabilidad_duracion(df)
    assert estado.estado == "ausente"
    assert estado.unidad is None
    assert estado.columna == "duracion"
    assert estado.motivo == "sin_valores"


# 3. HH:MM:SS -> segura/hhmmss
def test_formato_hhmmss_es_seguro():
    df = _df(["00:05:30", "01:12:00", "00:00:45"])
    estado = clasificar_confiabilidad_duracion(df)
    assert estado.estado == "segura"
    assert estado.unidad == "hhmmss"
    assert estado.motivo == "formato_autodescriptivo"
    assert estado.confiable is True


# 4. MM:SS -> segura/hhmmss
def test_formato_mmss_es_seguro():
    df = _df(["05:30", "12:00", "00:45"])
    estado = clasificar_confiabilidad_duracion(df)
    assert estado.estado == "segura"
    assert estado.unidad == "hhmmss"
    assert estado.motivo == "formato_autodescriptivo"


# 5. Encabezado duracion_seg -> segura/segundos
def test_encabezado_duracion_seg_es_seguro_segundos():
    df = _df([30, 5400, 120], columna="duracion_seg")
    estado = clasificar_confiabilidad_duracion(df)
    assert estado.estado == "segura"
    assert estado.unidad == "segundos"
    assert estado.motivo == "encabezado_declara_segundos"


# 6. Encabezado duration_seconds -> segura/segundos
def test_encabezado_duration_seconds_es_seguro_segundos():
    df = _df([30, 5400, 120], columna="duration_seconds")
    estado = clasificar_confiabilidad_duracion(df)
    assert estado.estado == "segura"
    assert estado.unidad == "segundos"
    assert estado.motivo == "encabezado_declara_segundos"


# 7. Columna genérica numérica sin unidad -> ambigua
def test_columna_generica_numerica_sin_unidad_es_ambigua():
    df = _df([30, 5400, 120, 3, 7200, 45, 900])
    estado = clasificar_confiabilidad_duracion(df)
    assert estado.estado == "ambigua"
    assert estado.unidad == "desconocida"
    assert estado.motivo == "columna_generica_numerica_sin_unidad"
    assert estado.confiable is False


# 8. unidad_declarada=segundos -> segura/segundos
def test_unidad_declarada_segundos_es_segura():
    df = _df([30, 5400, 120])
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="segundos")
    assert estado.estado == "segura"
    assert estado.unidad == "segundos"
    assert estado.motivo == "seleccion_usuario_segundos"


# 8b. unidad_declarada=milisegundos -> segura/milisegundos
def test_unidad_declarada_milisegundos_es_segura():
    df = _df([760905, 5400000, 120000])
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="milisegundos")
    assert estado.estado == "segura"
    assert estado.unidad == "milisegundos"
    assert estado.motivo == "seleccion_usuario_milisegundos"


# 9. unidad_declarada=minutos -> segura/minutos
def test_unidad_declarada_minutos_es_segura():
    df = _df([30, 5400, 120])
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="minutos")
    assert estado.estado == "segura"
    assert estado.unidad == "minutos"
    assert estado.motivo == "seleccion_usuario_minutos"


# 10. unidad_declarada=desconocida -> ambigua/desconocida
def test_unidad_declarada_desconocida_es_ambigua():
    df = _df([30, 5400, 120])
    estado = clasificar_confiabilidad_duracion(df, unidad_declarada="desconocida")
    assert estado.estado == "ambigua"
    assert estado.unidad == "desconocida"
    assert estado.motivo == "seleccion_usuario_desconocida"


# 11. No debe inferir unidad por magnitud (valores grandes no cambian el resultado)
def test_no_infiere_unidad_por_valores_grandes():
    df_pequenos = _df([1, 2, 3])
    df_grandes = _df([360000, 720000, 999999])
    estado_pequenos = clasificar_confiabilidad_duracion(df_pequenos)
    estado_grandes = clasificar_confiabilidad_duracion(df_grandes)
    assert estado_pequenos.estado == estado_grandes.estado == "ambigua"
    assert estado_pequenos.unidad == estado_grandes.unidad == "desconocida"
    assert estado_pequenos.motivo == estado_grandes.motivo == "columna_generica_numerica_sin_unidad"


# 12. El clasificador no modifica el DataFrame
def test_no_modifica_el_dataframe():
    df = _df([30, 5400, 120])
    original = df.copy()
    clasificar_confiabilidad_duracion(df)
    pdt.assert_frame_equal(df, original)


# Extra: encabezado_original explícito tiene prioridad sobre el nombre de columna
def test_encabezado_original_explicito_declara_segundos():
    df = _df([30, 5400, 120])  # columna canónica ya renombrada a "duracion"
    estado = clasificar_confiabilidad_duracion(df, encabezado_original="duracion_seg")
    assert estado.estado == "segura"
    assert estado.unidad == "segundos"
    assert estado.motivo == "encabezado_declara_segundos"
    assert estado.columna_original == "duracion_seg"


# Extra: DuracionEstado.confiable no se almacena como campo duplicado
def test_duracion_estado_confiable_es_propiedad_no_campo():
    assert "confiable" not in DuracionEstado.__dataclass_fields__
    estado = DuracionEstado(estado="segura", unidad="segundos", columna="duracion",
                             columna_original="duracion_seg", motivo="x")
    assert estado.confiable is True


# ── PASO 4: pregunta QC condicional ─────────────────────────────────────

def test_requiere_pregunta_qc_solo_para_columna_generica_numerica():
    df = _df([30, 5400, 120, 3, 7200, 45, 900])
    estado = clasificar_confiabilidad_duracion(df)
    assert requiere_pregunta_qc_duracion(estado) is True


def test_no_requiere_pregunta_qc_si_hhmmss():
    df = _df(["00:05:30", "01:12:00"])
    estado = clasificar_confiabilidad_duracion(df)
    assert requiere_pregunta_qc_duracion(estado) is False


def test_no_requiere_pregunta_qc_si_encabezado_declara_segundos():
    df = _df([30, 5400, 120], columna="duracion_seg")
    estado = clasificar_confiabilidad_duracion(df)
    assert requiere_pregunta_qc_duracion(estado) is False


def test_no_requiere_pregunta_qc_si_columna_ausente():
    df = pd.DataFrame({"otra_col": [1, 2, 3]})
    estado = clasificar_confiabilidad_duracion(df)
    assert requiere_pregunta_qc_duracion(estado) is False


def test_no_requiere_pregunta_qc_si_columna_vacia():
    df = _df([None, None])
    estado = clasificar_confiabilidad_duracion(df)
    assert requiere_pregunta_qc_duracion(estado) is False


def test_preguntar_unidad_qc_opcion_1_es_milisegundos():
    assert preguntar_unidad_duracion_qc(prompt_fn=lambda _msg: "1") == "milisegundos"


def test_preguntar_unidad_qc_opcion_2_es_segundos():
    assert preguntar_unidad_duracion_qc(prompt_fn=lambda _msg: "2") == "segundos"


def test_preguntar_unidad_qc_opcion_3_es_minutos():
    assert preguntar_unidad_duracion_qc(prompt_fn=lambda _msg: "3") == "minutos"


def test_preguntar_unidad_qc_opcion_4_es_desconocida():
    assert preguntar_unidad_duracion_qc(prompt_fn=lambda _msg: "4") == "desconocida"


def test_preguntar_unidad_qc_enter_equivale_a_desconocida():
    assert preguntar_unidad_duracion_qc(prompt_fn=lambda _msg: "") == "desconocida"


def test_preguntar_unidad_qc_otro_valor_equivale_a_desconocida():
    assert preguntar_unidad_duracion_qc(prompt_fn=lambda _msg: "9") == "desconocida"


def test_preguntar_unidad_qc_muestra_texto_esperado():
    mensajes = []

    def _prompt(msg):
        mensajes.append(msg)
        return ""

    preguntar_unidad_duracion_qc(prompt_fn=_prompt)
    texto = mensajes[0]
    assert "el archivo no indica claramente la unidad de medida" in texto
    assert "[1] Milisegundos" in texto
    assert "[2] Segundos" in texto
    assert "[3] Minutos" in texto
    assert "[4] Unidad desconocida" in texto


def test_preguntar_unidad_qc_respuesta_no_pegada_a_opcion_4():
    mensajes = []

    def _prompt(msg):
        mensajes.append(msg)
        return ""

    preguntar_unidad_duracion_qc(prompt_fn=_prompt)
    texto = mensajes[0]
    idx_opcion4 = texto.index("[4] Unidad desconocida")
    idx_opcion_linea = texto.index("Opción")
    assert idx_opcion_linea > idx_opcion4
    entre = texto[idx_opcion4:idx_opcion_linea]
    assert entre.count("\n") >= 2
