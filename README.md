# 🛰️ TZ Analysis v1.0.0

**Procesador forense de bitácoras telefónicas**, diseñado para analizar registros de comunicación, generar informes HTML y representaciones geográficas en KML/KMZ.  
Su propósito es apoyar investigaciones técnicas bajo el marco legal, priorizando precisión, trazabilidad y facilidad de interpretación.

---

## ⚙️ Características principales

- ✅ **Lectura automatizada** de archivos Excel (`.xlsx`) con detección de columnas esenciales (teléfono, fecha, hora, latitud, longitud, azimut).  
- 🧭 **Generación de KML/KMZ** para visualización en Google Earth:
  - Carpeta global de antenas.
  - Subcarpetas por rango horario (mañana, tarde, noche, madrugada).
  - Top de antenas y contactos más activados.
- 📊 **Informes HTML**:
  - Resumen general de actividad.
  - Tablas de frecuencia, ubicación y períodos.
  - Metadatos de usuario (alias, abonado, IMSI, IMEI si aplica).
- 🧩 **Configuración flexible** mediante `config.json` (rangos horarios, sinónimos, estilos, branding, etc.).
- 🧱 **Arquitectura modular**:
  - `script_principal_bitacoras_refactory.py` → flujo principal.
  - `utilidades.py` → funciones auxiliares.
  - `validaciones.py` → verificación de datos.
  - `kml_generador.py` → motor de exportación geográfica.

---

## 🧭 Estructura del proyecto

TZ_Analysis_1.0.0/
│
├── config.json
├── script_principal_bitacoras_refactory.py
├── utilidades.py
├── validaciones.py
├── kml_generador.py
├── logo_tz.png
├── README.md
└── .gitignore

---

## 🧠 Filosofía de desarrollo

TZ Analysis busca **reducir el tiempo de procesamiento** y **eliminar errores humanos** en la interpretación de registros técnicos, ofreciendo una interfaz sencilla y un resultado visual verificable.

> “Cada línea procesada debe poder explicarse.”  
> — *Principio central del desarrollo TZ Analysis*

---

## 🚧 Estado del proyecto

Versión **1.0.0** — Fase de consolidación técnica.  
- [x] Motor de lectura Excel estable  
- [x] Generación KML y HTML funcional  
- [ ] Previsualización antes del guardado  
- [ ] Exportación a IBM i2 / Gephi  
- [ ] Asistente GUI (versión 2.0 planificada)  
- [ ] Manual técnico y empaquetado ejecutable

---

## 🔒 Notas de confidencialidad

> Proyecto con fines investigativos y de análisis forense.  
> La divulgación o uso indebido de los informes podría violar normativa vigente.

---

## 🧾 Licencia

© 2025 — *Desarrollo interno por Tony Zero*.  
Distribución o reproducción no autorizada **prohibida**.
