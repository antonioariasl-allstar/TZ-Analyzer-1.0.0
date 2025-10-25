# 🚨 FASE 8B - ANÁLISIS CRÍTICO DE DEPENDENCIAS
## HTML Generator Extraction - Campo Minado Protocol

### 📊 **MAPEO COMPLETO DE DEPENDENCIAS**

#### ✅ **Variables Globales HTML (Estado Dinámico)**
```python
# Línea 2421-2422 - Declaración inicial
HTML_SECCION_INTERACCIONES = ""
HTML_SECCION_ANTENAS = ""

# Variable implícita (no declarada inicialmente)
HTML_SECCION_TODOS_CONTACTOS = ""  # Creada dinámicamente en main()
```

**Patrón de Uso:**
- **Línea 8110-8117**: Construcción de `HTML_SECCION_INTERACCIONES`
- **Línea 8121-8126**: Construcción de `HTML_SECCION_TODOS_CONTACTOS`  
- **Línea 8131-8157**: Construcción de `HTML_SECCION_ANTENAS`
- **Línea 4560, 4573**: Consumo en `generar_informe_html()` vía `globals().get()`

#### ⚙️ **CONFIG Global (Configuración Crítica)**
```python
# Accesos identificados en generar_informe_html():
CONFIG.get("salida", {}).get("separar_kml_kmz", False)      # Línea ~3370
CONFIG.get("branding", {}).get("logo_path")                # Call sites
CONFIG["html"]["generar_en_modo_manual"]                   # Flow control
```

#### 🔧 **Funciones Auxiliares**
```python
# Línea 980 - Función de utilidad de logos
def _copiar_logo_a_salida(logo_src: str, carpeta_salida: str) -> str | None

# Logging global
log()  # Usado extensivamente en la función
```

### 🎯 **CALL SITES CRÍTICOS**

#### **Call Site 1 - Modo Manual (Línea 7998)**
```python
if bool(CONFIG.get("html", {}).get("generar_en_modo_manual", False)):
    _copiar_logo_a_salida(CONFIG.get("branding", {}).get("logo_path"), carpeta_salida)
    informe_html = generar_informe_html(
        df, archivo_kml, carpeta_salida, nombre_salida, hoja
    )
```

#### **Call Site 2 - Flujo Estándar (Línea 8162)**
```python
_copiar_logo_a_salida(CONFIG.get("branding", {}).get("logo_path"), carpeta_salida)
informe_html = generar_informe_html(
    df, archivo_kml, carpeta_salida, nombre_salida, hoja,
    os.path.basename(archivo_entrada)
)
```

### 🚨 **ESTRATEGIA DE DESACOPLAMIENTO**

#### **Fase 8B.1 - Parametrización**
1. **CONFIG → Parámetro**: Pasar config como dict
2. **HTML_SECCION_* → Parámetro**: Pasar como dict `html_sections`
3. **log → Parámetro**: Función logging inyectable
4. **_copiar_logo_a_salida → Import**: Importar desde tz_core.utils

#### **Fase 8B.2 - Interfaz Temporal**
```python
def generar_informe_html(
    df, archivo_kml, carpeta_salida, nombre_salida, 
    hoja=None, nombre_bitacora=None,
    config=None,                    # NEW: CONFIG parametrizado
    html_sections=None,             # NEW: HTML_SECCION_* parametrizadas
    logger_func=None                # NEW: log() inyectable
):
    # Fallbacks durante transición
    if config is None:
        config = globals().get('CONFIG', {})
    if html_sections is None:
        html_sections = {
            'interacciones': globals().get('HTML_SECCION_INTERACCIONES', ''),
            'antenas': globals().get('HTML_SECCION_ANTENAS', ''),
            'todos_contactos': globals().get('HTML_SECCION_TODOS_CONTACTOS', '')
        }
    if logger_func is None:
        logger_func = globals().get('log', print)
```

#### **Fase 8B.3 - Call Sites Update**
```python
# En main(), después de construir secciones HTML:
html_sections = {
    'interacciones': HTML_SECCION_INTERACCIONES,
    'antenas': HTML_SECCION_ANTENAS, 
    'todos_contactos': HTML_SECCION_TODOS_CONTACTOS
}

# Llamadas actualizadas:
informe_html = generar_informe_html(
    df, archivo_kml, carpeta_salida, nombre_salida, hoja,
    config=CONFIG,
    html_sections=html_sections,
    logger_func=log
)
```

### ⚡ **RIESGOS IDENTIFICADOS**

| **Riesgo** | **Criticidad** | **Mitigación** |
|------------|----------------|----------------|
| Variables HTML dinámicas | **ALTA** | Parametrización con fallbacks |
| CONFIG global mutable | **CRÍTICA** | Pass-by-value, defensive copy |
| Call sites múltiples | **MEDIA** | Update coordinado con wrapper |
| Estado HTML timing | **ALTA** | Validar construcción antes de uso |

### 🎯 **SIGUIENTE PASO: FASE 8B.4 - GOLDEN BACKUP**

Crear snapshot atómico pre-extracción para garantizar rollback seguro.

---
**ESTADO**: ✅ Mapeo completo - Listo para Golden Backup  
**ROI**: 30% reducción monolito (2590/7680 líneas)  
**RIESGO**: MODERADO (dependencias parametrizables)