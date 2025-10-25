# 🎯 PLAN MAESTRO DE REFACTORIZACIÓN TZ ANALYZER
## De Monolito a Arquitectura Modular de Clase Mundial

**Versión:** 2.0  
**Fecha inicio:** 24 de octubre de 2025  
**Estado:** En preparación  
**Responsable:** Equipo de desarrollo + Claude Sonnet 4  

---

## 🚨 PROTOCOLO ANTI-EXPLOSIÓN

> **"En campo minado: un paso mal calculado explota todo el proyecto"**

### 🛡️ FILOSOFÍA DE SEGURIDAD

**Principios inviolables:**
1. **UN cambio a la vez** - Nunca mezclar refactor + features + bugfix
2. **Tests ANTES que código** - Golden baseline es sagrado
3. **Rollback en <5 minutos** - Siempre hay plan B
4. **Gates obligatorios** - FAIL en cualquier gate = STOP total
5. **Documentación en tiempo real** - Cada paso se documenta AL HACERLO

### ⚠️ REGLAS DE ORO

- ✅ **VERDE para continuar:** Todos los gates PASS
- 🛑 **ROJO para STOP:** Cualquier gate FAIL
- 📋 **AMARILLO para revisar:** Gate PASS pero con warnings

**Si algo se rompe:**
1. **STOP inmediato** - No "arreglar sobre la marcha"
2. **Git stash/reset** al último commit bueno
3. **Analizar causa raíz** antes de reintentar
4. **Actualizar plan** si es necesario

---

## 📊 ESTADO ACTUAL VS OBJETIVO

### ❌ **ESTADO ACTUAL (Monolito Insostenible)**
```
TZ Analyzer 1.0 - MONOLITO
├── script_principal_bitacoras_refactory.py (7,680 líneas)
│   ├── 200+ funciones mezcladas
│   ├── Configuración + I/O + Validación + Análisis + KML + HTML + UI
│   ├── Funciones duplicadas
│   ├── Sin tests unitarios
│   └── Sin separación de responsabilidades
├── config.json (configuración)
├── utilidades.py (algunas utilidades)
└── validaciones.py (validaciones básicas)
```

**Problemas identificados:**
- ✗ Deuda técnica crítica
- ✗ Imposible de mantener
- ✗ Cambios riesgosos
- ✗ Sin tests automatizados
- ✗ Debugging complejo

### ✅ **OBJETIVO (Arquitectura Modular)**
```
TZ Analyzer 2.0 - MODULAR
├── script_principal.py (solo main + orquestación, <200 líneas)
├── config.json (configuración externa)
├── tz_core/ (núcleo modular)
│   ├── __init__.py
│   ├── config_manager.py (gestión de configuración)
│   ├── data_loader.py (carga Excel/TSV/CSV) 
│   ├── data_validator.py (validación/limpieza)
│   ├── data_processor.py (análisis/agregaciones)
│   ├── kml_generator.py (generación KML/KMZ)
│   ├── html_generator.py (reportes HTML)
│   ├── ui_helpers.py (menús/wizards)
│   └── utils.py (utilidades comunes)
├── tests/ (suite completa de tests)
│   ├── golden/ (baseline de regresión)
│   ├── unit/ (tests por módulo)
│   ├── integration/ (tests end-to-end)
│   └── fixtures/ (datos de prueba)
└── docs/ (documentación técnica)
```

**Beneficios esperados:**
- ✅ Mantenibilidad alta
- ✅ Tests automatizados
- ✅ Cambios seguros
- ✅ Onboarding rápido
- ✅ Debugging eficiente

---

## 🗺️ ROADMAP DE TRANSFORMACIÓN (15 Fases)

### **FASE 0: PREPARACIÓN Y SEGURIDAD** 🛡️

#### **0.1 Documentación y Planificación**
- [x] Crear Biblia de Desarrollo v2.0
- [x] Crear Plan Maestro v2.0  
- [ ] Crear rama `refactor/modular-architecture`
- [ ] Tag de versión pre-refactor (`v1.0-pre-refactor`)

#### **0.2 Baseline de Seguridad**
- [ ] Backup completo del repositorio
- [ ] Verificar que script actual funciona con datos de prueba
- [ ] Documentar configuración del entorno

**Gates de Fase 0:**
- [ ] ✅ **BUILD PASS:** Script actual compila y ejecuta sin errores
- [ ] ✅ **ENV PASS:** Entorno Python configurado correctamente
- [ ] ✅ **BRANCH PASS:** Rama de refactor creada y activa

---

### **FASE 1: BASELINE DORADO** 🏆

#### **1.1 Crear Golden Standard**
- [ ] Ejecutar `python -m tests.update_golden` 
- [ ] Verificar generación de `tests/golden/kml_normalized.txt`
- [ ] Verificar generación de `tests/golden/html_normalized.txt`
- [ ] Documentar proceso de normalización

#### **1.2 Test de Regresión E2E**
- [ ] Instalar pytest si no está disponible
- [ ] Ejecutar `pytest tests/test_e2e_regresion.py`
- [ ] Verificar que test PASS con golden actual

**Gates de Fase 1:**
- [ ] ✅ **GOLDEN PASS:** Test E2E pasa con baseline actual
- [ ] ✅ **NORMALIZE PASS:** Normalizador funciona correctamente
- [ ] ✅ **REPRODUCIBLE PASS:** Golden se puede regenerar consistentemente

---

### **FASE 2: ESQUELETO MODULAR** 🏗️

#### **2.1 Crear Estructura tz_core**
- [ ] Crear directorio `tz_core/`
- [ ] Crear `tz_core/__init__.py` (vacío por ahora)
- [ ] Crear módulos placeholder (solo docstring + pass):
  - [ ] `tz_core/utils.py`
  - [ ] `tz_core/config_manager.py`
  - [ ] `tz_core/data_loader.py`
  - [ ] `tz_core/data_validator.py`
  - [ ] `tz_core/data_processor.py`
  - [ ] `tz_core/kml_generator.py`
  - [ ] `tz_core/html_generator.py`
  - [ ] `tz_core/ui_helpers.py`

#### **2.2 Verificación de Esqueleto**
- [ ] Importar módulos sin errores: `from tz_core import utils`
- [ ] Verificar que script principal sigue funcionando
- [ ] Correr test E2E para verificar no regresión

**Gates de Fase 2:**
- [ ] ✅ **IMPORT PASS:** Todos los módulos se importan sin errores
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **STRUCTURE PASS:** Estructura de carpetas es correcta

---

### **FASE 3: EXTRACCIÓN DE UTILIDADES** 🔧

#### **3.1 Identificar Funciones Puras**
Mover funciones sin dependencias cruzadas a `tz_core/utils.py`:
- [ ] `_sha256_de_archivo`
- [ ] `_escribe_hashes_txt`
- [ ] `_compactar_ruta`
- [ ] `_sanear_nombre_archivo*`
- [ ] Funciones de normalización de texto
- [ ] Helpers de fecha/hora (si son puros)

#### **3.2 Proceso de Extracción Segura**
Para cada función:
1. [ ] **Copiar** función a `tz_core/utils.py` (mantener original)
2. [ ] **Crear test unitario** en `tests/unit/test_utils.py`
3. [ ] **Importar y usar** desde script principal
4. [ ] **Correr test E2E** para verificar no regresión
5. [ ] **Eliminar** función original del script principal
6. [ ] **Commit atómico** con un solo cambio

#### **3.3 Validación de Extracción**
- [ ] Todas las funciones extraídas tienen tests
- [ ] Cobertura de tests ≥80% para utils.py
- [ ] No hay imports circulares
- [ ] Test E2E sigue pasando

**Gates de Fase 3:**
- [ ] ✅ **UNIT PASS:** Tests unitarios de utilidades PASS
- [ ] ✅ **COVERAGE PASS:** Cobertura ≥80% en módulo utils
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **CLEAN PASS:** Código duplicado eliminado

---

### **FASE 4: GESTIÓN DE CONFIGURACIÓN** ⚙️

#### **4.1 Extraer Gestión de Config**
Mover a `tz_core/config_manager.py`:
- [ ] `bootstrap_config`
- [ ] `cargar_config`
- [ ] `cfg_build_rename_map`
- [ ] `cfg_add_user_synonym`
- [ ] `_normalize_key_for_synonyms`
- [ ] `_atomic_write_json`

#### **4.2 Crear API de Configuración**
- [ ] Clase `ConfigManager` con métodos claros
- [ ] Mantener compatibilidad con API actual
- [ ] Tests unitarios para carga/guardado de config
- [ ] Tests con archivos de config mock

#### **4.3 Integración y Validación**
- [ ] Actualizar script principal para usar `ConfigManager`
- [ ] Verificar que `config.json` se lee correctamente
- [ ] Test con config inválido (debe fallar gracefully)

**Gates de Fase 4:**
- [ ] ✅ **CONFIG PASS:** Configuración se carga sin errores
- [ ] ✅ **API PASS:** Nueva API mantiene compatibilidad
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **ERROR PASS:** Errores de config manejados correctamente

---

### **FASE 5: CARGA DE DATOS** 📂

#### **5.1 Extraer I/O de Datos**
Mover a `tz_core/data_loader.py`:
- [ ] Funciones de lectura Excel/TSV/CSV
- [ ] `_obtener_hojas_visibles`
- [ ] `_seleccionar_hoja*`
- [ ] `_listar_todas_hojas`
- [ ] Detección automática de formato

#### **5.2 Crear API de DataLoader**
- [ ] Clase `DataLoader` con métodos por tipo de archivo
- [ ] Manejo de errores específicos por formato
- [ ] Tests con archivos mock
- [ ] Validación de formatos soportados

**Gates de Fase 5:**
- [ ] ✅ **LOAD PASS:** Carga archivos de prueba sin errores
- [ ] ✅ **FORMAT PASS:** Soporta Excel, TSV, CSV
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **MOCK PASS:** Tests con archivos sintéticos PASS

---

### **FASE 6: VALIDACIÓN DE DATOS** ✅

#### **6.1 Extraer Validación y Limpieza**
Mover a `tz_core/data_validator.py`:
- [ ] `validate_schema_or_abort`
- [ ] Funciones de normalización
- [ ] `_preflight_esenciales`
- [ ] `_normalizar_fecha`
- [ ] `_normalizar_hora`
- [ ] Validaciones de esquema

#### **6.2 Crear API de DataValidator**
- [ ] Clase `DataValidator` con validaciones modulares
- [ ] Validadores específicos por tipo de dato
- [ ] Mensajes de error descriptivos
- [ ] Tests con DataFrames sintéticos

**Gates de Fase 6:**
- [ ] ✅ **VALIDATE PASS:** Valida esquemas correctamente
- [ ] ✅ **ERROR PASS:** Errores descriptivos y útiles
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **EDGE PASS:** Casos límite manejados correctamente

---

### **FASE 7: PROCESAMIENTO ANALÍTICO** 📊

#### **7.1 Extraer Lógica de Análisis**
Mover a `tz_core/data_processor.py`:
- [ ] `generar_historial_cambios_antena`
- [ ] `etiqueta_rango`
- [ ] Funciones de agregación
- [ ] Análisis de rangos horarios
- [ ] Cálculos geoespaciales

#### **7.2 Crear API de AnalysisEngine**
- [ ] Clase `AnalysisEngine` con métodos específicos
- [ ] Tests con datos controlados/deterministas
- [ ] Validación de cálculos matemáticos
- [ ] Benchmarks de performance

**Gates de Fase 7:**
- [ ] ✅ **CALC PASS:** Cálculos matemáticos correctos
- [ ] ✅ **PERF PASS:** Performance no degradada >5%
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **DETERMINISTIC PASS:** Resultados reproducibles

---

### **FASE 8: GENERACIÓN KML** 🗺️

#### **8.1 Extraer Generación KML**
Mover a `tz_core/kml_generator.py`:
- [ ] `generar_kml`
- [ ] `_crear_feature_kml`
- [ ] Helpers de geometría
- [ ] Funciones de estilo KML
- [ ] Generación de KMZ

#### **8.2 Crear API de KMLGenerator**
- [ ] Clase `KMLGenerator` con métodos específicos
- [ ] Validación de XML generado
- [ ] Tests comparando estructura KML
- [ ] Verificación con golden KMZ

**Gates de Fase 8:**
- [ ] ✅ **KML PASS:** KML válido generado
- [ ] ✅ **STRUCTURE PASS:** Estructura XML correcta
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **GEO PASS:** Datos geoespaciales correctos

---

### **FASE 9: GENERACIÓN HTML** 📄

#### **9.1 Extraer Generación HTML**
Mover a `tz_core/html_generator.py`:
- [ ] `generar_informe_html`
- [ ] `_construir_seccion_*`
- [ ] Templates y helpers HTML
- [ ] Funciones de formateo
- [ ] Generación de estilos

#### **9.2 Crear API de HTMLReportGenerator**
- [ ] Clase `HTMLReportGenerator` con secciones modulares
- [ ] Validación de HTML generado
- [ ] Tests de estructura DOM
- [ ] Verificación con golden HTML

**Gates de Fase 9:**
- [ ] ✅ **HTML PASS:** HTML válido generado
- [ ] ✅ **DOM PASS:** Estructura DOM correcta
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **STYLE PASS:** Estilos y JS funcionan

---

### **FASE 10: UI Y ORQUESTACIÓN** 🖥️

#### **10.1 Extraer Interfaz de Usuario**
Mover a `tz_core/ui_helpers.py`:
- [ ] Wizards y menús
- [ ] Funciones de input
- [ ] Selección de archivos
- [ ] Validación de entrada usuario

#### **10.2 Simplificar main()**
- [ ] Refactorizar `main()` como orquestador simple
- [ ] Usar APIs de módulos tz_core
- [ ] Mantener flujo de usuario actual
- [ ] Simplificar lógica de control

**Gates de Fase 10:**
- [ ] ✅ **UI PASS:** Interfaz funciona igual que antes
- [ ] ✅ **FLOW PASS:** Flujo de usuario sin cambios
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **SIMPLE PASS:** main() <200 líneas

---

### **FASE 11: LIMPIEZA Y ELIMINACIÓN LEGACY** 🧹

#### **11.1 Eliminar Código Duplicado**
- [ ] Buscar y eliminar funciones duplicadas
- [ ] Consolidar imports
- [ ] Eliminar código comentado/muerto
- [ ] Limpiar variables globales innecesarias

#### **11.2 Optimización de Imports**
- [ ] Reorganizar imports por módulo
- [ ] Eliminar imports no utilizados
- [ ] Verificar que no hay imports circulares
- [ ] Optimizar tiempo de carga

**Gates de Fase 11:**
- [ ] ✅ **CLEAN PASS:** Sin código duplicado
- [ ] ✅ **IMPORT PASS:** Imports optimizados
- [ ] ✅ **GOLDEN PASS:** Test E2E sigue pasando
- [ ] ✅ **SIZE PASS:** Archivo principal <1000 líneas

---

### **FASE 12: QUALITY GATES Y LINTING** 🔍

#### **12.1 Configurar Herramientas de Calidad**
- [ ] Configurar flake8 con reglas del proyecto
- [ ] Configurar black para formateo automático
- [ ] Configurar pytest para cobertura
- [ ] Crear pre-commit hooks

#### **12.2 Aplicar Estándares**
- [ ] Correr linting en todo el código
- [ ] Aplicar formateo automático
- [ ] Medir cobertura de tests
- [ ] Generar reporte de calidad

**Gates de Fase 12:**
- [ ] ✅ **LINT PASS:** Sin errores críticos de linting
- [ ] ✅ **FORMAT PASS:** Código formateado consistentemente
- [ ] ✅ **COVERAGE PASS:** Cobertura ≥80%
- [ ] ✅ **QUALITY PASS:** Métricas de calidad OK

---

### **FASE 13: DOCUMENTACIÓN Y ROLLBACK** 📚

#### **13.1 Documentación Técnica**
- [ ] README de arquitectura
- [ ] Documentación de APIs
- [ ] Guía de contribución
- [ ] Diagramas de flujo actualizados

#### **13.2 Plan de Rollback**
- [ ] Crear script de rollback automático
- [ ] Documentar proceso de reversión
- [ ] Tag de versión post-refactor
- [ ] Instrucciones de troubleshooting

**Gates de Fase 13:**
- [ ] ✅ **DOCS PASS:** Documentación completa y actualizada
- [ ] ✅ **ROLLBACK PASS:** Plan de rollback probado
- [ ] ✅ **VERSION PASS:** Versionado correcto aplicado

---

### **FASE 14: VALIDACIÓN FINAL** 🎯

#### **14.1 Tests Exhaustivos**
- [ ] Ejecutar suite completa de tests
- [ ] Performance benchmarking
- [ ] Tests con datasets reales grandes
- [ ] Validación en diferentes entornos

#### **14.2 Smoke Testing**
- [ ] Ejecución end-to-end con datos reales
- [ ] Validación de outputs generados
- [ ] Verificación de todas las funcionalidades
- [ ] Comparación con versión pre-refactor

**Gates de Fase 14:**
- [ ] ✅ **COMPREHENSIVE PASS:** Todos los tests PASS
- [ ] ✅ **PERF PASS:** Performance igual o mejor
- [ ] ✅ **REAL PASS:** Funciona con datos reales
- [ ] ✅ **FEATURE PASS:** Todas las features funcionan

---

### **FASE 15: RELEASE Y CIERRE** 🚀

#### **15.1 Release Final**
- [ ] Tag de versión v2.0
- [ ] Changelog completo
- [ ] Release notes
- [ ] Backup de versión v1.0

#### **15.2 Cierre y Retrospectiva**
- [ ] Documentar lecciones aprendidas
- [ ] Actualizar metodología para futuros proyectos
- [ ] Celebrar el éxito 🎉

**Gates de Fase 15:**
- [ ] ✅ **RELEASE PASS:** Versión 2.0 lista para producción
- [ ] ✅ **BACKUP PASS:** Versión 1.0 respaldada
- [ ] ✅ **DOCS PASS:** Documentación de release completa

---

## 🚦 PROTOCOLO DE GATES

### **Gate de Entrada (Pre-fase)**
Antes de empezar cualquier fase:
1. ✅ **Commit limpio:** Working directory clean
2. ✅ **Tests baseline:** Golden test PASS
3. ✅ **Environment check:** Dependencias OK
4. ✅ **Backup point:** Tag de respaldo creado

### **Gate Intermedio (Durante fase)**
Después de cada cambio significativo:
1. ✅ **Build check:** Código compila sin errores
2. ✅ **Quick test:** Tests relacionados PASS
3. ✅ **Lint check:** Sin errores críticos
4. ✅ **Smoke test:** Funcionalidad básica OK

### **Gate de Salida (Post-fase)**
Antes de marcar fase como completa:
1. ✅ **Full test suite:** Todos los tests PASS
2. ✅ **Golden verification:** Test E2E PASS
3. ✅ **Documentation:** Cambios documentados
4. ✅ **Performance:** Sin degradación >5%
5. ✅ **Rollback ready:** Plan de reversión probado

### **Gate de Emergencia (Si algo falla)**
1. 🛑 **STOP:** Detener trabajo inmediatamente
2. 📊 **Assess:** Evaluar impacto del fallo
3. 🔄 **Revert:** Git reset/stash al último punto bueno
4. 🔍 **Analyze:** Entender causa raíz
5. 📝 **Plan:** Actualizar estrategia antes de continuar

---

## 📊 DASHBOARD DE PROGRESO

### **Estado General**
```
🎯 TZ Analyzer Refactorización - Dashboard en Tiempo Real

📅 Iniciado: 2025-10-24
🎯 Meta: Arquitectura modular de clase mundial
📊 Progreso: 0/15 fases completadas (0%)

┌─────────────────────────────────────────────────────────┐
│                    PROGRESO POR FASE                   │
├─────────────────────────────────────────────────────────┤
│ [ ] Fase 0: Preparación ⚪                             │
│ [ ] Fase 1: Baseline dorado ⚪                         │
│ [ ] Fase 2: Esqueleto modular ⚪                       │
│ [ ] Fase 3: Utilidades ⚪                              │
│ [ ] Fase 4: Configuración ⚪                           │
│ [ ] Fase 5: Carga de datos ⚪                          │
│ [ ] Fase 6: Validación ⚪                              │
│ [ ] Fase 7: Procesamiento ⚪                           │
│ [ ] Fase 8: Generación KML ⚪                          │
│ [ ] Fase 9: Generación HTML ⚪                         │
│ [ ] Fase 10: UI y orquestación ⚪                      │
│ [ ] Fase 11: Limpieza ⚪                               │
│ [ ] Fase 12: Quality gates ⚪                          │
│ [ ] Fase 13: Documentación ⚪                          │
│ [ ] Fase 14: Validación final ⚪                       │
│ [ ] Fase 15: Release ⚪                                │
└─────────────────────────────────────────────────────────┘
```

### **Métricas de Calidad**
```
┌─────────────────────────────────────────────────────────┐
│                   MÉTRICAS ACTUALES                    │
├─────────────────────────────────────────────────────────┤
│ 🧪 Cobertura Tests: -%                                 │
│ 🚨 Lint Score: -/10                                    │
│ ⚡ Performance: -%                                      │
│ 📏 Líneas script principal: 7,680                      │
│ 🔗 Módulos extraídos: 0/8                              │
│ 📊 Complejidad: No medida                              │
│ 🎯 Gates pasados: 0                                    │
└─────────────────────────────────────────────────────────┘
```

### **Estado de Gates Críticos**
```
┌─────────────────────────────────────────────────────────┐
│                  GATES CRÍTICOS                        │
├─────────────────────────────────────────────────────────┤
│ ⚪ BUILD PASS: No evaluado                              │
│ ⚪ GOLDEN PASS: No evaluado                             │
│ ⚪ LINT PASS: No evaluado                               │
│ ⚪ COVERAGE PASS: No evaluado                           │
│ ⚪ PERF PASS: No evaluado                               │
└─────────────────────────────────────────────────────────┘
```

---

## 📚 REFERENCIAS Y RECURSOS

### **Documentos del Proyecto**
- [Biblia de Desarrollo v2.0](./PRINCIPIOS_DESARROLLO_PROFESIONAL.md)
- [Plan Maestro de Refactorización](./PLAN_MAESTRO_REFACTORIZACION.md) (este documento)

### **Scripts y Herramientas**
- Golden baseline: `python -m tests.update_golden`
- Test regresión: `pytest tests/test_e2e_regresion.py`
- Linting: `flake8 script_principal_bitacoras_refactory.py`
- Formateo: `black script_principal_bitacoras_refactory.py`

### **Comandos Git Útiles**
```bash
# Crear rama de refactor
git checkout -b refactor/modular-architecture

# Tag pre-refactor
git tag v1.0-pre-refactor

# Rollback de emergencia
git reset --hard v1.0-pre-refactor

# Ver cambios desde inicio de refactor
git diff v1.0-pre-refactor..HEAD
```

---

## 🎬 SIGUIENTE PASO

**ACCIÓN INMEDIATA:** Ejecutar Fase 0 (Preparación y Seguridad)

1. [ ] Crear rama `refactor/modular-architecture`
2. [ ] Crear tag `v1.0-pre-refactor`
3. [ ] Verificar que script actual funciona
4. [ ] Validar entorno Python

**COMANDO PARA EMPEZAR:**
```bash
git checkout -b refactor/modular-architecture
git tag v1.0-pre-refactor
python script_principal_bitacoras_refactory.py --help
```

¿Estás listo para empezar la transformación? 🚀

---

**Documento vivo - Se actualiza con cada fase completada**  
**Última actualización:** 24 de octubre de 2025  
**Próxima revisión:** Después de cada fase completada