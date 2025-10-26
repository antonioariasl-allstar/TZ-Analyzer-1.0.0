# 🛰️ TZ Analyzer – Forensic Data Processor

**Procesador forense de bitácoras telefónicas y motor integral de análisis, correlación y generación de productos forenses.**

Su propósito es apoyar investigaciones técnicas bajo el marco legal, priorizando precisión, trazabilidad y facilidad de interpretación.

---

## ⚙️ Características principales

- ✅ **Wizard de mapeo interactivo**: Detecta automáticamente las columnas del archivo Excel y permite mapear manualmente campos esenciales (teléfono, fecha, hora, latitud, longitud, azimut) y no esenciales (alias, usuario, abonado, IMEI, contacto, interacción, duración, etc.).
- 🔄 **Tolerancia y flexibilidad**: Soporta múltiples formatos de fecha/hora (serial Excel, ISO, dd/mm/yyyy), maneja coordenadas fuera de rango, normaliza texto (mojibake, abreviaturas) y permite remapear campos individuales sin reiniciar.
- 🧭 **Generación de KML/KMZ** para visualización en Google Earth:
  - Carpeta global con todas las antenas.
  - Subcarpetas por fecha (día del año + fecha ISO).
  - Subcarpetas por rango horario (madrugada, mañana, tarde, noche).
  - Deduplicación de puntos por (antena, lat, lon) con resumen de azimuts.
  - Líneas de azimut y conos de orientación configurables.
  - Top N de antenas y contactos más activados.
- 📊 **Informes HTML**:
  - Resumen general de actividad con metadatos (alias, usuario, abonado, IMSI, IMEI).
  - Tablas de frecuencia por antena, contacto y período temporal.
  - Marca de agua y pie legal configurables para confidencialidad.
- 🧩 **Configuración avanzada** mediante `config.json`:
  - Estilos y colores (paleta sugerida, HEX manual, escala de íconos, opacidad).
  - Sinónimos de columnas para detectar automáticamente variantes (aprende de mapeos previos).
  - Rangos horarios personalizables.
  - Branding (logo, marca de agua, pie legal).
- 🧪 **Pruebas de regresión**: Test automatizado que valida la estructura del KMZ (carpetas, azimuts, conos) para blindar cambios futuros.
- 🧱 **Arquitectura modular y documentada**:
  - `script_principal_bitacoras_refactory.py` → Flujo principal y orquestación.
  - `utilidades.py` → Selección de archivos/carpetas (Tkinter + fallback consola).
  - `validaciones.py` → Normalización defensiva de fecha/hora/coordenadas/azimut.
  - `kml_generador.py` → Generador de puntos libres (modo manual).
  - `tests/test_e2e_regresion.py` → Tests E2E y validación de estructura KMZ.

---

## 🧭 Estructura del proyecto

```
TZ-Analyzer/
│
├── config.json                            # Configuración global (estilos, branding, sinónimos)
├── script_principal_bitacoras_refactory.py  # Flujo principal y orquestación
├── utilidades.py                          # Selección de archivos/carpetas
├── validaciones.py                        # Normalización y validación
├── kml_generador.py                       # Generador de puntos libres
├── logo_tz.png                            # Logo para branding
├── README.md                              # Este archivo
├── TODO.md                                # Tareas y observaciones
├── .gitignore                             # Archivos excluidos del repo
└── tests/
    └── test_e2e_regresion.py              # Tests E2E y validación KMZ
    └── unit/                              # Tests unitarios por componente
```

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
1. **Ejecutar el script principal**:
   ```bash
   python script_principal_bitacoras_refactory.py
   ```

2. **Seleccionar color tema** (opcional):
   - Elegí un color de la paleta sugerida (1-N) o ingresá un HEX manual (#RRGGBB).
   - Si omitís, se usa el color predeterminado de `config.json`.

3. **Seleccionar archivo Excel**:
   - Se abre un diálogo gráfico (Tkinter).
   - Si no está disponible, se pide la ruta por consola.

4. **Mapeo interactivo de columnas**:
   - El wizard muestra las columnas disponibles y te pide asignar campos esenciales (tel, lat, long, fecha, hora, azimut) y no esenciales (alias, usuario, abonado, IMEI, contacto o destino, interacción o tipo, etc.).
   - Podés omitir columnas, asignar valores fijos o remapear individualmente después.

5. **Filtros y opciones**:
   - Filtrar por día específico, rango de días o rango de horas.
   - Seleccionar Top N de antenas y contactos.
   - Ingresar alias, usuario y abonado si no están en el archivo.

6. **Seleccionar carpeta de salida**:
   - Se abre un diálogo gráfico (Tkinter).
   - Si no está disponible, se pide la ruta por consola.

7. **Generación**:
   - Se crean los archivos KML/KMZ, informe HTML y archivo de errores (si corresponde).
   - Los resultados se guardan en la carpeta de salida con timestamp.

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

---

## 🚧 Estado del proyecto

Versión **1.0.0** — Fase de consolidación técnica.

### Completado ✅
- [x] Motor de lectura Excel con detección automática y mapeo interactivo
- [x] Wizard de mapeo tolerante con remapeo individual
- [x] Normalización defensiva de fecha/hora/coordenadas/azimut
- [x] Generación KML/KMZ con carpetas por fecha y rango horario
- [x] Deduplicación de puntos con resumen de azimuts
- [x] Informes HTML con metadatos y branding
- [x] Configuración flexible mediante `config.json`
- [x] Pruebas de regresión para estructura KMZ
- [x] Documentación completa (docstrings, comentarios, README)

### Pendiente 🔜
- [ ] Previsualización antes del guardado
- [ ] Exportación a IBM i2 / Gephi
- [ ] Asistente GUI (versión 2.0 planificada)
- [ ] Manual técnico en PDF
- [ ] Empaquetado ejecutable (PyInstaller)

---

## 🧪 Pruebas

Para ejecutar las pruebas de regresión:

```bash
# Tests E2E completos con validación golden
python tests/test_e2e_regresion.py

# Tests unitarios por componente
python -m pytest tests/unit/
```

Los tests validan estructura KMZ, generación HTML y integridad del pipeline completo.

---

## 🔧 Configuración avanzada

El archivo `config.json` permite ajustar:

- **Estilos KML**: color tema, escala de íconos, ancho de línea, opacidad de conos.
- **Branding**: logo, marca de agua, pie legal.
- **Sinónimos de columnas**: mapeo automático de variantes (aprende de ejecuciones previas).
- **Rangos horarios**: personalización de madrugada, mañana, tarde, noche.
- **Top N**: cantidad de antenas y contactos a destacar en el KML.

Ejemplo de sección `style`:

```json
"style": {
  "theme_hex": "#ff00ff",
  "pin_scale": 1.1,
  "line_width": 5,
  "cone_opacity": 0.35,
  "palette": [
    ["Magenta", "#ff00ff"],
    ["Verde", "#00ff00"],
    ["Azul", "#0000ff"]
  ]
}
```

---

## 🔒 Notas de confidencialidad

> Proyecto con fines investigativos y de análisis forense.  
> La divulgación o uso indebido de los informes podría violar normativa vigente.

---

## 🧾 Licencia

© 2025 — *Desarrollo interno por Tony Zero (Omar Arias)*.  
Distribución o reproducción no autorizada **prohibida**.
