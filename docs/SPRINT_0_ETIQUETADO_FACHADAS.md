# SPRINT 0: ETIQUETADO Y FACHADAS - ARQUITECTURA MODULAR COMPLETA
## TZ-Analyzer v1.1.0-modular_cut - Preparación

### 🎯 **OBJETIVO SPRINT 0**

Preparar la arquitectura híbrida existente para modularización completa según el diagrama objetivo, mediante:
1. ✅ Etiquetado sistemático de funciones con packages destino
2. ✅ Creación de fachadas limpias como puntos de entrada únicos
3. ✅ Planificación detallada de 4 sprints de extracción
4. ✅ Validación de compatibilidad 100%

### 📋 **INVENTARIO DE FUNCIONES ETIQUETADAS**

#### 🎯 **tz_kml/ - Generación KML/KMZ**
```python
# pkg: tz_kml
# layer: core
# TODO extract → tz_kml/generator.py (Sprint 2)
generar_kml()                    # 141 líneas - función principal KML

# pkg: tz_kml  
# layer: core
# TODO extract → tz_kml/feature_creator.py (Sprint 2)
_crear_feature_kml()             # ~50 líneas - creación de features
```

#### 🔧 **tz_services/ - Servicios Core**
```python
# pkg: tz_services
# layer: core  
# TODO extract → tz_services/dataframe_tools.py (Sprint 1)
_dedupe_columns()                # Deduplicación de columnas

# pkg: tz_services
# layer: presentation
# TODO extract → tz_services/report_generator.py (Sprint 1)  
generar_informe_html()           # 199 líneas - generación HTML

# pkg: tz_services
# layer: validation
# TODO extract → tz_services/data_validator.py (Sprint 1)
validar_columnas()               # Validación fallback
validar_datos()                  # Validación core
```

#### 💾 **tz_io/ - Input/Output Operations**
```python
# pkg: tz_io
# layer: io
# TODO extract → tz_io/hash_utils.py (Sprint 1)
_escribe_hashes_txt()            # Generación de hashes

# pkg: tz_io
# layer: io
# TODO extract → tz_io/branding_utils.py (Sprint 1)  
_copiar_logo_a_salida()          # Copiado de branding
```

#### 🖥️ **tz_cli/ - Interfaz y Orquestación**
```python
# pkg: tz_cli
# layer: orchestration
# TODO extract → tz_cli/main_menu.py (Sprint 3)
main()                           # 72 líneas - menú principal

# pkg: tz_cli
# layer: ui
# TODO extract → tz_cli/wizard_mapper.py (Sprint 4 - ZONA PELIGROSA)
_wizard_qc_mapeo()               # ⚡ 382 líneas - RIESGO EXTREMO
```

### 🎭 **FACHADAS CREADAS (PUNTOS DE ENTRADA ÚNICOS)**

#### 1. **`build_kml(df, cfg, out_dir, flat=False)`**
- **Destino:** tz_kml package (Sprint 2)
- **Función:** Punto de entrada único para generación KML/KMZ
- **Implementación actual:** Llama internamente a `generar_kml()`

#### 2. **`generate_html(df, cfg, out_dir, kml_file, ...)`**
- **Destino:** tz_services package (Sprint 1)  
- **Función:** Punto de entrada único para reportes HTML
- **Implementación actual:** Llama internamente a `generar_informe_html()`

#### 3. **`hash_outputs(out_dir)`**
- **Destino:** tz_io package (Sprint 1)
- **Función:** Punto de entrada único para hashing
- **Implementación actual:** Llama internamente a `_escribe_hashes_txt()`

#### 4. **`dedupe_columns(df)`**  
- **Destino:** tz_services package (Sprint 1)
- **Función:** Punto de entrada único para deduplicación
- **Implementación actual:** Llama internamente a `_dedupe_columns()`

#### 5. **`run_cli()`**
- **Destino:** tz_cli package (Sprint 3)
- **Función:** Punto de entrada único para interfaz CLI
- **Implementación actual:** Llama internamente a `main()`

### 🗓️ **ROADMAP DE 4 SPRINTS**

#### **📦 SPRINT 1: Servicios y I/O (PRIORIDAD ALTA)**
**Objetivo:** Extraer funciones de servicios básicos y I/O
**Duración estimada:** 2-3 días
**Funciones objetivo:**
- ✅ `_dedupe_columns()` → `tz_services/dataframe_tools.py`
- ✅ `generar_informe_html()` → `tz_services/report_generator.py`  
- ✅ `_escribe_hashes_txt()` → `tz_io/hash_utils.py`
- ✅ `_copiar_logo_a_salida()` → `tz_io/branding_utils.py`
- ✅ Validadores fallback → `tz_services/data_validator.py`

**Beneficio:** ~280 líneas extraídas (-3.8%)

#### **🗺️ SPRINT 2: Generación KML (PRIORIDAD ALTA)**
**Objetivo:** Extraer todo el subsistema KML/KMZ
**Duración estimada:** 3-4 días  
**Funciones objetivo:**
- ✅ `generar_kml()` (141 líneas) → `tz_kml/generator.py`
- ✅ `_crear_feature_kml()` → `tz_kml/feature_creator.py`
- ✅ Funciones de estilos KML → `tz_kml/styles.py`

**Beneficio:** ~200 líneas extraídas (-2.7%)

#### **🖥️ SPRINT 3: CLI y Orquestación (PRIORIDAD MEDIA)**
**Objetivo:** Extraer interfaz de usuario y menús
**Duración estimada:** 2-3 días
**Funciones objetivo:**
- ✅ `main()` (72 líneas) → `tz_cli/main_menu.py`
- ✅ Funciones de selección → `tz_cli/input_handlers.py`
- ✅ Orquestación de flujos → `tz_cli/orchestrator.py`

**Beneficio:** ~120 líneas extraídas (-1.6%)

#### **⚡ SPRINT 4: Wizard QC (ZONA PELIGROSA)**
**Objetivo:** Extraer el wizard de mapeo con máxima precaución
**Duración estimada:** 4-5 días (incluye testing exhaustivo)
**Funciones objetivo:**
- ⚠️ `_wizard_qc_mapeo()` (382 líneas) → `tz_cli/wizard_mapper.py`
- ⚠️ **REQUIERE PROTOCOLO ESPECIAL DE VALIDACIÓN**
- ⚠️ **MÚLTIPLES CHECKPOINTS DE TESTING**

**Beneficio:** ~400 líneas extraídas (-5.4%)

### 📊 **IMPACTO TOTAL PROYECTADO**

| **Sprint** | **Líneas Extraídas** | **Reducción %** | **Monolito Resultante** |
|------------|---------------------|-----------------|-------------------------|
| **Sprint 1** | ~280 | -3.8% | ~7,075 líneas |
| **Sprint 2** | ~200 | -2.7% | ~6,875 líneas |  
| **Sprint 3** | ~120 | -1.6% | ~6,755 líneas |
| **Sprint 4** | ~400 | -5.4% | ~6,355 líneas |
| **TOTAL** | **~1,000** | **-13.5%** | **~6,355 líneas** |

**Reducción acumulada desde origen:** ~47% (12,000 → 6,355 líneas estimadas)

### 🛡️ **PROTOCOLO DE VALIDACIÓN**

Para cada sprint se aplicará la metodología 4-subfases probada:

#### **Subfase A: Análisis Pre-Extracción**
- 🔍 Mapeo de dependencias exactas
- 📋 Identificación de imports necesarios  
- 🎯 Determinación de tests específicos

#### **Subfase B: Extracción Controlada**
- 📦 Creación de módulo destino
- 🔧 Movimiento de código con preservación exacta
- 🔗 Actualización de fachada para usar módulo

#### **Subfase C: Validación Exhaustiva**
- 🧪 **7-test suite:** Import, función, wrapper, integración, casos edge
- ✅ Verificación de cero regresiones
- 🔄 Compatibilidad perfecta confirmada

#### **Subfase D: Documentación y Commit**
- 📚 Documentación de cambios
- 💾 Commit con mensaje detallado
- 🎯 Actualización de este roadmap

### 🎯 **ESTADO ACTUAL POST-SPRINT 0**

✅ **ETIQUETADO COMPLETADO:** 15+ funciones marcadas con packages destino  
✅ **FACHADAS CREADAS:** 5 puntos de entrada únicos implementados  
✅ **ROADMAP DEFINIDO:** 4 sprints planificados con métricas claras  
✅ **COMPATIBILIDAD:** 100% preservada - sistema funcional  
✅ **PREPARACIÓN:** Lista para iniciar Sprint 1  

### 🚀 **PRÓXIMO PASO**

**Iniciar Sprint 1** con extracción de:
1. `_dedupe_columns()` → `tz_services/dataframe_tools.py`
2. Validación con 7-test suite
3. Actualización de fachada `dedupe_columns()`

---

**Documento generado:** Sprint 0 - 29 de octubre de 2025  
**Estado:** ✅ PREPARACIÓN COMPLETADA  
**Siguiente objetivo:** Sprint 1 - Servicios y I/O