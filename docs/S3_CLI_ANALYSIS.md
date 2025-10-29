# Sprint 3: Análisis CLI - Identificación de Comandos

**Fecha**: 29 de octubre de 2025  
**Sprint**: 3 - Interfaz CLI Modular  
**Fase**: 3.1 - Análisis CLI  
**Estado**: EN PROGRESO 🔄  

---

## 🎯 Comandos CLI Identificados

### Del `script_principal_bitacoras_refactory.py`

#### 1. **Comando Principal: `process`**
**Función origen:** `main()` - L5232  
**Descripción:** Procesar bitácora completa con menú interactivo  
**Sintaxis propuesta:** `tzanalysis process [archivo] [opciones]`

**Sub-comandos detectados:**
- `process full` - Opción [1] Procesar bitácora completa
- `process time` - Opción [2] Procesar por tiempo 
- `process manual` - Opción [3] Ingresar antenas manualmente

#### 2. **Comando Programático: `run`**
**Función origen:** `run_tz_analysis()` - L5037  
**Descripción:** Ejecución directa sin prompts (para GUI/scripts)  
**Sintaxis propuesta:** `tzanalysis run --input [archivo] --top-antenas [N] --top-contactos [N] [opciones]`

**Parámetros identificados:**
```python
ruta_entrada: str          # --input FILE
hoja: int|str|None         # --sheet NAME/NUMBER
top_antenas: int          # --top-antenas N  
top_contactos: int        # --top-contactos N
solo_kmz: bool            # --kmz-only
carpeta_salida: str|None  # --output-dir DIR
```

#### 3. **Comando Manual: `manual`**
**Función origen:** `_modo_manual()` - L4732  
**Descripción:** Entrada manual de antenas/puntos  
**Sintaxis propuesta:** `tzanalysis manual [opciones]`

**Flujo identificado:**
- [A] Agregar registro
- [L] Listar registros  
- [E] Eliminar registro
- [G] Graficar (generar KML/KMZ)
- [V] Volver (cancelar)

---

## 🏗️ Arquitectura CLI Propuesta

### Estructura `tz_cli/`

```
tz_cli/
├── __init__.py              # Entry point principal
├── main.py                  # CLI orchestrator con click/argparse
├── commands/                # Comandos modulares
│   ├── __init__.py
│   ├── process.py           # tzanalysis process [sub-comandos]
│   ├── run.py               # tzanalysis run [programático]
│   ├── manual.py            # tzanalysis manual [interactivo]
│   └── utils.py             # Comandos auxiliares
├── handlers/                # Business logic handlers
│   ├── __init__.py
│   ├── file_handler.py      # Selección y validación archivos
│   ├── config_handler.py    # Manejo configuración y temas
│   └── output_handler.py    # Generación y organización salidas
└── validators/              # Validadores input
    ├── __init__.py
    ├── file_validators.py   # Validación archivos entrada
    └── param_validators.py  # Validación parámetros
```

### Sintaxis CLI Target

```bash
# Comando principal interactivo (actual main())
tzanalysis process [archivo.xlsx]
tzanalysis process --file bitacora.xlsx --sheet 0 --theme blue

# Sub-comandos específicos  
tzanalysis process full --file bitacora.xlsx
tzanalysis process time --file bitacora.xlsx --days 3
tzanalysis process manual

# Comando programático (actual run_tz_analysis())
tzanalysis run --input bitacora.xlsx --top-antenas 10 --top-contactos 5 --output-dir ./output

# Comando manual puro
tzanalysis manual --name "caso_manual"

# Comandos auxiliares
tzanalysis config --show
tzanalysis config --theme [blue|green|red|rainbow]
tzanalysis validate --file bitacora.xlsx
```

---

## 📋 Mapeo Función → Comando

| Función Original | Comando CLI | Handler | Descripción |
|-----------------|-------------|---------|-------------|
| `main()` | `tzanalysis process` | `process.py` | Menú interactivo principal |
| `run_tz_analysis()` | `tzanalysis run` | `run.py` | Ejecución programática |
| `_modo_manual()` | `tzanalysis manual` | `manual.py` | Entrada manual antenas |
| `seleccionar_archivo()` | `--file FILE` | `file_handler.py` | Selección archivo entrada |
| `seleccionar_carpeta()` | `--output-dir DIR` | `output_handler.py` | Selección carpeta salida |
| `_solicitar_color_tema()` | `--theme COLOR` | `config_handler.py` | Configuración tema colores |
| `_solicitar_filtros_tiempo()` | `process time --days N` | `process.py` | Filtros temporales |

---

## 🔍 Dependencias Identificadas

### Imports Requeridos
```python
# CLI Framework
import click          # O argparse (más nativo)
import sys
import os
from pathlib import Path

# Funciones del monolito
from script_principal_bitacoras_refactory import (
    main,                    # Para process
    run_tz_analysis,        # Para run  
    _modo_manual,           # Para manual
    bootstrap_config        # Para inicialización
)

# Utilities modulares ya extraídas
from utilidades import seleccionar_archivo, seleccionar_carpeta
from tz_core.ui_utils import solicitar_overrides_topn
```

### Variables de Contexto Global
- `CONFIG`: Configuración global (colores, paths, schema)
- `LOG_FILE`: Archivo de logging activo
- `nombre_salida`: Nombre base archivos salida
- `hoja`: Hoja Excel seleccionada
- `archivo_errores`: Path archivo errores

---

## 🎛️ Parámetros CLI Detectados

### Comunes a Todos los Comandos
- `--config PATH`: Archivo config.json personalizado
- `--log-level [DEBUG|INFO|WARN|ERROR]`: Nivel logging
- `--output-dir DIR`: Directorio salida (override `seleccionar_carpeta()`)
- `--quiet`: Suprime output no esencial
- `--verbose`: Output detallado

### Específicos `process`
- `--file FILE`: Archivo entrada (override `seleccionar_archivo()`)
- `--sheet NAME|NUMBER`: Hoja Excel específica
- `--theme [blue|green|red|rainbow]`: Tema colores
- `--full`: Forzar modo completo (opción 1)
- `--time`: Forzar modo temporal (opción 2) 
- `--manual`: Forzar modo manual (opción 3)

### Específicos `run` (Programático)
- `--input FILE`: (requerido) Archivo entrada
- `--sheet NAME|NUMBER`: Hoja Excel
- `--top-antenas N`: Top N antenas (default: 10)
- `--top-contactos N`: Top N contactos (default: 5)
- `--kmz-only`: Solo generar KMZ (no HTML)
- `--output-name NAME`: Nombre base archivos salida

### Específicos `manual`
- `--name NAME`: Nombre caso manual
- `--interactive`: (default) Modo interactivo completo
- `--batch FILE`: Cargar registros desde archivo JSON/CSV

---

## 🚨 Riesgos y Consideraciones

### Riesgo 1: Variables Globales
**Descripción:** Script principal usa muchas variables globales (`CONFIG`, `LOG_FILE`, etc.)  
**Mitigación:** ✅ Crear context object o inyección dependencias  
**Estado:** PLANIFICADO

### Riesgo 2: Input Interactivo
**Descripción:** Funciones usan `input()` y `print()` directamente  
**Mitigación:** ✅ Abstraer con click prompts y echo  
**Estado:** PLANIFICADO

### Riesgo 3: Imports Circulares
**Descripción:** tz_cli importa script_principal que podría importar tz_cli  
**Mitigación:** ✅ CLI solo importa funciones específicas, no módulos completos  
**Estado:** MONITOREADO

### Riesgo 4: Exception Handling
**Descripción:** CLI necesita manejo robusto de errores para UX  
**Mitigación:** ✅ Wrapper try/catch con mensajes usuario-friendly  
**Estado:** PLANIFICADO

---

## ✅ Criterios de Éxito Sprint 3

### Fase 3.1: Análisis CLI ✅ COMPLETADA
- ✅ Comandos identificados: `process`, `run`, `manual`
- ✅ Parámetros mapeados desde funciones originales
- ✅ Estructura `tz_cli/` diseñada
- ✅ Dependencias y riesgos documentados

### Fase 3.2: Diseño CLI (SIGUIENTE)
- 🔄 Definir sintaxis exacta con click/argparse
- 🔄 Crear command registry pattern
- 🔄 Diseñar context object para variables globales
- 🔄 Prototipo help system contextual

### Fase 3.3: Implementación CLI (PENDIENTE)
- 🔄 Implementar `tz_cli/main.py` con entry point
- 🔄 Crear handlers modulares en `tz_cli/handlers/`
- 🔄 Integrar commands en `tz_cli/commands/`
- 🔄 Testing básico CLI end-to-end

### Fase 3.4: Validación CLI (PENDIENTE)
- 🔄 Testing argumentos y opciones
- 🔄 Validar help contextual y manejo errores
- 🔄 Verificar zero regressions vs script original
- 🔄 Documentación usuario final

---

## 🎯 Próximo Paso: Fase 3.2

**Objetivo:** Diseñar sintaxis CLI definitiva con framework seleccionado  
**Entregables:**
1. Definir click vs argparse
2. Crear command registry pattern  
3. Diseñar context object para estado global
4. Prototipo help system contextual

**Timeline:** Inmediato post-documentación Sprint 2B

---

**Sprint 3 Fase 3.1: Análisis CLI - COMPLETADO** ✅

*Continúa: Fase 3.2 - Diseño CLI*