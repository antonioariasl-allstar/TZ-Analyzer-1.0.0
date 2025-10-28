# 🔬 DIAGNÓSTICO FORENSE: Análisis de Modularización

**Fecha:** 27 de octubre de 2025  
**Analista:** GitHub Copilot + Herramientas de análisis estático  
**Objetivo:** Determinar estrategia segura para modularizar sin romper el proyecto

---

## 📊 ESTADO ACTUAL DEL PROYECTO

### Métricas del Monolito

```
Archivo: script_principal_bitacoras_refactory.py
├── Tamaño: 385 KB (~8,400 líneas)
├── Funciones/Clases: 58
├── Conexiones totales: 60
├── Promedio llamadas/función: 1.03
├── Puntos de entrada: 14
└── Funciones huérfanas: 10
```

### Arquitectura Actual (Híbrida)

```
✅ EXISTE (parcial):
├── tz_core/
│   ├── config_manager.py
│   ├── data_loader.py
│   └── utils.py

❌ NO EXISTE:
├── tz_services/    (time_filters, data_validator, geo_tools, report_packager)
├── tz_io/          (html_writer, hash_tools)
└── tz_utils/       (path_tools, color_picker, helpers)

⚠️  MONOLITO:
└── script_principal_bitacoras_refactory.py (385 KB - TODO aquí)
```

---

## 🎯 FUNCIONES CRÍTICAS (Top Dependientes)

Estas funciones son **nudos** de la red de dependencias:

| Función | Dependientes | Descripción | Riesgo de Mover |
|---------|--------------|-------------|-----------------|
| `log` | 5 | Función de logging | 🔴 ALTO |
| `_en_rango` | 3 | Validación temporal | 🟡 MEDIO |
| `main` | 3 | Orquestador principal | 🔴 CRÍTICO (no mover) |
| `calcular_punto_final` | 2 | Cálculo geográfico | 🟢 BAJO |
| `cfg_build_rename_map` | 2 | Config management | 🟢 BAJO |

---

## 📦 CATEGORIZACIÓN FUNCIONAL

### 1. UTILIDADES (11 funciones) - 🟢 BAJO RIESGO
```
log, _tiene_valor, _formatear_valor_para_burbuja, _a_float, 
_armar_descripcion_compacta, _agregar_bloque, _construir_rangos_cfg, 
_solicitar_overrides_topn, _compactar_ruta
```
**Recomendación:** Mover a `tz_utils/helpers.py`

### 2. NORMALIZACIÓN (7 funciones) - 🟡 MEDIO RIESGO
```
_fix_mojibake_text, _aplicar_reemplazos_regex, normalizar_texto, 
normalizar_columnas_texto, _dedupe_columns, _normalizar_fecha, 
_normalizar_hora
```
**Recomendación:** Mover a `tz_services/data_validator.py`

### 3. IO (7 funciones) - 🟢 BAJO RIESGO
```
_sha256_de_archivo, _escribe_hashes_txt, _copiar_logo_a_salida, 
_cargar_excel_con_normalizacion, _atomic_write_json, 
_obtener_hojas_visibles, _seleccionar_hoja
```
**Recomendación:** Mover a `tz_io/file_io.py` y `tz_io/hash_tools.py`

### 4. CONFIG (6 funciones) - 🟢 BAJO RIESGO
```
cfg_build_rename_map, bootstrap_config, cargar_config, 
_normalize_key_for_synonyms, cfg_add_user_synonym, get_config
```
**Recomendación:** Ya existe `tz_core/config_manager.py` - migrar allí

### 5. TIEMPO (6 funciones) - 🟡 MEDIO RIESGO
```
_en_rango, _parse_hhmmss_to_minutes, _hhmmss_to_time_or_none, 
_clasificar_rango_sv, _minutes_from_any, etiqueta_rango
```
**Recomendación:** Mover a `tz_services/time_filters.py`

### 6. UI (6 funciones) - 🟢 BAJO RIESGO
```
_solicitar_color_tema, _solicitar_filtros_tiempo, 
_seleccionar_hoja_visible, _modo_manual, _solicitar_overrides_topn, 
_wizard_qc_mapeo
```
**Recomendación:** Mover a `tz_core/cli_interface.py`

### 7. KML (3 funciones) - 🔴 ALTO RIESGO
```
generar_kml, _crear_feature_kml, _hex_to_kml_color
```
**Recomendación:** Mover ÚLTIMO - tiene dependencias complejas

### 8. HTML (3 funciones) - 🔴 ALTO RIESGO
```
_construir_seccion_interacciones, _construir_seccion_todos_contactos, 
generar_informe_html
```
**Recomendación:** Mover a `tz_io/html_writer.py` ÚLTIMO

### 9. GEO (3 funciones) - 🟢 BAJO RIESGO
```
calcular_punto_final, grados_a_radianes, generar_cono
```
**Recomendación:** Mover a `tz_services/geo_tools.py`

### 10. VALIDACIÓN (2 funciones) - 🟢 BAJO RIESGO
```
_wizard_qc_mapeo, _preflight_esenciales
```
**Recomendación:** Mover a `tz_services/data_validator.py`

### 11. ANÁLISIS (2 funciones) - 🟡 MEDIO RIESGO
```
generar_historial_cambios_antena, analizar_antenas
```
**Recomendación:** Mover a `tz_services/analysis_engine.py`

### 12. ORQUESTACIÓN (2 funciones) - 🔴 CRÍTICO
```
main, run_tz_analysis
```
**Recomendación:** ❌ **NUNCA MOVER** - Son el corazón del sistema

---

## ⚠️ NUDOS CRÍTICOS DETECTADOS

### 1. `main` - Score: 60 (3 deps × 20 llamadas)
- **Tipo:** Orquestador principal
- **Problema:** Llama a 20 funciones diferentes
- **Solución:** NO mover. Es el punto de entrada.

### 2. `generar_kml` - Score: 10 (2 deps × 5 llamadas)
- **Tipo:** Generador de KML
- **Problema:** Dependencias con geo, config, logging
- **Solución:** Mover ÚLTIMO, después de sus dependencias

---

## 👻 FUNCIONES HUÉRFANAS (Candidatas a limpieza)

Estas funciones **no son llamadas por nadie** y **no llaman a nadie**:

```
1. _atomic_write_json (L1043)      ← Posiblemente obsoleta
2. _es_num (L5971)                 ← Helper no usado
3. _listar_todas_hojas (L5932)     ← Excel helper no usado
4. _normalizar_fecha (L5977)       ← Normalización no usada
5. _normalizar_hora (L6011)        ← ídem
6. _obtener_hojas_visibles (L5928) ← Excel helper no usado
7. _pad_hhmmss (L5993)             ← Padding no usado
8. _preflight_esenciales (L6028)   ← Validación no usada
9. _seleccionar_hoja (L5940)       ← Excel helper no usado
10. analizar_antenas (L1167)       ← Análisis no usado
```

**Recomendación:** Investigar si realmente no se usan antes de eliminar.

---

## 🎯 ESTRATEGIA DE MODULARIZACIÓN SEGURA

### FASE 1: PREPARACIÓN (1 sesión)
✅ **Objetivo:** Sin cambios funcionales, solo infraestructura

1. Crear estructura de directorios:
   ```
   tz_services/
   tz_io/
   tz_utils/
   ```

2. Crear archivos `__init__.py` en cada módulo

3. Ejecutar tests baseline (asegurar que TODO funciona)

4. Commit: `feat: estructura de módulos preparada`

---

### FASE 2: EXTRACCIÓN NIVEL 1 - BAJO RIESGO (2-3 sesiones)

#### SESIÓN 1: Utilidades básicas
**Target:** `tz_utils/helpers.py`

Funciones a mover:
```python
- grados_a_radianes
- _a_float
- _tiene_valor
- _compactar_ruta
```

**Test después de cada función:**
```bash
python -m pytest tests/
```

**Commit después de validar:** `refactor: extraer utilidades básicas a tz_utils`

---

#### SESIÓN 2: Herramientas GEO
**Target:** `tz_services/geo_tools.py`

Funciones a mover:
```python
- calcular_punto_final (depende de grados_a_radianes)
- generar_cono
```

**Test:** Validar que KML sigue generándose bien

**Commit:** `refactor: extraer geo_tools a tz_services`

---

#### SESIÓN 3: Herramientas IO
**Target:** `tz_io/file_io.py` y `tz_io/hash_tools.py`

Funciones a mover:
```python
# hash_tools.py
- _sha256_de_archivo
- _escribe_hashes_txt

# file_io.py
- _copiar_logo_a_salida
- _cargar_excel_con_normalizacion
```

**Test:** Validar que archivos se procesan correctamente

**Commit:** `refactor: extraer IO y hash tools`

---

### FASE 3: EXTRACCIÓN NIVEL 2 - MEDIO RIESGO (3-4 sesiones)

#### SESIÓN 4: Filtros de tiempo
**Target:** `tz_services/time_filters.py`

**⚠️ CUIDADO:** Hay funciones duplicadas con mismo nombre

Funciones a mover:
```python
- _hhmmss_to_time_or_none (resolver duplicado L89 vs L6044)
- _en_rango (resolver duplicado)
- _parse_hhmmss_to_minutes
- _minutes_from_any
- _clasificar_rango_sv
- etiqueta_rango
```

**Plan:**
1. Identificar cuál versión es la correcta
2. Eliminar duplicado
3. Mover función unificada

**Test:** Validar filtros temporales en reportes

**Commit:** `refactor: extraer y unificar time_filters`

---

#### SESIÓN 5: Normalización de datos
**Target:** `tz_services/data_validator.py`

Funciones a mover:
```python
- _fix_mojibake_text
- _aplicar_reemplazos_regex
- normalizar_texto
- normalizar_columnas_texto
- _dedupe_columns
```

**Test:** Validar que datos se normalizan correctamente

**Commit:** `refactor: extraer data_validator`

---

#### SESIÓN 6: Interfaz de usuario
**Target:** `tz_core/cli_interface.py`

Funciones a mover:
```python
- _solicitar_color_tema
- _solicitar_filtros_tiempo
- _solicitar_overrides_topn
- _wizard_qc_mapeo
- _modo_manual
```

**Test:** Ejecutar flujo completo manual

**Commit:** `refactor: extraer CLI interface`

---

### FASE 4: EXTRACCIÓN NIVEL 3 - ALTO RIESGO (3-4 sesiones)

#### SESIÓN 7-8: Generación KML
**Target:** `tz_io/kml_generator.py`

**⚠️ MUY ENREDADO** - Hacer con extremo cuidado

Funciones a mover:
```python
- _hex_to_kml_color
- _crear_feature_kml (dependencia con config, geo)
- generar_kml (dependencia con MUCHAS funciones)
```

**Plan:**
1. Mover primero `_hex_to_kml_color` (simple)
2. Luego `_crear_feature_kml`
3. ÚLTIMO `generar_kml` (núcleo crítico)

**Test:** Validar que KMZ se genera idéntico

**Commit:** `refactor: extraer KML generator (alto riesgo)`

---

#### SESIÓN 9-10: Generación HTML
**Target:** `tz_io/html_writer.py`

**⚠️ MUY ENREDADO** - Tiene 2,500+ líneas de HTML embebido

Funciones a mover:
```python
- _construir_seccion_interacciones
- _construir_seccion_todos_contactos
- generar_informe_html (GIGANTE)
```

**Plan:**
1. NO mover inmediatamente
2. Primero refactorizar HTML a templates
3. Luego extraer generador

**Test:** Validar HTML bit-a-bit con golden baseline

**Commit:** `refactor: extraer HTML writer (alto riesgo)`

---

### FASE 5: LIMPIEZA FINAL (1 sesión)

1. Investigar funciones huérfanas
2. Eliminar código muerto
3. Actualizar imports en script principal
4. Documentar nuevos módulos
5. Actualizar README con nueva arquitectura

**Commit:** `refactor: limpieza final y documentación`

---

## 🚨 REGLAS DE ORO

### ❌ NUNCA HACER:

1. ❌ Mover múltiples categorías en un solo commit
2. ❌ Modificar lógica mientras se mueve código
3. ❌ Mover funciones sin ejecutar tests después
4. ❌ Tocar `main()` o `run_tz_analysis()`
5. ❌ Hacer refactoring "de paso"

### ✅ SIEMPRE HACER:

1. ✅ Un commit por función/grupo movido
2. ✅ Ejecutar tests después de CADA cambio
3. ✅ Comparar outputs con golden baseline
4. ✅ Documentar cambios en commit message
5. ✅ Mantener script original como fallback hasta validar TODO

---

## 📊 ESTIMACIÓN DE TIEMPO

| Fase | Sesiones | Riesgo | Prioridad |
|------|----------|--------|-----------|
| FASE 1: Preparación | 1 | 🟢 Bajo | 🔥 Alta |
| FASE 2: Nivel 1 | 2-3 | 🟢 Bajo | 🔥 Alta |
| FASE 3: Nivel 2 | 3-4 | 🟡 Medio | ⚡ Media |
| FASE 4: Nivel 3 | 3-4 | 🔴 Alto | ⏳ Baja |
| FASE 5: Limpieza | 1 | 🟢 Bajo | ⏳ Baja |
| **TOTAL** | **10-13** | - | - |

---

## 🎯 DECISIÓN RECOMENDADA

### Opción A: MODULARIZACIÓN COMPLETA ⭐ (Recomendada)
- **Tiempo:** 10-13 sesiones
- **Riesgo:** Medio-Alto (pero controlado con tests)
- **Beneficio:** Proyecto profesional, mantenible, escalable
- **Costo:** ~2-3 semanas de trabajo cuidadoso

### Opción B: MODULARIZACIÓN PARCIAL (Conservadora)
- **Tiempo:** 5-6 sesiones
- **Riesgo:** Bajo
- **Beneficio:** Solo extraer módulos seguros (Fase 1-2)
- **Costo:** Proyecto sigue híbrido

### Opción C: STATUS QUO (No recomendada)
- **Tiempo:** 0 sesiones
- **Riesgo:** Cero
- **Beneficio:** Estabilidad a corto plazo
- **Costo:** 385KB monolito insostenible a largo plazo

---

## 💡 VEREDICTO FINAL

**Claude Sonnet 4 y otros modelos se echaron atrás porque:**
1. ✅ Tienen razón: hay riesgo real de romper el proyecto
2. ✅ El código ESTÁ enredado (60 conexiones entre 58 funciones)
3. ✅ Hay duplicados ocultos (funciones con mismo nombre)
4. ⚠️ PERO: Con análisis exhaustivo y estrategia incremental es FACTIBLE

**MI RECOMENDACIÓN:**
- ✅ **Sí modularizar**, pero con método científico
- ✅ Fase 1-2 son SEGURAS (bajo riesgo)
- ⚠️ Fase 3-4 requieren paciencia extrema
- ✅ Tests automatizados son OBLIGATORIOS

**ALTERNATIVA SI TIENES PRISA:**
- Hacer solo FASE 1-2 (5-6 sesiones)
- Dejar KML/HTML en monolito documentado
- Tener "arquitectura híbrida permanente" bien organizada

---

## 📝 PRÓXIMOS PASOS

Si decides proceder:

1. **Revisar este documento completo**
2. **Decidir: Opción A (completa) o B (parcial)**
3. **Validar que tests funcionan actualmente**
4. **Crear branch: `refactor/modularization-safe`**
5. **Empezar con FASE 1 (solo infraestructura)**

**¿Listo para empezar o necesitas más análisis?** 🤔

---

*Documento generado por análisis automatizado + revisión humana*  
*Herramientas: `analisis_dependencias.py`, `categorizar_funciones.py`*  
*Metodología: Análisis estático de dependencias + categorización semántica*
