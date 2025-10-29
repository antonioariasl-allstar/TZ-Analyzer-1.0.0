# SPRINT 1 ADAPTADO: tz_services + Fachadas Mínimas

**Basado en:** Prompt GPT-5 + Análisis TZ-Analyzer Fase 2  
**Fecha:** 29 octubre 2025  
**Objetivo:** Extraer **18 funciones tz_services REALES** con fachadas limpias  

## 🎯 ALCANCE VALIDADO

### Funciones Target (18 funciones REALES verificadas)

#### **validation.py** (13 funciones)
```python
# LOW RISK - Funciones puras de validación
validar_columnas(L666)           # 3 líneas - SAFE
validar_datos(L671)              # 25 líneas - SAFE  
_valid_latlon_vals(L1811)        # 12 líneas - SAFE
_es_valida_latlon_row(L1823)     # 27 líneas - SAFE  
_es_valida_latlon_row(L1930)     # Duplicado - MERGE REQUIRED
_valid_latlon(L3608)             # Similar - DEDUPE
_first_valid_geo(L3831)          # 20 líneas - SAFE
_valida_formato_hora(L5568)      # 6 líneas - SAFE
_valida_fecha_parsible(L5574)    # 7 líneas - SAFE
_valida_latlon(L5581)            # 15 líneas - SAFE  
validate_schema_or_abort(L5596)  # 25 líneas - SAFE
_es_columna_valida_para(L6011)   # 10 líneas - SAFE
_valida_formato_hora(L6156)      # Duplicado - MERGE REQUIRED
```

#### **html_generation.py** (5 funciones)
```python  
# MEDIUM RISK - Funciones de generación HTML
render_heatmap_html_for_day(L2193)  # 157 líneas - COMPLEX
_build_logo_html(L3198)             # 22 líneas - SAFE
generate_html(L7362)                # 5 líneas - FACADE
generar_informe_html(L3256)         # 199 líneas - ALREADY TAGGED
```

## ⚙️ MODO DE TRABAJO (GPT-5 + TZ-Analyzer)

### **Fase 1.1 - Estructura Base + Validadores SAFE** 
**Tiempo estimado:** 2-3 horas  
**Riesgo:** BAJO  

1. **Crear estructura tz_services/**
   ```
   tz_services/
   ├── __init__.py          # Exports públicos
   ├── validation.py        # 13 funciones validación
   └── html_generation.py   # 5 funciones HTML
   ```

2. **Migrar validadores SAFE (8 funciones)**
   - `validar_columnas`, `validar_datos` 
   - `_valid_latlon_vals`, `_first_valid_geo`
   - `_valida_formato_hora`, `_valida_fecha_parsible`
   - `_valida_latlon`, `validate_schema_or_abort`

3. **Crear fachadas limpias en monolito**
   ```python
   def validar_columnas(dataframe, columnas_esperadas):
       from tz_services.validation import validar_columnas as _impl
       return _impl(dataframe, columnas_esperadas)
   ```

4. **Checkpoint 1:** Test básico validación columnas

### **Fase 1.2 - Resolución Duplicados**
**Tiempo estimado:** 1-2 horas  
**Riesgo:** MEDIO  

1. **Mergear funciones duplicadas**
   - `_es_valida_latlon_row` (L1823 vs L1930) → Unificar
   - `_valida_formato_hora` (L5568 vs L6156) → Consolidar
   - `_valid_latlon` vs `_valida_latlon` → Alias

2. **Checkpoint 2:** Test validación lat/lon

### **Fase 1.3 - HTML Generation (COMPLEX)**
**Tiempo estimado:** 3-4 horas  
**Riesgo:** ALTO  

1. **Analizar dependencias render_heatmap_html_for_day**
   - Depende: `_fmt_coord`, `_formatear_valor_para_burbuja`
   - Estrategia: Copiar dependencias o crear interfaces

2. **Migrar funciones HTML**
   - `_build_logo_html` (SAFE) 
   - `render_heatmap_html_for_day` (COMPLEX - 157 líneas)

3. **Checkpoint 3:** Comparar HTML output completo

## 🛡️ REGLAS ADAPTADAS

### **De GPT-5 (Conservadas)**
- ✅ No eliminar del monolito → solo copiar + fachada
- ✅ Evitar imports circulares 
- ✅ Checkpoints tras cada fase
- ✅ Pausas automáticas en dependencias complejas

### **De TZ-Analyzer (Añadidas)**
- ✅ Priorizar LOW RISK → MEDIUM RISK → Evitar DANGER ZONE
- ✅ Resolver duplicados antes de migrar
- ✅ Validar con datos reales pequeños (dataset test)
- ✅ Mantener etiquetas `# pkg:` hasta confirmación

## 🧪 PRUEBAS ESPECÍFICAS

### **Validación (Fase 1.1)**
```python
# Test básico
df_test = pd.DataFrame({'col1': [1,2], 'col2': [3,4]})
assert validar_columnas(df_test, ['col1', 'col3']) == ['col3']
assert validar_datos(df_test, ['col1', 'col2']) == []
```

### **HTML Generation (Fase 1.3)**
```python
# Test comparativo - antes vs después
html_antes = generar_informe_html(dataset_small, config_test)
# ... migrar funciones ...
html_despues = generar_informe_html(dataset_small, config_test)
assert html_antes == html_despues  # DEBE SER IDÉNTICO
```

## 📁 ARCHIVOS A CREAR

```
tz_services/
├── __init__.py                    # Exports: validate_dataset, render_heatmap, etc.
├── validation.py                  # 13 funciones validación (8 safe + 5 merge)
└── html_generation.py             # 5 funciones HTML

docs/
├── S1_SERVICES_MIGRATION.md       # Log migración detallado
└── S1_CHECKPOINT_RESULTS.csv      # Resultados tests por fase
```

## ⚠️ PAUSAS AUTOMÁTICAS (GPT-5 + TZ-Analyzer)

### **Pausar si detecta:**
- 🚨 Dependencia circular: `tz_services` → `CONFIG` → `_wizard_qc_mapeo`
- 🚨 Variables globales o estado mutable
- 🚨 Imports complejos: `tkinter`, `matplotlib`, `CONFIG`
- 🚨 Fallo en checkpoints comparativos

### **Pausar y consultar si:**
- ⚡ Función >100 líneas (`render_heatmap_html_for_day` = 157 líneas)
- ⚡ Dependencias cruzadas entre funciones migradas
- ⚡ Tests comparativos con diferencias menores (<5%)

## 📊 MÉTRICAS DE ÉXITO

### **Criterios Aceptación (GPT-5)**
- ✅ Proyecto corre igual (HTML/KML/CLI intactos)
- ✅ `tz_services` importable independientemente  
- ✅ Fachadas limpias funcionando
- ✅ Documentación completa

### **Métricas TZ-Analyzer**
- ✅ **18 funciones extraídas** (10.6% del total)
- ✅ **~400 líneas migradas** (5.4% del monolito)
- ✅ **0 regressions** en outputs
- ✅ **Reducción complejidad monolito** medible

## 🚀 PRÓXIMOS PASOS POST-SPRINT 1

1. **Sprint 2:** `tz_kml` (6 funciones, dependencias moderadas)
2. **Sprint 3:** `tz_io` + `tz_cli` (14 funciones, bajo riesgo)  
3. **Sprint 4:** `tz_core` (11 funciones, utilidades)
4. **Sprint 5:** `tz_legacy` analysis (114 funciones)
5. **Sprint 6:** DANGER ZONE `_wizard_qc_mapeo` (382 líneas críticas)

---

## ✅ CONCLUSIÓN

**Sprint 1 adaptado** combina la **estrategia segura de GPT-5** (fachadas + checkpoints) con el **análisis real de TZ-Analyzer** (18 funciones verificadas). 

**Confianza de éxito:** 90% (funciones verificadas, estrategia probada, riesgos identificados)

**¿PROCEDER CON SPRINT 1?**