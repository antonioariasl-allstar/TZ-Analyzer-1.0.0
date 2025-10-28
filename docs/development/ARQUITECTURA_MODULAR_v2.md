# 🏗️ DIAGNÓSTICO ARQUITECTURAL PROFUNDO v2.0
## ESTRUCTURA DE MÓDULOS ESCALABLE Y FUTURO-PROOF

**Fecha:** 27 octubre 2025  
**Análisis base:** 58 funciones, 61 conexiones, 14 puntos entrada  

---

## 🎯 ARQUITECTURA OBJETIVO

### **Estructura Modular Propuesta**

```
tz_analyzer/                          # Paquete principal
├── __init__.py                       # API pública
├── cli/                              # Interfaz línea de comandos
│   ├── __init__.py
│   ├── main.py                       # main() + run_tz_analysis()
│   └── interactive.py                # _modo_manual() + UI
├── core/                             # Núcleo ya existente (expandir)
│   ├── __init__.py
│   ├── config.py                     # Configuración y sinónimos
│   ├── logging.py                    # Sistema de logging unificado
│   └── exceptions.py                 # Excepciones personalizadas
├── data/                             # Manejo de datos
│   ├── __init__.py
│   ├── loaders.py                    # Carga Excel/CSV
│   ├── validation.py                 # Validaciones de datos
│   ├── normalization.py              # Limpieza y normalización
│   └── transforms.py                 # Transformaciones de datos
├── utils/                            # Utilidades generales
│   ├── __init__.py
│   ├── files.py                      # E/S archivos + hashing
│   ├── text.py                       # Procesamiento texto
│   ├── time.py                       # Manejo temporal
│   └── geo.py                        # Cálculos geográficos
├── services/                         # Lógica de negocio
│   ├── __init__.py
│   ├── kml_generator.py              # Generación KML/KMZ
│   ├── html_generator.py             # Generación HTML
│   ├── analyzer.py                   # Análisis de antenas
│   └── filtering.py                  # Filtros temporales
└── extensions/                       # Para futuras expansiones
    ├── __init__.py
    ├── plugins/                      # Sistema de plugins
    ├── formats/                      # Nuevos formatos export
    └── integrations/                 # APIs externas
```

---

## 📊 ANÁLISIS DE DEPENDENCIAS POR MÓDULO

### **🟢 RIESGO MÍNIMO** (Extraer primero)

#### **`utils/files.py`** (5 funciones)
```python
# Funciones puras sin dependencias
- _sha256_de_archivo()           # deps: 1 | calls: 0
- _escribe_hashes_txt()          # deps: 1 | calls: 1  
- _copiar_logo_a_salida()        # deps: 1 | calls: 0
- _compactar_ruta()              # deps: 0 | calls: 2
- _atomic_write_json()           # deps: 0 | calls: 0 (HUÉRFANA)
```
**Riesgo:** 1/10 - Funciones utilitarias puras  
**Dependencias:** Solo bibliotecas estándar  
**Tiempo estimado:** 1-2 días  

#### **`utils/geo.py`** (3 funciones)  
```python
# Matemáticas puras geográficas
- grados_a_radianes()            # deps: 1 | calls: 0
- calcular_punto_final()         # deps: 2 | calls: 1
- generar_cono()                 # deps: 0 | calls: 1
```
**Riesgo:** 1/10 - Cálculos matemáticos deterministas  
**Dependencias:** Solo math/numpy  
**Tiempo estimado:** 1 día  

#### **`utils/text.py`** (6 funciones)
```python
# Utilidades de texto y normalización básica
- _tiene_valor()                 # deps: 2 | calls: 0
- _a_float()                     # deps: 1 | calls: 0
- _formatear_valor_para_burbuja() # deps: 2 | calls: 1
- _armar_descripcion_compacta()  # deps: 1 | calls: 2
- _fix_mojibake_text()           # deps: 1 | calls: 0
- _aplicar_reemplazos_regex()    # deps: 1 | calls: 0
```
**Riesgo:** 2/10 - Algunas interdependencias  
**Dependencias:** re, unicodedata  
**Tiempo estimado:** 2 días  

### **🟡 RIESGO BAJO-MEDIO** (Segunda ola)

#### **`utils/time.py`** (6 funciones)
```python
# Manejo temporal especializado
- _hhmmss_to_time_or_none()      # deps: 1 | calls: 0
- _parse_hhmmss_to_minutes()     # deps: 2 | calls: 0  
- _en_rango()                    # deps: 3 | calls: 0 ⚠️
- _clasificar_rango_sv()         # deps: 1 | calls: 2
- _minutes_from_any()            # deps: 1 | calls: 1
- etiqueta_rango()               # deps: 0 | calls: 3
```
**Riesgo:** 3/10 - `_en_rango` tiene 3 dependientes  
**Dependencias:** datetime, pandas  
**Tiempo estimado:** 2-3 días  

#### **`data/normalization.py`** (4 funciones)
```python
# Normalización de datos
- normalizar_texto()             # deps: 1 | calls: 2
- normalizar_columnas_texto()    # deps: 1 | calls: 1  
- _dedupe_columns()              # deps: 1 | calls: 0
- compactar_nombre_antena_kml()  # deps: 1 | calls: 0
```
**Riesgo:** 4/10 - Usado por varios módulos  
**Dependencias:** utils/text  
**Tiempo estimado:** 3 días  

#### **`data/validation.py`** (3 funciones)
```python
# Validaciones de datos
- _wizard_qc_mapeo()             # deps: 1 | calls: 0
- _preflight_esenciales()        # deps: 0 | calls: 0 (HUÉRFANA)
- validar_datos()                # Importada externa
```
**Riesgo:** 3/10 - Relativamente independiente  
**Dependencias:** pandas, data/normalization  
**Tiempo estimado:** 2-3 días  

### **🟠 RIESGO MEDIO-ALTO** (Tercera ola)

#### **`data/loaders.py`** (8 funciones)
```python
# Carga y procesamiento de archivos
- _cargar_excel_con_normalizacion() # deps: 1 | calls: 0
- _seleccionar_hoja_visible()       # deps: 1 | calls: 0
- _obtener_hojas_visibles()         # deps: 0 | calls: 0 (HUÉRFANA)
- _listar_todas_hojas()             # deps: 0 | calls: 0 (HUÉRFANA)
- _seleccionar_hoja()               # deps: 0 | calls: 0 (HUÉRFANA)
- _normalizar_fecha()               # deps: 0 | calls: 0 (HUÉRFANA)
- _normalizar_hora()                # deps: 0 | calls: 0 (HUÉRFANA)
- _es_num()                         # deps: 0 | calls: 0 (HUÉRFANA)
```
**Riesgo:** 5/10 - Muchas funciones huérfanas a limpiar  
**Dependencias:** pandas, data/normalization, data/validation  
**Tiempo estimado:** 4-5 días  

#### **`core/config.py`** (6 funciones)
```python
# Sistema de configuración crítico
- cfg_build_rename_map()         # deps: 2 | calls: 0 ⚠️
- bootstrap_config()             # deps: 1 | calls: 2
- cargar_config()                # deps: 1 | calls: 0
- _normalize_key_for_synonyms()  # deps: 1 | calls: 0
- cfg_add_user_synonym()         # deps: 1 | calls: 0
- get_config()                   # deps: 1 | calls: 0
```
**Riesgo:** 6/10 - Sistema crítico de configuración  
**Dependencias:** tz_core.config_manager (ya existe)  
**Tiempo estimado:** 3-4 días  

### **🔴 RIESGO ALTO** (Cuarta ola - con extrema cautela)

#### **`services/analyzer.py`** (2 funciones)
```python
# Análisis de datos especializados
- generar_historial_cambios_antena() # deps: 1 | calls: 1
- analizar_antenas()                 # deps: 0 | calls: 0 (HUÉRFANA)
```
**Riesgo:** 4/10 - Una función huérfana  
**Dependencias:** pandas, utils/time  
**Tiempo estimado:** 3 días  

#### **`cli/interactive.py`** (7 funciones)
```python
# Interfaz usuario interactiva
- _solicitar_color_tema()        # deps: 2 | calls: 0 ⚠️
- _solicitar_filtros_tiempo()    # deps: 2 | calls: 0 ⚠️
- _modo_manual()                 # deps: 1 | calls: 4
- _solicitar_overrides_topn()    # deps: 1 | calls: 0
- seleccionar_archivo()          # deps: 1 | calls: 0
- seleccionar_carpeta()          # deps: 1 | calls: 0
- mostrar_estadisticas()         # deps: 1 | calls: 0
```
**Riesgo:** 7/10 - UI compleja con estado  
**Dependencias:** core/config, utils/*  
**Tiempo estimado:** 5-6 días  

### **🚫 RIESGO CRÍTICO** (Última ola - máxima cautela)

#### **`services/kml_generator.py`** (3 funciones)
```python
# Generación KML crítica
- generar_kml()                  # deps: 2 | calls: 5 🔴 NUDO CRÍTICO
- _crear_feature_kml()           # deps: 1 | calls: 2
- _hex_to_kml_color()            # deps: 1 | calls: 0
```
**Riesgo:** 9/10 - `generar_kml` es NUDO CRÍTICO  
**Dependencias:** Todo el sistema  
**Tiempo estimado:** 7-10 días  

#### **`services/html_generator.py`** (3 funciones)
```python
# Generación HTML crítica  
- generar_informe_html()         # deps: 1 | calls: 2
- _construir_seccion_interacciones() # deps: 1 | calls: 1
- _construir_seccion_todos_contactos() # deps: 1 | calls: 0
```
**Riesgo:** 8/10 - Sistema complejo de reportes  
**Dependencias:** Todo el sistema  
**Tiempo estimado:** 6-8 días  

#### **`cli/main.py`** (2 funciones)
```python
# NUNCA MOVER - núcleo de orquestación
- main()                         # deps: 3 | calls:20 🔴 NUDO CRÍTICO  
- run_tz_analysis()              # deps: 0 | calls: 1
```
**Riesgo:** 10/10 - MANTENER EN MONOLITO  
**Razón:** Punto de entrada crítico  

---

## 🚀 FUNCIONES HUÉRFANAS A LIMPIAR PRIMERO

**10 funciones candidatas a eliminar:**
```
- _atomic_write_json (wrapper vacío)
- _es_num (sin uso)  
- _listar_todas_hojas (sin uso)
- _normalizar_fecha (sin uso)
- _normalizar_hora (sin uso)
- _obtener_hojas_visibles (sin uso)
- _pad_hhmmss (sin uso)
- _preflight_esenciales (sin uso)
- _seleccionar_hoja (sin uso)
- analizar_antenas (sin uso)
```

---

## 🛡️ ESTRATEGIA DE MIGRACIÓN SEGURA

### **FASE 2A: Limpieza (1 semana)**
1. Eliminar 10 funciones huérfanas
2. Crear estructura de carpetas
3. Setup tests de regresión

### **FASE 2B: Utilidades (2 semanas)**
1. `utils/files.py` (5 funciones)
2. `utils/geo.py` (3 funciones)  
3. `utils/text.py` (6 funciones)

### **FASE 2C: Datos (3 semanas)**
1. `utils/time.py` (6 funciones)
2. `data/normalization.py` (4 funciones)
3. `data/validation.py` (3 funciones)
4. `data/loaders.py` (8 funciones)

### **FASE 2D: Core (2 semanas)**
1. `core/config.py` (6 funciones)
2. `services/analyzer.py` (2 funciones)

### **FASE 2E: Interfaz (3 semanas)**
1. `cli/interactive.py` (7 funciones)

### **FASE 2F: Servicios Críticos (4 semanas)**
1. `services/html_generator.py` (3 funciones)
2. `services/kml_generator.py` (3 funciones)

**TOTAL ESTIMADO:** ~15 semanas (3-4 meses) con máxima cautela

---

## 🔮 ESCALABILIDAD FUTURA

### **`extensions/plugins/`** - Sistema de Plugins
```python
# Para futuras funcionalidades
- custom_analyzers/              # Análisis personalizados
- export_formats/                # PDF, Excel, CSV exports
- data_sources/                  # APIs, bases de datos
- visualization/                 # Gráficos avanzados
```

### **`extensions/integrations/`** - Integraciones
```python
# APIs y servicios externos
- google_maps/                   # Geocodificación
- databases/                     # PostgreSQL, MongoDB
- cloud_storage/                 # AWS S3, Google Drive
- reporting/                     # Power BI, Tableau
```

### **`extensions/formats/`** - Nuevos Formatos
```python
# Soporte futuro para más formatos
- geojson/                       # GeoJSON export
- shapefile/                     # ESRI Shapefile
- gpx/                           # GPS Exchange Format
- json_reports/                  # JSON estructurado
```

---

## ✅ CRITERIOS DE VALIDACIÓN

### **Por cada módulo extraído:**
1. ✅ 46+ tests siguen pasando
2. ✅ CI green (análisis estático)  
3. ✅ Performance sin degradación
4. ✅ API backwards compatible
5. ✅ Documentación actualizada
6. ✅ Imports limpios y explícitos

### **Métricas de éxito:**
- **Cobertura de tests:** >95% por módulo
- **Complejidad ciclomática:** <10 por función
- **Acoplamiento:** Minimal dependencies
- **Cohesión:** Single responsibility per module

---

**🎯 OBJETIVO:** Arquitectura modular, testeable, mantenible y preparada para escalar durante los próximos 5+ años.**