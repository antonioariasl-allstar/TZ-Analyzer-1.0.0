# TZ Analyzer CLI - Guía de Usuario Completa

> **Versión**: 1.0.2 | **Sprint**: 3B | **Fecha**: 29 octubre 2025

## 🎯 Introducción

**TZ Analyzer CLI** es la interfaz moderna de línea de comandos para el procesamiento automatizado de bitácoras telefónicas. Ofrece control programático completo para análisis forense, generación de mapas KML/KMZ y reportes HTML.

### ✨ Características Principales

- **Procesamiento Programático**: Ejecución automatizada sin interacción manual
- **Múltiples Formatos**: KML, KMZ, HTML según necesidades
- **Filtros Temporales**: Análisis por día, rangos de fechas/horas
- **Temas Visuales**: 12+ paletas de colores para Google Earth
- **Validación Automática**: Verificación de archivos antes del procesamiento
- **Entrada Manual**: Coordenadas específicas para análisis dirigido
- **Bridge Interactivo**: Acceso al wizard paso a paso desde CLI

---

## 🚀 Instalación y Configuración

### Requisitos Previos
- Python 3.8+
- Dependencias: Click, Pandas, OpenPyXL
- Configuración `config.json` (incluida)

### Ejecutar CLI
```bash
# Desde directorio raíz del proyecto
python tzanalysis.py [COMANDO] [OPCIONES]

# Ayuda general
python tzanalysis.py --help

# Versión
python tzanalysis.py --version
```

---

## 📋 Comandos Principales

### 🔵 `run` - Procesamiento Programático

**Propósito**: Procesamiento directo automatizado con argumentos CLI.

```bash
# Sintaxis básica
python tzanalysis.py run --input ARCHIVO [OPCIONES]

# Ejemplo básico
python tzanalysis.py run --input bitacora.xlsx --top-antenas 10

# Ejemplo avanzado con filtros
python tzanalysis.py run --input data.xlsx \
  --theme magenta \
  --format kmz \
  --time-filter rango-dias \
  --date-start 2025-10-01 \
  --date-end 2025-10-31 \
  --output resultados/
```

#### Opciones del Comando `run`

| Opción | Tipo | Descripción | Default |
|--------|------|-------------|---------|
| `--input, -i` | PATH | Archivo Excel/TSV a procesar | **Requerido** |
| `--top-antenas` | INT | Top N antenas en análisis | 10 |
| `--theme` | TEXT | Tema de colores (magenta, cyan, etc.) | default |
| `--output, -o` | PATH | Directorio de salida | auto-generado |
| `--format` | CHOICE | Formato: kml, kmz, html, all | all |
| `--time-filter` | CHOICE | Filtro temporal (ver sección) | completo |
| `--date-start` | DATE | Fecha inicio (YYYY-MM-DD) | - |
| `--date-end` | DATE | Fecha fin (YYYY-MM-DD) | - |
| `--hour-start` | TIME | Hora inicio (HH:MM) | - |
| `--hour-end` | TIME | Hora fin (HH:MM) | - |
| `--sheet` | TEXT | Hoja Excel específica | primera visible |

#### Filtros Temporales

| Filtro | Descripción | Opciones Requeridas |
|--------|-------------|-------------------|
| `completo` | Todos los datos sin filtro | Ninguna |
| `dia` | Filtrar por día específico | `--date-start` |
| `rango-dias` | Filtrar por rango de fechas | `--date-start --date-end` |
| `rango-horas` | Filtrar por rango horario | `--hour-start --hour-end` |

#### Ejemplos Avanzados `run`

```bash
# Solo KML con tema cyan
python tzanalysis.py run --input datos.xlsx --format kml --theme cyan

# Análisis de un día específico
python tzanalysis.py run --input bitacora.xlsx \
  --time-filter dia --date-start 2025-10-15

# Rango horario específico (madrugada)
python tzanalysis.py run --input data.xlsx \
  --time-filter rango-horas \
  --hour-start 02:00 --hour-end 06:00

# Procesamiento completo con verbose
python tzanalysis.py --verbose run --input bitacora.xlsx \
  --top-antenas 15 --theme magenta --output analisis_completo/
```

---

### 🔵 `validate` - Validación de Archivos

**Propósito**: Verificar archivos antes del procesamiento.

```bash
# Validación básica
python tzanalysis.py validate --input bitacora.xlsx

# Con reporte HTML
python tzanalysis.py validate --input data.tsv \
  --schema telefonico \
  --report validacion.html

# Auto-fix problemas menores
python tzanalysis.py validate --input archivo.xlsx --fix-auto --verbose
```

#### Opciones `validate`

| Opción | Descripción |
|--------|-------------|
| `--input, -i` | Archivo a validar (requerido) |
| `--report` | Archivo reporte HTML |
| `--schema` | Schema: telefonico, antenas, custom |
| `--fix-auto` | Auto-corregir problemas menores |

---

### 🔵 `manual` - Entrada Manual de Coordenadas

**Propósito**: Crear mapas de antenas con coordenadas específicas.

```bash
# Antena individual
python tzanalysis.py manual \
  --coord-lat 40.4168 \
  --coord-lon -3.7038 \
  --name "Torre Madrid"

# Con configuración personalizada
python tzanalysis.py manual \
  --coord-lat 19.4326 \
  --coord-lon -99.1332 \
  --name "Torre_CDMX" \
  --radius 2km \
  --theme magenta \
  --output mapas_manuales/

# Import desde archivo CSV
python tzanalysis.py manual --import-file antenas.csv --theme cyan
```

#### Opciones `manual`

| Opción | Descripción |
|--------|-------------|
| `--coord-lat` | Latitud de la antena |
| `--coord-lon` | Longitud de la antena |
| `--name` | Nombre de la antena |
| `--radius` | Radio cobertura (ej: 1km, 500m) |
| `--import-file` | Importar desde CSV/TSV |
| `--add-multiple` | Modo entrada múltiple interactiva |
| `--theme` | Tema de colores |
| `--output, -o` | Directorio de salida |

#### Formatos de Import

**CSV**:
```csv
lat,lon,name,radius
40.4168,-3.7038,Torre Madrid,1km
19.4326,-99.1332,Torre CDMX,2km
```

**TSV**:
```
lat	lon	name	radius
40.4168	-3.7038	Torre Madrid	1km
19.4326	-99.1332	Torre CDMX	2km
```

---

### 🔵 `config` - Gestión de Configuración

**Propósito**: Configurar y consultar el sistema TZ Analyzer.

```bash
# Mostrar configuración actual
python tzanalysis.py config show

# Listar temas disponibles
python tzanalysis.py config themes

# Establecer valor
python tzanalysis.py config set style.theme_hex "#ff00ff"

# Reset a defaults
python tzanalysis.py config reset

# Exportar configuración
python tzanalysis.py config export --output mi_config.json

# Importar configuración
python tzanalysis.py config import --file nueva_config.json
```

#### Subcomandos `config`

| Subcomando | Descripción |
|------------|-------------|
| `show` | Mostrar configuración actual |
| `themes` | Listar temas y opciones disponibles |
| `set` | Establecer valor de configuración |
| `reset` | Reset a valores por defecto |
| `export` | Exportar configuración a archivo |
| `import` | Importar configuración desde archivo |

---

### 🔵 `process` - Bridge Interactivo

**Propósito**: Acceder al menú interactivo desde CLI manteniendo el wizard.

```bash
# Menú interactivo completo
python tzanalysis.py process

# Pre-seleccionar archivo
python tzanalysis.py process --input bitacora.xlsx

# Equivalente a: python run.py
python tzanalysis.py process --interactive
```

**Diferencias**:
- `run`: Argumentos CLI directos, sin interacción
- `process`: Wizard paso a paso, bridge al menú existente

---

### 🔵 `info` - Información del Sistema

**Propósito**: Diagnóstico y estado del sistema.

```bash
# Información completa
python tzanalysis.py info

# Solo versión
python tzanalysis.py info --version

# Solo sistema
python tzanalysis.py info --system

# Solo dependencias
python tzanalysis.py info --dependencies
```

---

## ⚙️ Opciones Globales

Estas opciones se aplican a todos los comandos:

| Opción | Descripción |
|--------|-------------|
| `--config, -c` | Archivo config.json personalizado |
| `--output-dir, -o` | Directorio base para salidas |
| `--log-level, -l` | Nivel logging: debug, info, warn, error |
| `--quiet, -q` | Suprimir output no esencial |
| `--verbose, -v` | Output detallado con timestamps |
| `--dry-run` | Simular ejecución sin cambios |
| `--version` | Mostrar versión y salir |

### Ejemplos Opciones Globales

```bash
# Modo silencioso
python tzanalysis.py --quiet run --input data.xlsx

# Modo verboso con log debug
python tzanalysis.py --verbose --log-level debug run --input bitacora.xlsx

# Dry-run para validar sin ejecutar
python tzanalysis.py --dry-run run --input data.xlsx --format all

# Configuración personalizada
python tzanalysis.py --config mi_config.json run --input archivo.xlsx
```

---

## 🎨 Temas de Colores Disponibles

```bash
# Ver todos los temas
python tzanalysis.py config themes
```

**Temas Populares**:
- `magenta` - Alto contraste, forense
- `cyan` - Azul brillante, técnico  
- `yellow` - Amarillo, alta visibilidad
- `red` - Rojo intenso, alertas
- `blue` - Azul profesional
- `green` - Verde, análisis ambiental

---

## 📁 Estructura de Archivos de Salida

### Comando `run` con `--format all`

```
outputs_archivo_2025-10-29/
├── TZ_Analysis_Report.html     # Reporte interactivo
├── mapa_calor_antenas.kml      # Mapa Google Earth
├── datos_completos.kmz         # Archive comprimido
└── archivo_hashes.txt          # Verificación integridad
```

### Comando `manual`

```
salida_manual/
├── antena_Torre_Madrid_mapa.kml      # Mapa individual
└── antena_Torre_Madrid_cobertura.kmz # Cobertura con radio
```

---

## 🔄 Workflows Típicos

### 1. Análisis Forense Completo

```bash
# Paso 1: Validar archivo
python tzanalysis.py validate --input bitacora_caso.xlsx --verbose

# Paso 2: Análisis completo
python tzanalysis.py run --input bitacora_caso.xlsx \
  --theme magenta \
  --format all \
  --top-antenas 15 \
  --output caso_2025_10_29/

# Paso 3: Puntos de interés específicos
python tzanalysis.py manual \
  --coord-lat 19.4326 \
  --coord-lon -99.1332 \
  --name "Ubicacion_Sospechosa" \
  --theme red \
  --output caso_2025_10_29/puntos_interes/
```

### 2. Análisis Temporal Específico

```bash
# Actividad durante horario laboral
python tzanalysis.py run --input datos.xlsx \
  --time-filter rango-horas \
  --hour-start 08:00 \
  --hour-end 18:00 \
  --theme blue

# Actividad fin de semana específico
python tzanalysis.py run --input datos.xlsx \
  --time-filter rango-dias \
  --date-start 2025-10-26 \
  --date-end 2025-10-27 \
  --theme cyan
```

### 3. Batch Processing Automatizado

```bash
#!/bin/bash
# Script para procesar múltiples archivos

for archivo in *.xlsx; do
  echo "Procesando: $archivo"
  python tzanalysis.py run \
    --input "$archivo" \
    --format kmz \
    --theme magenta \
    --output "resultados_$(basename $archivo .xlsx)/"
done
```

---

## ❌ Manejo de Errores

### Errores Comunes y Soluciones

**Archivo no encontrado**:
```bash
Error: Invalid value for '--input': Path 'archivo.xlsx' does not exist.
```
✅ **Solución**: Verificar ruta y existencia del archivo

**Formato de fecha inválido**:
```bash  
Error: Invalid value for '--date-start': invalid date format
```
✅ **Solución**: Usar formato YYYY-MM-DD (ej: 2025-10-29)

**Columnas faltantes**:
```bash
❌ Error: Columnas requeridas no encontradas: fecha, hora, lat, long
```
✅ **Solución**: Usar `validate` antes de `run`, verificar mapeo de columnas

### Debug Avanzado

```bash
# Información detallada de errores
python tzanalysis.py --verbose --log-level debug run --input archivo.xlsx

# Validación previa completa
python tzanalysis.py validate --input archivo.xlsx --fix-auto --verbose
```

---

## 🔄 CLI vs Menú Interactivo

| Aspecto | CLI (`tzanalysis.py`) | Menú Interactivo (`python run.py`) |
|---------|----------------------|-----------------------------------|
| **Uso** | Automatización, scripts, batch | Exploración, aprendizaje, one-off |
| **Interacción** | Argumentos únicos | Wizard paso a paso |
| **Reproducibilidad** | Scripts reutilizables | Manual cada vez |
| **Flexibilidad** | Opciones predefinidas | Mapeo dinámico columnas |
| **Velocidad** | Instantáneo | Requiere interacción |
| **Learning Curve** | Requiere conocer opciones | Guiado y explicativo |

### Cuándo Usar Cada Uno

**Usar CLI cuando**:
- Procesamiento automatizado
- Scripts y batch jobs  
- Parámetros conocidos y fijos
- Integración con otros sistemas
- Reproducibilidad exacta

**Usar Menú Interactivo cuando**:
- Primera vez con archivo nuevo
- Explorar opciones disponibles
- Mapeo complejo de columnas
- Aprender el sistema
- Análisis ad-hoc

### Migración: Menú → CLI

1. **Ejecutar una vez en menú interactivo** para entender el archivo
2. **Tomar nota de opciones** usadas (tema, top antenas, filtros)
3. **Convertir a comando CLI**:

```bash
# Del wizard interactivo:
# - Archivo: bitacora.xlsx  
# - Tema: magenta
# - Top antenas: 10
# - Filtro: rango días 01-15 oct

# Al comando CLI:
python tzanalysis.py run \
  --input bitacora.xlsx \
  --theme magenta \
  --top-antenas 10 \
  --time-filter rango-dias \
  --date-start 2025-10-01 \
  --date-end 2025-10-15
```

---

## 🔧 Integración y Automatización

### Scripts de Shell

```bash
#!/bin/bash
# analisis_diario.sh - Procesamiento automático diario

FECHA=$(date +%Y-%m-%d)
ARCHIVO="bitacoras/bitacora_$FECHA.xlsx"

if [ -f "$ARCHIVO" ]; then
  python tzanalysis.py run \
    --input "$ARCHIVO" \
    --theme cyan \
    --format all \
    --output "reportes_diarios/$FECHA/"
  
  echo "✅ Análisis completado: $FECHA"
else
  echo "❌ Archivo no encontrado: $ARCHIVO"
fi
```

### Python Scripts

```python
import subprocess
import sys
from pathlib import Path

def procesar_bitacora(archivo, tema="magenta", formato="all"):
    """Procesar bitácora usando TZ Analyzer CLI"""
    cmd = [
        sys.executable, "tzanalysis.py", 
        "run",
        "--input", str(archivo),
        "--theme", tema,
        "--format", formato,
        "--output", f"salida_{archivo.stem}/"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ Procesado: {archivo}")
        return True
    else:
        print(f"❌ Error: {result.stderr}")
        return False

# Usar función
archivos = Path("bitacoras/").glob("*.xlsx")
for archivo in archivos:
    procesar_bitacora(archivo)
```

---

## 📚 Referencia Rápida

### Comandos Esenciales

```bash
# Help principal
python tzanalysis.py --help

# Información sistema
python tzanalysis.py info

# Validar archivo
python tzanalysis.py validate --input archivo.xlsx

# Procesamiento básico
python tzanalysis.py run --input archivo.xlsx

# Procesamiento avanzado
python tzanalysis.py run --input archivo.xlsx \
  --theme magenta --format all --top-antenas 15

# Entrada manual
python tzanalysis.py manual \
  --coord-lat LAT --coord-lon LON --name NOMBRE

# Configuración
python tzanalysis.py config show
python tzanalysis.py config themes

# Modo interactivo
python tzanalysis.py process --input archivo.xlsx
```

### Formatos de Fecha/Hora

```bash
--date-start 2025-10-29        # YYYY-MM-DD
--date-end 2025-10-31          # YYYY-MM-DD  
--hour-start 08:30             # HH:MM
--hour-end 17:45               # HH:MM
```

### Temas Más Usados

```bash
--theme magenta    # Forense, alto contraste
--theme cyan       # Técnico, azul brillante
--theme red        # Alertas, crítico
--theme yellow     # Alta visibilidad
```

---

## 🆘 Soporte y Troubleshooting

### Problemas Comunes

1. **CLI no funciona**: Verificar Python path y dependencias
2. **Errores de archivo**: Usar `validate` primero
3. **Salida incorrecta**: Verificar permisos directorio
4. **Columnas no reconocidas**: Revisar estructura Excel/TSV

### Obtener Ayuda

```bash
# Help general
python tzanalysis.py --help

# Help específico por comando  
python tzanalysis.py run --help
python tzanalysis.py validate --help
python tzanalysis.py manual --help
python tzanalysis.py config --help

# Información diagnóstico
python tzanalysis.py info --verbose

# Modo debug
python tzanalysis.py --verbose --log-level debug [COMANDO]
```

---

**TZ Analyzer CLI v1.0.2** - Herramienta profesional para análisis forense de bitácoras telefónicas.

*Desarrollado durante Sprint 3B | 29 octubre 2025*