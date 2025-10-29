# SPRINT 3B - CLI MODERNO CON CLICK FRAMEWORK

**FECHA INICIO**: 29 octubre 2025  
**ESTADO**: 🚧 EN DESARROLLO  
**OBJETIVO**: Interfaz línea comandos moderna complementaria al menú interactivo  

## 🎯 DIFERENCIACIÓN: CLI CLICK vs MENÚ INTERACTIVO

### **MENÚ INTERACTIVO** (Sprint 3A - YA COMPLETADO ✅)
```bash
python run.py
# Menú [1/2/3] → Wizard paso a paso → Selección manual
```

### **CLI CLICK** (Sprint 3B - ESTE SPRINT 🚧)
```bash
tzanalysis run --input bitacora.xlsx --top-antenas 10 --output results/
tzanalysis manual --coord-lat 40.4168 --coord-lon -3.7038 --radius 5km
tzanalysis process --file data.tsv --theme magenta --format kmz
tzanalysis validate --input archivo.xlsx --report validation.html
```

**🔗 COMPLEMENTARIOS**: Ambos enfoques coexisten para diferentes workflows

## 📋 ARQUITECTURA CLI CLICK DISEÑADA

### **COMANDOS PRINCIPALES:**

#### `tzanalysis process` (Interactivo simplificado)
```bash
tzanalysis process [--input FILE] [--interactive]
# Equivale al menú [1] pero con pre-configuración opcional
```

#### `tzanalysis run` (Programático directo)
```bash
tzanalysis run --input FILE [OPTIONS]
  --input FILE              Archivo Excel/TSV a procesar  
  --top-antenas N          Top N antenas (default: 10)
  --theme COLOR            Color tema (magenta, cyan, yellow...)
  --output DIR             Directorio salida
  --format FORMAT          kml|kmz|html|all (default: all)
  --time-filter TYPE       completo|dia|rango-dias|rango-horas
  --date-start DATE        Fecha inicio (si time-filter)
  --date-end DATE          Fecha fin (si time-filter)  
  --hour-start TIME        Hora inicio (si rango-horas)
  --hour-end TIME          Hora fin (si rango-horas)
  --sheet SHEET            Hoja Excel específica
  --quiet                  Sin output verbose
  --dry-run                Validar sin ejecutar
```

#### `tzanalysis manual` (Entrada coordenadas)
```bash
tzanalysis manual [OPTIONS]
  --coord-lat LAT          Latitud antena
  --coord-lon LON          Longitud antena  
  --name NAME              Nombre antena
  --add-multiple           Modo entrada múltiple
  --import-file FILE       Importar desde archivo
  --radius RADIUS          Radio cobertura (default: 1km)
  --theme COLOR            Color tema
  --output DIR             Directorio salida
```

#### `tzanalysis validate` (Validación archivos)
```bash
tzanalysis validate --input FILE [OPTIONS]
  --input FILE             Archivo a validar
  --report FILE            Reporte validación HTML
  --schema SCHEMA          Schema esperado (telefonico|antenas|custom)
  --fix-auto               Auto-fix problemas menores
  --verbose                Output detallado errores
```

#### `tzanalysis config` (Configuración)
```bash
tzanalysis config [SUBCOMMAND]
  show                     Mostrar configuración actual
  set KEY VALUE            Setear valor configuración
  reset                    Reset a defaults
  themes                   Listar temas disponibles
  export FILE              Exportar config a archivo
  import FILE              Importar config desde archivo
```

#### `tzanalysis info` (Información sistema)
```bash
tzanalysis info [--version] [--system] [--dependencies]
```

### **ESTRUCTURA MODULAR CLICK:**

```
tz_cli_click/
├── __init__.py              # Entry point principal Click
├── main.py                  # CLI group principal con Click
├── commands/
│   ├── __init__.py          # Registry comandos
│   ├── process.py           # tzanalysis process
│   ├── run.py               # tzanalysis run  
│   ├── manual.py            # tzanalysis manual
│   ├── validate.py          # tzanalysis validate
│   ├── config.py            # tzanalysis config
│   └── info.py              # tzanalysis info
├── options/
│   ├── __init__.py          # Common options
│   ├── common.py            # --input, --output, --theme
│   ├── time_filters.py      # --date-start, --time-filter
│   └── validation.py        # --schema, --fix-auto
├── handlers/
│   ├── __init__.py          # Business logic handlers
│   ├── file_processor.py    # File processing logic
│   ├── manual_processor.py  # Manual entry logic
│   ├── validator.py         # Validation logic
│   └── config_manager.py    # Config management
└── utils/
    ├── __init__.py          # Utilities
    ├── output.py            # Output formatting
    ├── errors.py            # Error handling
    └── helpers.py           # Common helpers
```

## 🔗 INTEGRACIÓN CON SISTEMA ACTUAL

### **COEXISTENCIA:**
- **Menú interactivo** (Sprint 3A): `python run.py` → Wizard paso a paso
- **CLI Click** (Sprint 3B): `tzanalysis run --input file.xlsx` → Directo

### **CÓDIGO COMPARTIDO:**
- **tz_core**: KML, heatmap generation (reutilizado)
- **script_principal**: Business logic core (reutilizado)
- **tz_cli**: Menu helpers disponibles (reutilizado si necesario)

### **ENTRY POINTS:**
```python
# setup.py
entry_points={
    'console_scripts': [
        'tzanalysis=tz_cli_click.main:cli',  # CLI Click
        'tz-run=run:main',                   # Menú interactivo
    ]
}
```

## 🎯 PLAN DE IMPLEMENTACIÓN

### **Sprint 3B.1 - Diseño y estructura base** 
- ✅ Documentación arquitectura (este archivo)
- ⏳ Crear estructura tz_cli_click/
- ⏳ Implementar CLI group base con Click
- ⏳ Common options y utilities base

### **Sprint 3B.2 - Comando `run` core**
- ⏳ tzanalysis run --input file.xlsx básico
- ⏳ Integración con monolito para procesamiento
- ⏳ Testing E2E comando run

### **Sprint 3B.3 - Comandos complementarios** 
- ⏳ tzanalysis validate
- ⏳ tzanalysis manual
- ⏳ tzanalysis config/info

### **Sprint 3B.4 - Testing y documentación**
- ⏳ Testing suite completa
- ⏳ Documentación usage y ejemplos
- ⏳ Integration testing con menú interactivo

## 🎬 EJEMPLOS USO ESPERADOS

### **Desarrollo/Testing:**
```bash
# Procesamiento rápido desarrollo
tzanalysis run --input test.xlsx --quiet --dry-run

# Validar formato antes procesar
tzanalysis validate --input data.xlsx --verbose

# Configurar tema personalizado  
tzanalysis config set theme.default magenta
```

### **Producción/Automation:**
```bash
# Batch processing
tzanalysis run --input batch/*.xlsx --output results/ --format kmz

# Pipeline automation
tzanalysis run --input daily_data.xlsx --theme cyan --top-antenas 20 \
  --time-filter rango-dias --date-start 2025-10-01 --date-end 2025-10-31
```

### **Análisis específico:**
```bash
# Entrada manual coordenadas
tzanalysis manual --coord-lat 40.4168 --coord-lon -3.7038 --name "Torre Madrid"

# Análisis horario específico
tzanalysis run --input calls.xlsx --time-filter rango-horas \
  --hour-start 09:00 --hour-end 17:00 --theme yellow
```

---

**DIFERENCIACIÓN CLAVE**: CLI Click es **programático/automation-friendly**, mientras menú interactivo es **wizard user-friendly**. Ambos valiosos para diferentes workflows.