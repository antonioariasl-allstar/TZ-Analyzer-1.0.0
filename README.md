# 🛰️ TZ Analyzer — Forensic Data Processor

**Procesador forense de bitácoras telefónicas y motor integral de análisis, correlación y generación de productos forenses.**

Su propósito es apoyar investigaciones técnicas bajo el marco legal, priorizando precisión, trazabilidad y facilidad de interpretación.

---

## ⚠️ Estado actual del proyecto (Agosto 2026)

**✅ Sistema completamente funcional.** TZ Analyzer genera correctamente informes HTML, archivos KMZ para Google Earth y hashes de integridad.

**✅ Cerrado en v1.1:** P0-B (clasificación de contactos), patrón Versión B (omisión silenciosa en secciones HTML) y módulo KMZ (implementación completa y revisión visual aprobada).

### Consolidación completada (v1.0.0-consolidada)

El proyecto pasó por un proceso de consolidación y modularización que transformó un monolito de **2,344 líneas** en una arquitectura modular con un orquestador de **~825 líneas** y **46 módulos** en el paquete `tz_core/`.

La generación HTML fue descompuesta en submódulos dedicados dentro de `tz_core/html/`: assembler, kpi, contacts, antennas, metadata y header.

**Resultado:**
- **Suite automatizada** unitaria, de integración y E2E; criterio de release: 0 fallos
- **0 regresiones** durante todo el proceso
- Monolito reducido un **65%** (de 2,344 a ~825 líneas)
- Metodología atómica: analizar → planificar → ejecutar → test → commit

### Nota de alcance

La confiabilidad del sistema está validada para **bitácoras del formato salvadoreño** sobre el cual fue desarrollado. El procesamiento de formatos de otras operadoras o países puede producir resultados incorrectos sin advertencia. Esta es una limitación de alcance conocida, no un fallo arquitectural.

---

## ⚙️ Características principales

- **Wizard de mapeo interactivo**: Detecta automáticamente las columnas del archivo Excel y permite mapear manualmente campos esenciales (teléfono, fecha, hora, latitud, longitud, azimut) y no esenciales (alias, usuario, abonado, IMEI, contacto, interacción, duración, etc.).

- **Tolerancia y flexibilidad**: Soporta múltiples formatos de fecha/hora (serial Excel, ISO, dd/mm/yyyy), maneja coordenadas fuera de rango, normaliza texto (mojibake, abreviaturas) y permite remapear campos individuales sin reiniciar.

- **Generación de KML/KMZ** para visualización en Google Earth:
  - Carpeta global con todas las antenas.
  - Subcarpetas cronológicas por fecha con numeración secuencial (`001 — YYYY-MM-DD`) y tratamiento separado para registros sin fecha; dentro de ellas, activaciones numeradas (`0001 — HH:MM:SS — antena`). Carpeta `⚠ LEA PRIMERO` con parámetros y advertencias. ScreenOverlay permanente de representación orientativa. Rango horario (madrugada, mañana, tarde, noche).
  - Deduplicación de puntos por (antena, lat, lon) con resumen de azimuts.
  - Líneas de azimut y conos de orientación configurables.
  - Top N de antenas y contactos más activados.

- **Informes HTML**:
  - Resumen general de actividad con metadatos (alias, usuario, abonado, IMSI, IMEI).
  - Tablas de frecuencia por antena, contacto y período temporal.
  - Sección de interacciones y análisis de todos los contactos.
  - Marca de agua y pie legal configurables para confidencialidad.

- **Configuración avanzada** mediante `config.json`:
  - Estilos y colores (paleta sugerida, HEX manual, escala de íconos, opacidad).
  - Sinónimos de columnas para detectar automáticamente variantes.
  - Rangos horarios personalizables.
  - Branding (logo, marca de agua, pie legal).

- **Suite de pruebas**: pruebas unitarias, de integración y E2E con golden files que validan estructura KMZ, generación HTML e integridad del pipeline completo.

---

## 🧱 Estructura del proyecto

```
TZ-Analyzer/
├── script_principal_bitacoras_refactory.py  # Orquestador principal (~825 líneas)
├── run.py                                   # Entry point alternativo
├── config.json                              # Configuración global (estilos, branding, sinónimos)
│
├── tz_core/                                 # Paquete principal (46 módulos)
│   ├── analytics.py                         # Análisis forense y estadísticas
│   ├── app_runner.py                        # Punto de entrada de la aplicación
│   ├── bitacora_io.py                       # Lectura/escritura de bitácoras
│   ├── bitacora_normalization.py            # Normalización de datos de bitácora
│   ├── bitacora_utils.py                    # Utilidades de bitácora
│   ├── color_utils.py                       # Manejo de colores y paletas
│   ├── config_loader.py                     # Carga de configuración
│   ├── config_manager.py                    # Gestión avanzada de configuración
│   ├── data_loader.py                       # Carga de datos Excel
│   ├── dataframe_utils.py                   # Utilidades de DataFrames
│   ├── file_utils.py                        # Gestión de archivos y rutas
│   ├── format_utils.py                      # Formateo de datos
│   ├── geo_utils.py                         # Utilidades geográficas
│   ├── health_utils.py                      # Verificación de salud del sistema
│   ├── html_helpers.py                      # Helpers de construcción HTML
│   ├── html_toc.py                          # Tabla de contenidos HTML
│   ├── ingestion_pipeline.py                # Pipeline de ingesta de datos
│   ├── interacciones_builder.py             # Constructor de sección de interacciones
│   ├── kml_generator.py                     # Generación de KML/KMZ
│   ├── logging_utils.py                     # Sistema de logging centralizado
│   ├── manual_flow.py                       # Flujo de regeneración HTML manual
│   ├── manual_mapping_helpers.py            # Helpers de mapeo manual
│   ├── manual_mode.py                       # Modo manual de operación
│   ├── mapping_wizard.py                    # Wizard de mapeo interactivo
│   ├── output_flow.py                       # Flujo de salida
│   ├── output_pipeline.py                   # Pipeline de generación de productos
│   ├── output_runner.py                     # Ejecutor de pipeline de salida
│   ├── qc_engine.py                         # Motor de control de calidad
│   ├── qc_type_classifier.py                # Clasificador de tipos para QC
│   ├── runtime_utils.py                     # Utilidades de runtime
│   ├── schema_guard.py                      # Guardia de esquema de datos
│   ├── schema_utils.py                      # Utilidades de esquema
│   ├── synonym_utils.py                     # Manejo de sinónimos de columnas
│   ├── text_utils.py                        # Procesamiento de texto
│   ├── time_filters.py                      # Filtros temporales
│   ├── time_utils.py                        # Utilidades de tiempo y fecha
│   ├── types.py                             # Definiciones de tipos
│   ├── ui_utils.py                          # Interfaz de usuario (consola)
│   ├── utils.py                             # Utilidades generales
│   ├── validation_utils.py                  # Validaciones y normalización
│   ├── assets/
│   │   ├── Logo TZ.png                      # Legacy — ya no es dependencia activa
│   │   └── branding/                        # Ubicación canónica de identidad visual (Fase 2)
│   │       ├── TZ_Analyzer_icono_app.png        # Header, portada, AYUDA (pequeño); futuro icono .exe
│   │       ├── TZ_Analyzer_isotipo_principal.png # AYUDA "Acerca de", informe HTML (espacio suficiente)
│   │       └── TZ_Analyzer_logo_horizontal.png   # Disponible; sin uso forzado en espacios pequeños
│   └── html/                                # Submódulos de generación HTML
│       ├── assembler.py                     # Ensamblador del informe completo
│       ├── antennas.py                      # Sección de antenas
│       ├── contacts.py                      # Sección de contactos
│       ├── header.py                        # Encabezado del informe
│       ├── kpi.py                           # KPIs y métricas principales
│       └── metadata.py                      # Metadatos del sujeto
│
├── tz_io/                                   # Entrada/salida de archivos
│   └── file_io.py
│
├── tz_services/                             # Servicios externos
│   └── geo_tools.py                         # Herramientas geográficas
│
├── tz_cli_click/                            # CLI alternativo (Click)
│   └── commands/
│       └── info_backup.py
│
├── tests/                                   # Suite de pruebas unitaria, integración y E2E
│   ├── integration/                         # Tests E2E y de integración
│   │   ├── test_e2e_regresion.py            # Regresión E2E con golden files
│   │   ├── test_hour_ranges_flow.py         # Flujo de rangos horarios
│   │   ├── test_manual_flow_option1.py      # Flujo manual opción 1
│   │   └── test_p0b_pipeline.py             # Pipeline P0-B clasificación de contactos
│   ├── unit/                                # Tests unitarios por módulo (20+ archivos)
│   ├── helpers/                             # Helpers de testing
│   ├── golden/                              # Golden files para validación
│   ├── normalize_outputs.py                 # Normalización de outputs para tests
│   └── update_golden.py                     # Actualización de golden files
│
└── tools/                                   # Herramientas de desarrollo
    ├── analisis_dependencias.py             # Análisis de dependencias entre módulos
    ├── auditar_codigo_muerto.py             # Detección de código muerto
    ├── capture_golden_baseline.py           # Captura de baseline para golden tests
    ├── investigacion_forense.py             # Herramientas de investigación
    └── run_baseline_correct.py              # Ejecución de baseline correcta
```

---

## 🏗️ Arquitectura

El sistema sigue una arquitectura modular con un orquestador central:

```
script_principal (orquestador)
    │
    ├── ingestion_pipeline      → Carga Excel, wizard de mapeo, normalización
    │     ├── data_loader
    │     ├── mapping_wizard
    │     ├── bitacora_normalization
    │     └── schema_utils
    │
    ├── output_pipeline         → Generación de productos forenses
    │     ├── tz_core/html/     → Informe HTML (assembler + submódulos)
    │     ├── kml_generator     → KML/KMZ para Google Earth
    │     └── output_runner
    │
    ├── manual_flow             → Regeneración manual de HTML
    │
    └── módulos de soporte
          ├── config_manager    → Configuración global
          ├── logging_utils     → Logging centralizado
          ├── analytics         → Análisis forense
          ├── time_utils        → Manejo de fechas/horas
          ├── validation_utils  → Normalización defensiva
          └── ...
```

**Principio clave:** El monolito (`script_principal`) actúa exclusivamente como orquestador. Toda la lógica de negocio reside en los módulos de `tz_core/`.

---

## 🚀 Guía rápida de uso

### Requisitos

- **CPython 3.12.8 x64 exacto** (contrato de desarrollo y build de v1)
- **Entrada Excel soportada**: `.xlsx`
- **Dependencias runtime**: `requirements.txt`
- **Dependencias de pruebas**: `requirements-test.txt`

El usuario de la aplicación empaquetada no tendrá que instalar Python. Este
contrato aplica únicamente al desarrollo, las pruebas y la construcción de la
release.

### Instalación

```powershell
# Opción recomendada: valida versión/arquitectura y prepara .venv312
.\setup.ps1
```

Preparación manual equivalente:

```powershell
# Validar implementación, versión y plataforma antes de continuar
py -3.12-64 -c "import platform, struct, sys, sysconfig; assert platform.python_implementation() == 'CPython' and sys.version_info[:3] == (3, 12, 8) and struct.calcsize('P') * 8 == 64 and sysconfig.get_platform() == 'win-amd64'"
if ($LASTEXITCODE -ne 0) { throw "Se requiere CPython 3.12.8 x64 (win-amd64)" }

# La recreación debe partir de una ruta nueva; no se borra ningún entorno automáticamente
if (Test-Path -LiteralPath '.\.venv312') { throw "Retire manualmente .venv312 antes de recrear el entorno" }

# Crear entorno virtual limpio con el intérprete canónico
py -3.12-64 -m venv .venv312

# Activar entorno virtual (Windows PowerShell)
.\.venv312\Scripts\Activate.ps1

# Instalar runtime y tooling de pruebas con versiones exactas
.\.venv312\Scripts\python.exe -m pip install --upgrade pip==24.3.1
.\.venv312\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv312\Scripts\python.exe -m pip check
```

### Ejecución

```powershell
.\.venv312\Scripts\python.exe script_principal_bitacoras_refactory.py
```

1. **Seleccionar color tema** (opcional) — Paleta sugerida o HEX manual.
2. **Seleccionar archivo Excel** — Diálogo gráfico (Tkinter) o ruta por consola.
3. **Mapeo interactivo de columnas** — Asignar campos esenciales y no esenciales.
4. **Filtros y opciones** — Filtrar por día, rango de días, rango de horas, Top N.
5. **Seleccionar carpeta de salida** — Se generan KML/KMZ, informe HTML y hashes.

### Pruebas

```powershell
# Suite web
.\.venv312\Scripts\python.exe -m pytest tests/web -q

# Suite completa: criterio de release = 0 fallos
.\.venv312\Scripts\python.exe -m pytest -q

# Test E2E con golden files
.\.venv312\Scripts\python.exe -m pytest tests/integration/test_e2e_regresion.py -q
```

El detalle del contrato reproducible está en
[`docs/RELEASE_ENVIRONMENT.md`](docs/RELEASE_ENVIRONMENT.md). El golden KML se
compara por semántica XML canónica, no por diferencias léxicas equivalentes de
serialización.

---

## 🔧 Configuración avanzada

El archivo `config.json` permite ajustar:

- **Estilos KML**: color tema, escala de íconos, ancho de línea, opacidad de conos.
- **Branding**: logo, marca de agua, pie legal.
- **Sinónimos de columnas**: mapeo automático de variantes.
- **Rangos horarios**: personalización de madrugada, mañana, tarde, noche.
- **Top N**: cantidad de antenas y contactos a destacar.

---

## 🧠 Filosofía de desarrollo

TZ Analyzer busca **reducir el tiempo de procesamiento** y **eliminar errores humanos** en la interpretación de registros técnicos, ofreciendo una interfaz sencilla, un resultado visual verificable y una arquitectura modular que facilita el mantenimiento y la extensión.

> "Cada línea procesada debe poder explicarse."
> — *Principio central del desarrollo TZ Analyzer*

### Principios clave

- **Tolerancia a errores**: El programa sigue funcionando ante datos incompletos o formatos inesperados.
- **Trazabilidad**: Cada decisión (mapeo, normalización, filtro) se registra y se puede auditar.
- **Modularidad**: Cada módulo tiene una responsabilidad clara y documentada.
- **Configurabilidad**: Los estilos, sinónimos y rangos horarios se ajustan sin tocar el código.
- **Metodología atómica**: Analizar → planificar → ejecutar → test → commit. Sin commits antes de testing manual.

---

## 🚧 Pendientes conocidos

- Generalización de formatos para operadoras de otros países (v1.2+)
- Pendientes funcionales menores del wizard: F2 y F3
- Ajustes cosméticos no bloqueantes: F5-UX y F8
- Mejoras al informe HTML (más interpretativo y forenses defensible)
- Exportación a IBM i2 / Gephi
- Manual técnico en PDF
- Empaquetado ejecutable (PyInstaller)

---

## 🔒 Notas de confidencialidad

> Proyecto con fines investigativos y de análisis forense.
> La divulgación o uso indebido de los informes podría violar normativa vigente.

---

## 🧾 Licencia

© 2025–2026 — *Desarrollo interno por Tony Zero (Omar Arias)*.
Distribución o reproducción no autorizada **prohibida**.
