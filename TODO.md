# TODO – TZ Analysis: OPERACIÓN A CORAZÓN ABIERTO 🫀
Rama: refactor/modular-architecture  
Fase: Post-Quirúrgica 5.3a (Sistema cardiovascular dual extraído exitosamente)  
Fecha: 2025-10-25  
**Estado del Paciente:** EXCELENTE - Fase 5.3a completada con sistema dual preservado

> **🫀 ANALOGÍA MÉDICA:** La refactorización del TZ Analyzer es literalmente una **operación a corazón abierto**. La Fase 5.3a logró extraer exitosamente el **sistema cardiovascular dual** manteniendo ambas arterias (columnas originales + normalizadas) funcionando perfectamente.

> **📋 Handoff para casa:** Ver archivo `HANDOFF_CASA.txt` en la raíz del repo con instrucciones paso a paso para continuar el trabajo en casa.

## 🏥 AGENDA POST-QUIRÚRGICA

### FASE FINAL - Limpieza de Comentarios Profesionales
**Prioridad:** Media (agendado para fases finales 13-15)
**Descripción:** Traducir la jerga médica/analogías internas a comentarios profesionales
**Archivos afectados:** 
- `tz_core/data_loader.py` - Remover referencias "cardiovasculares"
- `docs/SISTEMA_CARDIOVASCULAR_DUAL.md` - Mantener explicación técnica pero con lenguaje más estándar
- Tests unitarios - Simplificar explicaciones sin perder contenido crítico

**Razón de agendamiento:** Mantener momentum de refactorización, una pasada final es más eficiente

## 🚨 INTERVENCIONES CRÍTICAS DIFERIDAS

### ⚡ **ZONA DE PELIGRO EXTREMO: WIZARD QC MANUAL**
**Fecha evaluación:** 25 oct 2025  
**Estado:** 🔴 **CONTRAINDICACIÓN ABSOLUTA** - Intervención diferida
**Ubicación:** `_wizard_qc_mapeo()` líneas 353-735 (382 líneas)

**DIAGNÓSTICO MÉDICO:**
- **Tamaño:** Órgano masivo de 382 líneas de alta complejidad
- **Dependencias críticas:** Sistema dual, CONFIG global, múltiples input()
- **Efectos secundarios:** Modifica estado global, persistencia en CONFIG
- **Complejidad interactiva:** Nightmare para testing automático
- **Conexiones arteriales:** Sistema de sinónimos, mapeo manual columnas

**CONTRAINDICACIONES:**
- ❌ Intervención inmediata causaría falla sistémica
- ❌ Testing automático imposible sin refactoring previo  
- ❌ Dependencias circulares con funciones ya extraídas
- ❌ Core crítico del negocio con cero tolerancia a fallas

**ESTRATEGIA DE DIFERIMIENTO:**
- ⏳ **Agendar para fases 12-13** (especialización en interactividad)
- 🩺 **Requiere cirugía especializada** con mocking avanzado
- 📋 **Prioridad alta** pero solo cuando tengamos experiencia suficiente
- 🔄 **Re-evaluación obligatoria** antes de cualquier intervención

**ADVERTENCIA:** Cualquier desarrollador que vea esta función debe CONSULTAR este documento antes de modificarla.

## 🎯 NOTAS TÉCNICAS CRÍTICAS - REFACTORING

### 🚨 **MINA DESACTIVADA: Funciones de Saneamiento** 
**Fecha:** 24 oct 2025  
**Estado:** ✅ Extraída y unificada con cero breaking changes

**CONTEXTO:** Se detectó que `_sanear_nombre_archivo` y `_sanear_nombre_archivo_local` 
eran casi idénticas pero con fallbacks diferentes. Se unificaron en `sanear_nombre_archivo()` 
con parámetro fallback.

**TESTING PENDIENTE:**
- Golden Baseline actual usa datos "limpios" (sin caracteres problemáticos)
- Las funciones de saneamiento probablemente no se ejercitan en pruebas actuales
- **ACCIÓN FUTURA:** Crear test con datos problemáticos:
  ```
  TIPO_LLAMADA: "Llamada@Entrañte#"
  UBICACION: "Café & Restaurante José María"
  ```

### 🧠 **MEMORIA INNECESARIA: Sistema de Sinónimos**
**Fecha:** 24 oct 2025  
**Estado:** ⚠️ Candidato a desactivación

**CONTEXTO:** El sistema actual mantiene dos tipos de sinónimos:
- `synonyms`: Legacy del mapeo automático (686 líneas en config.json)
- `synonyms_user`: Memoria que crece automáticamente con cada mapeo

**PROBLEMA:** La memoria automática era útil para mapeo automático, pero 
actualmente el mapeo es 100% manual, haciendo innecesaria la recopilación.

**IMPACTO:** Los sinónimos legacy ocupan espacio y pueden confundir, pero 
el sistema sigue funcionando correctamente.

**ACCIÓN FUTURA:** Considerar desactivar `synonyms_user` automático y 
limpiar sinónimos legacy obsoletos. Probar con datos reales primero.

## 🏥 EXPEDIENTE MÉDICO - OPERACIÓN A CORAZÓN ABIERTO

### � **ESTADÍSTICAS QUIRÚRGICAS ACTUALES:**
- **🫀 Estado del Paciente:** ESTABLE - Signos vitales normales
- **✅ Operaciones Completadas:** 8/15 fases (53% del procedimiento)
- **🧪 Tests Unitarios:** 40/40 PASAN (100% éxito)
- **📈 Golden Baseline:** SIEMPRE OK (cero regresiones)
- **💾 Commits Atómicos:** 7 creados exitosamente
- **⚡ Funciones Extraídas:** 11 funciones trasplantadas con éxito

### 🩺 **DIAGNÓSTICO PRE-QUIRÚRGICO FASE 5.3:**

**🫀 ARTERIAS PRINCIPALES IDENTIFICADAS:**
1. **Arteria Aorta** (Línea 6543): `pd.read_excel()` - **FUNCIÓN DE CARGA PRINCIPAL**
2. **Arteria Coronaria** (Líneas 6549-6557): **Normalización de encabezados** (sistema circulatorio crítico)  
3. **Arteria Pulmonar** (Línea 804): `normalizar_columnas_texto()` - **Normalización de contenido**

**⚠️ RIESGOS CARDIOVASCULARES CRÍTICOS:**
- **💀 Paro cardíaco inmediato:** Si tocamos mal la función de carga principal
- **🩸 Isquemia diferida:** Falla silenciosa que se manifiesta horas después en KML/HTML
- **🫁 Embolia:** Dependencias rotas que bloquean el flujo de datos
- **💓 Arritmia:** Inconsistencias en mapeo de columnas que causan fallos intermitentes

**🏥 PROTOCOLO QUIRÚRGICO PROPUESTO:**
- **Opción A:** División en sub-fases ultra-granulares (5.3a, 5.3b, 5.3c)
- **Opción B:** Análisis forense más exhaustivo antes de proceder
- **Requisito:** **CIRUJANO DESCANSADO AL 100%** - OBLIGATORIO

### 📋 **HISTÓRICO QUIRÚRGICO EXITOSO:**

**🎯 FASE 3 - UTILIDADES PURAS (COMPLETADA):**
1. ✅ `sha256_de_archivo` (Commit: 3e8b629)
2. ✅ `escribe_hashes_txt` (Commit: 96584bf)  
3. ✅ `compactar_ruta` (Commit: ae4423d)
4. ✅ `sanear_nombre_archivo` (Commit: 2d4c724) - **MINA DESACTIVADA**

**🎯 FASE 4 - CONFIGURACIÓN COMPLETA (COMPLETADA):**
- ✅ **4.1:** `cargar_config()` (Commit: 2d4c724)
- ✅ **4.2:** `bootstrap_config()` + sinónimos (Commit: f4e159c) - **BOMBA DESACTIVADA**
- ✅ **4.3:** `solicitar_color_tema()` (Commit: 9695f02) - **MINA INTERACTIVA DESACTIVADA**
- ✅ **4.4:** Persistencia config (Commit: 3384d90) - **MINAS PERSISTENCIA DESACTIVADAS**

**🎯 FASE 5.1-5.2 - DATA_LOADER (COMPLETADA):**
- ✅ **5.1:** Funciones puras data_loader (Commit: 0dda2dc) - **MINAS DESACTIVADAS**
- ✅ **5.2:** Funciones interactivas (Commit: 9eb3335) - **MINAS INTERACTIVAS DESACTIVADAS**
- ✅ **5.3a:** Sistema cardiovascular dual (Commit: 02564b0) - **ARTERIAS CRÍTICAS ESTABILIZADAS**

### 🚨 **OPERACIÓN DIFERIDA POR RIESGO EXTREMO:**
**FASE 5.3b: WIZARD QC MANUAL** ⚡🔴🚨
- **Estado:** CONTRAINDICADO - Diferido para fases 12-13
- **Órgano:** `_wizard_qc_mapeo()` 382 líneas críticas
- **Riesgo:** EXTREMO - Órgano vital con dependencias masivas
- **Requisito:** Framework especializado + 3+ meses planificación
- **Documentación:** `docs/WIZARD_QC_PELIGRO_EXTREMO.md`

### 🟡 **FASE 6 EVALUADA Y DIFERIDA:**
**FILE PROCESSOR - Análisis completado** 📁
- **Estado:** ✅ EVALUADO - Diferido estratégicamente para v2.0+
- **Hallazgos:** `utilidades.py` ya modularizado y optimizado para Excel
- **Decisión médica:** Sistema actual perfecto para workflow con mapeo manual
- **Razón de diferimiento:** Bitácoras requieren análisis humano de estructura
- **Documentación:** Ver `docs/FILE_PROCESSOR_ESTADO_ACTUAL.md`

### 🟠 **PRÓXIMA OPERACIÓN CRÍTICA:**
**FASE 7: COLUMN PROCESSOR** �
- **Arteria objetivo:** Mapeo manual, renombrado, coalescencia, sinónimos
- **Riesgo:** ALTO - Conexión con wizard diferido pero funciones independientes
- **Estrategia:** Extracción cuidadosa evitando wizard QC

---

## 🚨 **MINA DESACTIVADA: Funciones de Saneamiento** 
**Fecha:** 24 oct 2025  
**Estado:** ✅ Extraída y unificada con cero breaking changes
**Fecha:** 21 de octubre de 2025  
**Estado:** ✅ Completada exitosamente

### Cambios realizados:
- ✅ Entorno virtual `.venv312` creado con Python 3.12.8
- ✅ Todas las dependencias instaladas (incluido `simplekml` que faltaba)
- ✅ Test de regresión `test_kml_regresion.py` ejecutado exitosamente
- ✅ README.md actualizado con la versión de Python requerida
- ✅ `requirements.txt` actualizado con `simplekml==1.3.6`
- ✅ `.gitignore` protegiendo correctamente el entorno virtual

### Notas:
- Pylance muestra advertencias de tipo (type hints) más estrictas en Python 3.12.8, pero **el código funciona correctamente**
- Las advertencias son de análisis estático y no afectan la ejecución
- El motor y la lógica del programa **no fueron modificados**

---

## Pase 1 (diagnóstico sin cambiar lógica)  
Fecha: 2025-10-16  
Criterio: Solo observaciones del código visible. Nada de features nuevas.

## validaciones.py
Funciones reales (según archivo):
- validar_datos(df, columnas_esenciales) -> (pd.DataFrame, List[str])
- guardar_errores(errores, carpeta_salida, nombre_base) -> Optional[str]
- _to_object(df, cols)
- _is_excel_serial(x)
- _excel_serial_to_timestamp(x)
- _safe_to_datetime(series, dayfirst=True, errors="coerce")
- _normalize_fecha_col(df, col)
- _normalize_hora_col(df, col)
- _to_float_safe(series)
- _coerce_azimut(series)
- _ensure_lon_name(df)
- _ensure_lat_name(df)

Pendientes observables (higiene, sin tocar lógica):
- [ ] Agregar docstrings breves a `validar_datos` y `guardar_errores` (qué hace, params, retorno).
- [ ] Verificar que los mensajes se gestionen por `logging` desde `run.py` (aquí no configurar logging).
- [ ] Confirmar consistencia de `"_SIN_INF"` en todas las salidas de formateo (solo revisión).
- [ ] (Opcional) Añadir type hints solo en funciones **públicas** si son obvios (sin cambiar cuerpos).

Notas:
- No filtra filas ni aborta: la etapa HTML/KML decide; mantener ese contrato.

## run.py
Funciones / responsabilidades (según archivo):
- Punto de entrada del programa (menú / opciones).
- Orquestación: lectura de bitácora, validaciones, generación de salidas (HTML/KML/KMZ), rutas de salida.

Pendientes observables (higiene, sin cambiar lógica):
- [ ] Centralizar configuración de `logging` aquí (nivel y formato simples). No configurar en módulos.
- [ ] Docstring breve al inicio del archivo explicando flujo general (1–2 líneas).
- [ ] Mensajes de usuario: revisar que sean claros y consistentes (evitar prints ruidosos).
- [ ] Manejo de errores: envolver la ejecución principal en try/except con mensaje legible + `logging.error(...)`.
- [ ] Comprobación de carpetas de salida: asegurar `os.makedirs(..., exist_ok=True)` antes de escribir.

Notas:
- Mantener contratos actuales con módulos (`validaciones`, `kml_generador`, etc.).
- No cambiar nombres de opciones del menú en este pase.

## kml_generador.py
Funciones / responsabilidades (según archivo):
- Construcción de KML/KMZ a partir del DataFrame validado.
- Formateo de coordenadas y burbujas (placemarks), agrupaciones por criterio (fecha/rango, top antenas).

Pendientes observables (higiene, sin cambiar lógica):
- [ ] Docstrings breves en funciones públicas clave (qué hace, params, return).
- [ ] Revisar consistencia de formato en lat/lon (6 decimales, sin ‘.0’ en enteros cuando aplique).
- [ ] Confirmar que solo se muestren campos con dato (omitir “Sin Inf.” en la burbuja si así está definido).
- [ ] Validar que el nombre de archivos/carpetas no introduzca caracteres problemáticos (solo verificación).
- [ ] (Opcional) Extraer pequeñas utilidades repetidas (helpers) si existen bloques duplicados.

Notas:
- Respetar estructura de carpetas actual y nombres base (no modificar en este pase).
- Mantener compatibilidad con configuración desde `config.json`.

## Transversal
- [ ] Configurar `logging` en `run.py` (no en módulos) con formato simple visible en consola.
- [ ] Mantener `"_SIN_INF"` coherente en todas las salidas (HTML/KML/KMZ).
- [ ] Tests mínimos (pytest) para normalización de fecha/hora y formateo de lat/lon.
- [ ] Confirmar zonas horarias y `dayfirst=True` donde aplique.
- [ ] Documentar en `README.md` requisitos básicos y flujo general (breve).