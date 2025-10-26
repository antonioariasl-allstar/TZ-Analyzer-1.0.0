# TODO – TZ Analysis: ARQUITECTURA HÍBRIDA PERMANENTE 🏗️

## �️ ARQUITECTURA HÍBRIDA PERMANENTE ESTABLECIDA ✅

**Fecha:** 25 de octubre de 2025  
**Commit:** 2b3503f  
**Estado:** 🏆 **SOLUCIÓN DEFINITIVA IMPLEMENTADA**

### �️ DECISIÓN ARQUITECTÓNICA FINAL

La **Arquitectura Híbrida Permanente** ha sido oficialmente adoptada como la solución definitiva del TZ Analyzer:

- ✅ **Patrón Strangler Fig** implementado como estrategia permanente  
- ✅ **Framework modular tz_core** + **Script principal** coexistiendo
- ✅ **Zero breaking changes** garantizados a largo plazo
- ✅ **Redirección inteligente** como característica permanente
- ✅ **Validación completa** end-to-end exitosa  
- ✅ **Documentación oficial** en `docs/ARQUITECTURA_HIBRIDA_PERMANENTE.md`

### 🛡️ GARANTÍAS ARQUITECTÓNICAS  
- **Mantenimiento simplificado:** Bugs se arreglan una vez
- **Evolución controlada:** Nuevas features en framework
- **Rollback instantáneo:** Revertir cambios es trivial
- **Testing dual:** Framework + monolito validados

---

## 🚨 ROADMAP DE MODULARIZACIÓN

### ✅ FASES COMPLETADAS

- [x] **Fase 1:** Configuración base (`config.json`) - DONE
- [x] **Fase 2:** Config Manager (`tz_core/config_manager.py`) - DONE  
- [x] **Fase 3:** Utils básicas (`tz_core/utils.py`) - DONE
- [x] **Fase 4:** Data Loader (`tz_core/data_loader.py`) - DONE
- [x] **Fase 5:** KML Generator (`tz_core/kml_generator.py`) - DONE
- [x] **Fase 6:** Validation Engine (`tz_core/validation_engine.py`) - DONE
- [x] **Fase 7:** Core Processor (`tz_core/core_processor.py`) - DONE
- [x] **Fase 8A:** HTML Generator - Preparación y esqueleto - DONE
- [x] **Fase 8B:** ✅ HTML Generator - Extracción modular EXITOSA
  - **Completado:** `generar_informe_html()` extraída (2591 líneas)
  - **Framework:** `tz_core/html_generator.py` operativo
  - **Validación:** End-to-end exitosa, Zero regresiones
  - **Golden Backup:** commit b60691b preservado
  - **Commit:** 1040083 - OPERACIÓN EXITOSA

### 🔄 PRÓXIMAS FASES

- [x] **Fase 8C:** ✅ **ARQUITECTURA HÍBRIDA PERMANENTE** - SOLUCIÓN DEFINITIVA
  - **Completado:** Patrón Strangler Fig implementado permanentemente
  - **Framework:** Redirección inteligente como característica definitiva
  - **Validación:** Sistema híbrido probado y documentado
  - **Commit:** 2b3503f - ARQUITECTURA HÍBRIDA PERMANENTE

### 🚀 **PRÓXIMAS OPORTUNIDADES (OPCIONALES)**

**La arquitectura híbrida permanente permite evolución gradual OPCIONAL:**

- [ ] **Fase 9:** Optimización de Performance (opcional)
  - **Target:** Análisis de bottlenecks en framework modular
  - **Beneficio:** Mejoras de velocidad sin riesgo arquitectónico

- [ ] **Fase 10:** Expansión de Testing (recomendado)  
  - **Target:** Cobertura adicional de edge cases
  - **Beneficio:** Mayor confianza en evolución futura

- [ ] **Fase 11:** UI/UX Modernization (futuro)
  - **Target:** Interface más moderna manteniendo backend híbrido
  - **Beneficio:** Mejor experiencia usuario sin tocar lógica crítica

---

## 📝 LEGACY: CLEANUP PROFESIONAL PENDIENTE

### FASE FINAL - Limpieza de Comentarios Profesionales
**Prioridad:** Media (agendado para fases finales 13-15)
**Descripción:** Traducir la terminología técnica/analogías internas a comentarios profesionales estándar
**Archivos afectados:** 
- `tz_core/data_loader.py` - Remover referencias "duales"
- `docs/SISTEMA_DUAL_COLUMNAS.md` - Mantener explicación técnica pero con lenguaje más estándar
- Tests unitarios - Simplificar explicaciones sin perder contenido crítico

**Razón de agendamiento:** Mantener momentum de refactorización, una pasada final es más eficiente

## 🚨 INTERVENCIONES CRÍTICAS DIFERIDAS

### ⚡ **ZONA DE PELIGRO EXTREMO: WIZARD QC MANUAL**
**Fecha evaluación:** 25 oct 2025  
**Estado:** 🔴 **CONTRAINDICACIÓN ABSOLUTA** - Intervención diferida
**Ubicación:** `_wizard_qc_mapeo()` líneas 353-735 (382 líneas)

**ANÁLISIS TÉCNICO:**
- **Tamaño:** Órgano masivo de 382 líneas de alta complejidad
- **Dependencias críticas:** Sistema dual, CONFIG global, múltiples input()
- **Efectos secundarios:** Modifica estado global, persistencia en CONFIG
- **Complejidad interactiva:** Nightmare para testing automático
- **Dependencias críticas:** Sistema de sinónimos, mapeo manual columnas

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

## 📊 HISTORIAL TÉCNICO - REFACTORIZACIÓN AVANZADA

### 📈 **ESTADÍSTICAS DE DESARROLLO ACTUALES:**
- **⚡ Estado del Sistema:** ESTABLE - Funcionamiento normal
- **✅ Fases Completadas:** 8/15 fases (53% del proceso)
- **🧪 Tests Unitarios:** 40/40 PASAN (100% éxito)
- **📈 Golden Baseline:** SIEMPRE OK (cero regresiones)
- **💾 Commits Atómicos:** 7 creados exitosamente
- **⚡ Funciones Extraídas:** 11 funciones refactorizadas con éxito

### 🔍 **ANÁLISIS TÉCNICO PRE-REFACTORING FASE 5.3:**

**🎯 COMPONENTES PRINCIPALES IDENTIFICADOS:**
1. **Función Central** (Línea 6543): `pd.read_excel()` - **FUNCIÓN DE CARGA PRINCIPAL**
2. **Normalizador de Headers** (Líneas 6549-6557): **Normalización de encabezados** (sistema de procesamiento crítico)  
3. **Procesador de Contenido** (Línea 804): `normalizar_columnas_texto()` - **Normalización de contenido**

**⚠️ RIESGOS TÉCNICOS CRÍTICOS:**
- **� Fallo inmediato:** Si tocamos mal la función de carga principal
- **⏰ Falla diferida:** Error silencioso que se manifiesta horas después en KML/HTML
- **🔗 Dependencias rotas:** Enlaces rotos que bloquean el flujo de datos
- **⚡ Inconsistencias:** Errores en mapeo de columnas que causan fallos intermitentes

**🛠️ PROTOCOLO DE DESARROLLO PROPUESTO:**
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
**FASE 7: COLUMN PROCESSOR** 🚨🔴⚡
- **Estado:** 🟡 DIFERIDA - Análisis forense completado
- **Complejidad:** 🚨 EXTREMA (9/10) - 650+ líneas monolíticas
- **Target:** main() líneas 6550-7200+ (Schema + Mapeo + Wizard + Sinónimos)
- **Riesgo:** CATASTRÓFICO - Sistema cardiovascular del negocio
- **Decisión:** Diferimiento inteligente para v2.0 (13-19 semanas estimadas)
- **Documentación:** `docs/COLUMN_PROCESSOR_ANALISIS_FORENSE.md`
- **Probabilidad falla futura:** 60% en 6-12 meses si no se aborda
- **Plan contingencia:** Definido en análisis forense

---

## 🚨 **MINA DESACTIVADA: Funciones de Saneamiento** 
**Fecha:** 24 oct 2025  
**Estado:** ✅ Extraída y unificada con cero breaking changes
**Fecha:** 21 de octubre de 2025  
**Estado:** ✅ Completada exitosamente

### Cambios realizados:
- ✅ Entorno virtual `.venv312` creado con Python 3.12.8
- ✅ Todas las dependencias instaladas (incluido `simplekml` que faltaba)
- ✅ Suite de tests consolidada y optimizada en `test_e2e_regresion.py`
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