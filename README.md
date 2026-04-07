# 🛰️ TZ Analyzer – Forensic Data Processor

**Procesador forense de bitácoras telefónicas y motor integral de análisis, correlación y generación de productos forenses.**

Su propósito es apoyar investigaciones técnicas bajo el marco legal, priorizando precisión, trazabilidad y facilidad de interpretación.

---

## 📚 Documentación

**Para documentación completa, consulta [docs/README.md](docs/README.md)**

### 📖 Para Usuarios

- **[Guía de Instalación](docs/user/GUIA_INSTALACION.md)** — Instalación paso a paso
- **[Guía de Uso Básico](docs/user/GUIA_USO_BASICO.md)** — Cómo usar el sistema
- **[Preguntas Frecuentes (FAQ)](docs/user/FAQ.md)** — Solución a problemas comunes

### 👨‍💻 Para Desarrolladores

- **🚨 [PROTOCOLO DE SINCRONIZACIÓN](docs/development/PROTOCOLO_SYNC_OBLIGATORIO.md)** — **⚠️ LEER ANTES DE CUALQUIER CAMBIO**
- **[Arquitectura del Sistema](docs/development/ARQUITECTURA_HIBRIDA_PERMANENTE.md)** — Diseño modular
- **[Principios de Desarrollo](docs/development/PRINCIPIOS_DESARROLLO_PROFESIONAL.md)** — Estándares de código
- **[Estrategia de Sincronización](docs/development/ESTRATEGIA_SYNC.md)** — Trabajo casa/oficina

---

## ⚠️ Estado actual del proyecto (Abril 2026)

**✅ Sistema completamente funcional.** TZ Analyzer genera correctamente informes HTML, archivos KMZ para Google Earth y hashes de integridad.

### Refactorización completada (Fase 1 + Fase 2)

El proyecto pasó por dos fases mayores de modularización que transformaron un monolito de **2,344 líneas** en una arquitectura modular con un orquestador de **~825 líneas** y **~40 módulos** en el paquete `tz_core/`.

**Fase 1** — Extracción de lógica de negocio del monolito hacia módulos independientes en `tz_core/`: utilidades de tiempo, validación, formato, HTML, archivos, DataFrames, configuración, carga de datos, analytics, logging, esquemas, normalización, UI, mapeo, KML, ingestion pipeline, entre otros.

**Fase 2** — Extracción completa de la generación HTML (`generar_informe_html`) al módulo `tz_core/html_generator.py` (3,460 líneas). Se eliminó el patrón wrapper del monolito; la pipeline de salida invoca directamente los módulos de generación.

**Resultado:**
- **250 tests** pasando (unitarios + integración + E2E), 2 skipped
- **0 regresiones** durante todo el proceso
- Monolito reducido un **65%** (de 2,344 a ~825 líneas)
- Metodología atómica: analizar → planificar → ejecutar → test → commit

### Bug conocido

El logo en el informe HTML aparece como texto raw (`<img src=.../>`) en lugar de renderizar la imagen. Es un bug preexistente (anterior a Fase 2) localizado en `build_logo_html()` dentro de `tz_core/html_generator.py`. Probable causa: el HTML del logo se está escapando en algún punto del template.

---

## ⚙️ Características principales

- **Wizard de mapeo interactivo**: Detecta automáticamente las columnas del archivo Excel y permite mapear manualmente campos esenciales (teléfono, fecha, hora, latitud, longitud, azimut) y no esenciales (alias, usuario, abonado, IMEI, contacto, interacción, duración, etc.).

- **Tolerancia y flexibilidad**: Soporta múltiples formatos de fecha/hora (serial Excel, ISO, dd/mm/yyyy), maneja coordenadas fuera de rango, normaliza texto (mojibake, abreviaturas) y permite remapear campos individuales sin reiniciar.

- **Generación de KML/KMZ** para visualización en Google Earth:
  - Carpeta global con todas las antenas.
  - Subcarpetas por fecha (día del año + fecha ISO) y rango horario (madrugada, mañana, tarde, noche).
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

- **Suite de pruebas**: 250 tests (unitarios, integración, E2E con golden files) que validan estructura KMZ, generación HTML e integridad del pipeline completo.

---

## 🧭 Estructura del proyecto

```
TZ-Analyzer/
├── script_principal_bitacoras_refactory.py  # Orquestador principal (~825 líneas)
├── utilidades.py                            # Selección de archivos/carpetas (Tkinter + consola)
├── validaciones.py                          # Normalización defensiva de fecha/hora/coordenadas
├── run.py                                   # Entry point alternativo
├── config.json                              # Configuración global (estilos, branding, sinónimos)
├── Logo TZ.png                              # Logo para branding
│
├── tz_core/                                 # Paquete principal (~40 módulos)
│   ├── analytics.py                         # Análisis forense y estadísticas
│   ├── app_runner.py                        # Punto de entrada de la aplicación
│   ├── bitacora_io.py                       # Lectura/escritura de bitácoras
│   ├── bitacora_normalization.py            # Normalización de datos de bitácora
│   ├── bitacora_utils.py                    # Utilidades de bitácora
│   ├── color_utils.py                       # Manejo de colores y paletas
│   ├── config_loader.py                     # Carga de configuración
│   ├── config_manager.py                    # Gestión avanzada de configuración
│   ├── data_loader.py                       # Carga de datos Excel
│   ├── data_normalizer.py                   # Normalización general de datos
│   ├── dataframe_utils.py                   # Utilidades de DataFrames
│   ├── file_utils.py                        # Gestión de archivos y rutas
│   ├── format_utils.py                      # Formateo de datos
│   ├── geo_utils.py                         # Utilidades geográficas
│   ├── health_utils.py                      # Verificación de salud del sistema
│   ├── html_generator.py                    # Generación completa de informes HTML (3,460 lín.)
│   ├── html_helpers.py                      # Helpers de construcción HTML
│   ├── html_toc.py                          # Tabla de contenidos HTML
│   ├── html_utils.py                        # Utilidades HTML generales
│   ├── ingestion_pipeline.py                # Pipeline de ingesta de datos
│   ├── interacciones_builder.py             # Constructor de sección de interacciones
│   ├── kml_generator.py                     # Generación de KML/KMZ
│   ├── logging_utils.py                     # Sistema de logging centralizado
│   ├── manual_flow.py                       # Flujo de generación HTML manual
│   ├── manual_mapping_helpers.py            # Helpers de mapeo manual
│   ├── manual_mode.py                       # Modo manual de operación
│   ├── mapping_wizard.py                    # Wizard de mapeo interactivo
│   ├── output_flow.py                       # Flujo de salida
│   ├── output_pipeline.py                   # Pipeline de generación de productos
│   ├── output_runner.py                     # Ejecutor de pipeline de salida
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
│   └── validation_utils.py                  # Validaciones y normalización
│
├── tz_io/                                   # Entrada/salida de archivos
│   └── file_io.py                           # Operaciones de archivo
│
├── tz_services/                             # Servicios externos
│   └── geo_tools.py                         # Herramientas geográficas
│
├── tests/                                   # Suite de pruebas (250 tests)
│   ├── integration/                         # Tests E2E y de integración
│   │   ├── test_e2e_regresion.py            # Regresión E2E con golden files
│   │   ├── test_hour_ranges_flow.py         # Flujo de rangos horarios
│   │   └── test_manual_flow_option1.py      # Flujo manual opción 1
│   ├── unit/                                # Tests unitarios por módulo
│   │   ├── test_html_generator.py
│   │   ├── test_output_pipeline.py
│   │   ├── test_manual_flow.py
│   │   └── ... (17 archivos de test)
│   ├── helpers/                             # Helpers de testing
│   ├── normalize_outputs.py                 # Normalización de outputs para tests
│   └── update_golden.py                     # Actualización de golden files
│
├── tools/                                   # Herramientas de desarrollo
│   ├── analisis_dependencias.py             # Análisis de dependencias entre módulos
│   ├── auditar_codigo_muerto.py             # Detección de código muerto
│   ├── capture_golden_baseline.py           # Captura de baseline para golden tests
│   ├── categorizar_funciones.py             # Categorización de funciones del monolito
│   ├── investigacion_forense.py             # Herramientas de investigación
│   └── run_baseline_correct.py              # Ejecución de baseline correcta
│
├── docs/                                    # Documentación del proyecto
│   ├── user/                                # Guías de usuario
│   ├── development/                         # Documentación de desarrollo
│   ├── technical/                           # Documentación técnica
│   ├── planning/                            # Planificación y diseño
│   ├── audits/                              # Auditorías de código
│   └── legacy/                              # Documentación histórica
│
└── .github/workflows/                       # CI/CD (GitHub Actions)
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
    │     ├── html_generator    → Informe HTML completo (3,460 lín.)
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

- **Python 3.12.8** (versión oficial del proyecto)
- **Dependencias**: Ver `requirements.txt`

### Instalación

```bash
# Crear entorno virtual (recomendado)
python -m venv .venv312

# Activar entorno virtual
# Windows:
.venv312\Scripts\activate
# Linux/Mac:
source .venv312/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### Ejecución

```bash
python script_principal_bitacoras_refactory.py
```

1. **Seleccionar color tema** (opcional) — Paleta sugerida o HEX manual.
2. **Seleccionar archivo Excel** — Diálogo gráfico (Tkinter) o ruta por consola.
3. **Mapeo interactivo de columnas** — Asignar campos esenciales y no esenciales.
4. **Filtros y opciones** — Filtrar por día, rango de días, rango de horas, Top N.
5. **Seleccionar carpeta de salida** — Se generan KML/KMZ, informe HTML y hashes.

---

## 🔧 Configuración avanzada

El archivo `config.json` permite ajustar:

- **Estilos KML**: color tema, escala de íconos, ancho de línea, opacidad de conos.
- **Branding**: logo, marca de agua, pie legal.
- **Sinónimos de columnas**: mapeo automático de variantes.
- **Rangos horarios**: personalización de madrugada, mañana, tarde, noche.
- **Top N**: cantidad de antenas y contactos a destacar.

---

## 🧪 Pruebas

```bash
# Suite completa (250 tests)
python -m pytest

# Solo tests unitarios
python -m pytest tests/unit/

# Solo tests de integración
python -m pytest tests/integration/

# Test E2E con golden files
python -m pytest tests/integration/test_e2e_regresion.py
```

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

## 🚧 Pendientes

- Corregir bug del logo en informe HTML (HTML escapado)
- Evaluar extracciones adicionales del monolito
- Previsualización antes del guardado
- Exportación a IBM i2 / Gephi
- Asistente GUI (versión 2.0 planificada)
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