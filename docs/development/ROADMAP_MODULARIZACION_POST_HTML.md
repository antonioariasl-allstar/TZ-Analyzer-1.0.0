# 🗺️ ROADMAP DE MODULARIZACIÓN POST-HTML EPIC
## TZ-Analyzer 1.0.0 - Próximas Fases de Extracción

**Fecha:** 28 de octubre de 2025  
**Contexto:** Análisis estratégico tras completar HTML Generator Epic  
**Estado del monolito:** 7,987 líneas (reducción de 252 líneas)  
**Framework modular:** 15 módulos activos en tz_core/

---

## 🎯 **OBJETIVO ESTRATÉGICO**

Continuar la modularización sistemática del monolito `script_principal_bitacoras_refactory.py` siguiendo la metodología exitosa demostrada en el HTML Generator Epic.

---

## 📊 **INVENTARIO DE FUNCIONES DEL MONOLITO**

### 🔍 **ANÁLISIS COMPLETO: 50 FUNCIONES IDENTIFICADAS**

**Funciones por categoría de riesgo:**

#### 🟢 **RIESGO BAJO** (14 funciones - candidatas inmediatas)
```python
# Normalización y validación de datos
_normalizar_fecha()         # ~25 líneas - Maneja serial Excel + ISO
_normalizar_hora()          # ~20 líneas - Formatos HH:MM:SS robustos  
normalizar_texto()          # ~15 líneas - Limpieza mojibake/unicode
normalizar_columnas_texto() # ~16 líneas - Aplicación masiva

# Validadores y utilidades simples
_tiene_valor()              # ~6 líneas - Validación de existencia
_es_num()                   # ~6 líneas - Detección numérica
_a_float()                  # ~6 líneas - Conversión segura
log()                       # ~5 líneas - Sistema de logging

# Helpers de formato y color
_hex_to_kml_color()         # ~8 líneas - Conversión HEX→ABGR
_formatear_valor_para_burbuja() # ~6 líneas - Formateo KML
_fix_mojibake_text()        # ~33 líneas - Limpieza de encoding
_aplicar_reemplazos_regex() # ~8 líneas - Sustituciones texto

# Utilidades de archivos
_escribe_hashes_txt()       # ~3 líneas - Generación checksums
_copiar_logo_a_salida()     # ~9 líneas - Gestión assets
```

#### 🟡 **RIESGO MEDIO** (22 funciones - requieren planificación)
```python
# Análisis de datos y reportes
analizar_antenas()                      # ~76 líneas - Reportes de antenas
generar_historial_cambios_antena()      # ~117 líneas - Tracking movimiento
_construir_seccion_interacciones()      # ~11 líneas preview - Secciones HTML
_construir_seccion_todos_contactos()    # ~9 líneas preview - Tablas contactos

# Sistema de configuración (PARCIALMENTE MODULARIZADO)
bootstrap_config()                      # ~55 líneas - ⚠️ CRÍTICO - Init global
cfg_build_rename_map()                  # ~30 líneas - Mapeo sinónimos  
cfg_add_user_synonym()                  # ~15 líneas - Gestión sinónimos
cargar_config()                         # ~11 líneas - Carga configuración
get_config()                            # ~25 líneas - Acceso configuración

# KML duplicados (consolidación pendiente)
_crear_feature_kml()                    # 2 versiones - ⚠️ DUPLICADO
generar_kml()                           # ~100+ líneas - vs generar_kml_puntos_libres

# Manejo de datos Excel
_cargar_excel_con_normalizacion()       # ~20 líneas - Carga con metadatos
_seleccionar_hoja_visible()             # ~6 líneas - Selección hojas
_dedupe_columns()                       # ~54 líneas - Limpieza columnas

# Funciones de tiempo y filtros
_hhmmss_to_time_or_none()              # ~6 líneas - Conversión horaria
_en_rango()                            # ~6 líneas - Validación rangos
_clasificar_rango_sv()                 # ~6 líneas - Clasificación El Salvador
_aplicar_filtros_tiempo()              # ~9 líneas - Filtrado temporal
etiqueta_rango()                       # Variable - Etiquetado horario

# UI y selección
_solicitar_color_tema()                # ~11 líneas - Selección paleta
_solicitar_filtros_tiempo()            # ~5 líneas - Input filtros
_solicitar_overrides_topn()            # ~7 líneas - Override configuración
```

#### 🔴 **RIESGO ALTO** (14 funciones - diferir hasta fases avanzadas)
```python
# ZONA PROHIBIDA - NO TOCAR
_wizard_qc_mapeo()          # 382 líneas - ⚠️ PELIGRO EXTREMO
main()                      # ~6 líneas - Orquestador principal
_modo_manual()              # ~9 líneas - Modo interactivo

# Funciones con dependencias complejas (11 funciones restantes)
# Análisis detallado pendiente para clasificación específica
```

---

## 🛣️ **ROADMAP DE EXTRACCIÓN SECUENCIAL**

### **FASE 9A: Normalización y Validación** (1-2 días)
**Riesgo:** 🟢 Bajo | **Prioridad:** Inmediata

#### Módulos objetivo:
```python
tz_core/data_normalizer.py     # Normalización de datos
├── _normalizar_fecha()
├── _normalizar_hora()  
├── normalizar_texto()
└── normalizar_columnas_texto()

tz_core/validation_utils.py    # Validadores simples
├── _tiene_valor()
├── _es_num()
├── _a_float()
└── helpers relacionados

tz_core/logging_utils.py       # Sistema de logging
└── log() + configuración
```

#### ✅ **Beneficios:**
- Reducción ~100 líneas del monolito
- Funciones autónomas sin dependencias críticas
- Base sólida para extracciones posteriores
- Testing directo y sencillo

### **FASE 9B: Analytics y Reportes** (2-3 días)  
**Riesgo:** 🟡 Medio | **Prioridad:** Alta

#### Módulos objetivo:
```python
tz_core/analytics.py           # Análisis de datos
├── analizar_antenas()
├── generar_historial_cambios_antena()
└── funciones estadísticas

tz_core/report_builder.py      # Construcción de secciones
├── _construir_seccion_interacciones()
├── _construir_seccion_todos_contactos()
└── helpers de secciones HTML
```

#### ⚠️ **Consideraciones:**
- Testing con datos reales requerido
- Validación de formatos de salida
- Compatibilidad con HTML generators existentes

### **FASE 10: Consolidación KML** (3-5 días)
**Riesgo:** 🟡 Medio-Alto | **Prioridad:** Media

#### Objetivos:
1. **Resolver duplicación `_crear_feature_kml`**
   - Versión en monolito vs kml_generador.py
   - Identificar diferencias funcionales
   - Consolidar en versión única

2. **Unificar generadores KML**
   - `generar_kml()` (monolito) vs `generar_kml_puntos_libres()` (módulo)
   - Migrar a `tz_core/kml_generator.py` (ya existe como esqueleto)

#### ⚠️ **Riesgos:**
- Posibles breaking changes en formatos KML
- Compatibilidad con configuraciones existentes
- Testing exhaustivo con Google Earth

### **FASE 11: Sistema de Configuración** (5-7 días)
**Riesgo:** 🔴 Alto | **Prioridad:** Crítica

#### Funciones objetivo:
```python
tz_core/config_manager.py (EXPANSIÓN)
├── bootstrap_config()         # ⚠️ ULTRA-CRÍTICO
├── cfg_build_rename_map()     # Variables globales
├── cfg_add_user_synonym()     # Estado compartido
└── funciones relacionadas
```

#### 🚨 **PRECAUCIONES EXTREMAS:**
- `bootstrap_config()` maneja variables globales CONFIG/RENAME_MAP
- Testing exhaustivo en múltiples escenarios
- Backup completo antes de modificaciones
- Rollback plan definido

---

## 🚫 **ZONAS PROHIBIDAS**

### ❌ **NO TOCAR HASTA FASES 12-13**

```python
_wizard_qc_mapeo()  # 382 líneas - PELIGRO EXTREMO DOCUMENTADO
                    # Razones:
                    # - Múltiples input() sin framework mocking
                    # - Dependencias complejas con CONFIG global
                    # - Efectos secundarios en estado global
                    # - Core crítico del negocio (zero fault tolerance)
                    # - Contraindicación absoluta documentada
```

### ⚠️ **MÁXIMA PRECAUCIÓN**
```python
main()              # Orquestador principal - tocar solo si es esencial
bootstrap_config()  # Variables globales críticas
cualquier función   # Con > 5 dependencias globales identificadas
```

---

## 📋 **CRITERIOS DE ÉXITO**

### ✅ **Métricas por fase:**

**FASE 9A (Normalización):**
- [ ] ~100 líneas reducidas del monolito
- [ ] 4-6 módulos nuevos creados
- [ ] 0 breaking changes
- [ ] 47/47 tests mantienen passing

**FASE 9B (Analytics):**
- [ ] ~200 líneas reducidas del monolito  
- [ ] Reportes HTML mantienen funcionalidad
- [ ] Compatibilidad con formatos existentes
- [ ] Performance sin degradación

**FASE 10 (KML):**
- [ ] Duplicados resueltos
- [ ] 1 generador KML unificado
- [ ] Google Earth compatibility mantenida
- [ ] Tests E2E con archivos reales

**FASE 11 (Config):**
- [ ] Variables globales gestionadas correctamente
- [ ] Inicialización app sin cambios
- [ ] Configuración persistent funcional
- [ ] Zero downtime deployment

---

## 🔧 **METODOLOGÍA DE TRABAJO**

### 📝 **Proceso de extracción estándar:**

1. **Análisis previo** (30 min)
   - Mapear dependencias exactas
   - Identificar imports necesarios
   - Planificar tests de validación

2. **Creación modular** (1-2 horas)
   - Crear módulo en tz_core/
   - Extraer función con docstring profesional
   - Implementar imports necesarios

3. **Redirección temporal** (30 min)
   - Crear wrapper en monolito
   - Importar desde nuevo módulo
   - Mantener contrato original

4. **Testing exhaustivo** (1 hora)
   - Ejecutar test suite completo
   - Validar funcionalidad específica
   - Testing con datos reales

5. **Documentación** (30 min)
   - Actualizar mapas de arquitectura
   - Documentar cambios en roadmap
   - Commit atómico con descripción clara

### 🎯 **Principios de extracción:**

- **Un módulo a la vez** - No extracciones masivas
- **Testing continuo** - 47/47 tests deben mantenerse passing
- **Commits atómicos** - Una extracción = un commit
- **Documentación sincronizada** - Actualizar docs en cada fase
- **Rollback ready** - Plan de reversión para cada cambio

---

## 📊 **IMPACTO PROYECTADO**

### 🎯 **Al completar las 4 fases:**

**Reducción del monolito:**
- Actual: 7,987 líneas
- Proyectado: ~7,200 líneas (-787 líneas adicionales)
- **Total del proyecto:** Reducción de ~1,039 líneas vs estado original

**Framework modular:**
- Actual: 15 módulos  
- Proyectado: 22-25 módulos
- **Cobertura:** ~80% de funcionalidad modularizada

**Mantenibilidad:**
- Funciones especializadas en módulos dedicados
- Testing granular por componente
- Debugging simplificado
- Onboarding developers acelerado

---

## 🏆 **CONCLUSIÓN ESTRATÉGICA**

El HTML Generator Epic ha demostrado que la **modularización sistemática es altamente exitosa** en este proyecto. El roadmap de 4 fases siguientes está **metodológicamente validado** y representa una **continuación natural** del trabajo excepcional ya realizado.

### 💡 **Recomendación inmediata:**
**Iniciar FASE 9A (Normalización)** - Riesgo mínimo, impacto alto, fundación sólida para fases posteriores.

---

*Este documento debe actualizarse después de cada fase completada para mantener sincronización entre agentes casa/oficina.*