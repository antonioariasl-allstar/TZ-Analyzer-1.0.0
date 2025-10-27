# ❓ Preguntas Frecuentes (FAQ) - TZ Analyzer

---

## 📥 Instalación

### ¿Qué versión de Python necesito?
**Python 3.12.8** específicamente. El proyecto ha sido probado y optimizado para esta versión.

### ¿Puedo usar Python 3.11 o 3.13?
No recomendado. Pueden aparecer incompatibilidades con las dependencias. Usa 3.12.8.

### ¿Funciona en Windows 7?
No oficialmente. Windows 10/11 son los sistemas soportados.

---

## 📂 Archivos y Formatos

### ¿Qué formato de Excel acepta?
- `.xlsx` (recomendado)
- `.xls` (soportado)

### ¿Puedo usar archivos CSV?
Sí, pero debes usar el "Modo Manual" (opción 3 del menú). Para análisis completo, convierte CSV a Excel primero.

### ¿Cuál es el tamaño máximo de archivo?
No hay límite técnico, pero archivos > 100MB pueden tardar varios minutos en procesarse.

### ¿El Excel debe tener una estructura específica?
Sí, debe tener:
- Una fila de encabezados
- Columnas para: teléfono, fecha, hora, latitud, longitud, azimut
- Sin celdas combinadas
- Sin filas vacías entre los datos

---

## 🗺️ Coordenadas y Mapeo

### ¿Qué rango de coordenadas es válido?
- **Latitud**: -90° a 90°
- **Longitud**: -180° a 180°

### ¿Qué formato de coordenadas acepta?
- Decimal: `13.6929, -89.2182` (recomendado)
- El sistema NO acepta grados/minutos/segundos directamente

### ¿Qué es el azimut y es obligatorio?
El azimut es la dirección de la antena (0-360 grados). **Es obligatorio** para generar las visualizaciones de dirección en Google Earth.

### Las coordenadas de mi Excel están en formato de texto, ¿funcionará?
Sí, el sistema las convierte automáticamente. Asegúrate de que usen punto (.) como separador decimal.

---

## 📅 Fechas y Horas

### ¿Qué formatos de fecha acepta?
- `dd/mm/yyyy` (recomendado)
- `yyyy-mm-dd` (ISO)
- Serial de Excel (se convierte automáticamente)

### ¿Y formatos de hora?
- `HH:MM:SS` (24 horas)
- `HH:MM`
- Serial de Excel (tiempo fraccional)

### ¿Qué zona horaria usa?
Por defecto: **America/El_Salvador** (GMT-6). Se puede configurar en `config.json`.

---

## 🎨 Visualización

### ¿Por qué no aparece el mapa de calor en el HTML?
Necesitas **conexión a Internet** la primera vez para cargar las librerías de Leaflet.js.

### Los íconos en Google Earth son muy pequeños, ¿cómo los agrando?
Edita `config.json`:
```json
{
  "style": {
    "pin_scale": 1.5  ← Aumentar valor (default: 1.1)
  }
}
```

### ¿Puedo cambiar el color de los íconos?
Sí, al inicio del programa te pregunta el color. También puedes editarlo en `config.json`:
```json
{
  "style": {
    "theme_hex": "#00ff00"  ← Verde
  }
}
```

---

## 🔧 Configuración

### ¿Dónde está el archivo de configuración?
`config.json` en la raíz del proyecto.

### ¿Qué pasa si borro `config.json`?
El sistema generará uno nuevo con valores por defecto al ejecutarse.

### ¿Puedo agregar mi propio logo?
Sí, coloca tu imagen y edita `config.json`:
```json
{
  "brand": {
    "logo_path": "mi_logo.png"
  }
}
```

---

## 📊 Procesamiento

### ¿Cuánto tarda en procesar una bitácora?
Depende del tamaño:
- 1,000 registros: ~10 segundos
- 10,000 registros: ~1 minuto
- 100,000 registros: ~10 minutos

### El programa se quedó congelado, ¿qué hago?
Probablemente esté procesando. Si es un archivo grande, dale tiempo. Si pasan más de 30 minutos, presiona `Ctrl+C` para cancelar.

### ¿Puedo procesar múltiples bitácoras a la vez?
No simultáneamente. Pero puedes procesarlas una tras otra en la misma sesión.

---

## ❌ Errores Comunes

### Error: "No module named 'pandas'"
**Solución**:
```bash
# Asegúrate de tener el entorno virtual activado
pip install -r requirements.txt
```

### Error: "No se encontraron registros válidos"
**Causas posibles**:
1. Coordenadas fuera de rango
2. Formato de fecha incorrecto
3. Columnas mapeadas incorrectamente

**Solución**: Revisa el archivo `errores_*.txt` en la carpeta de salida.

### Error: "Permission denied" al guardar archivos
**Causa**: No tienes permisos en la carpeta de destino  
**Solución**: Elige una carpeta donde tengas permisos de escritura

### El KMZ no se abre en Google Earth
**Causas posibles**:
1. Archivo corrupto
2. Google Earth no instalado
3. Extensión .kmz cambiada

**Solución**: 
- Reinstala Google Earth Pro
- Verifica que el archivo termine en `.kmz`
- Intenta regenerar el KMZ

### Los puntos no aparecen en el mapa
**Causas posibles**:
1. Coordenadas invertidas (lat/lon)
2. Coordenadas fuera del rango esperado

**Solución**: Verifica el mapeo de columnas (lat ≠ lon)

---

## 🔄 Actualización y Sincronización

### ¿Cómo actualizo a la última versión?
```bash
git pull origin main
pip install -r requirements.txt
```

### Trabajo en casa y en la oficina, ¿cómo sincronizo?
Lee la [Estrategia de Sincronización](../development/ESTRATEGIA_SYNC.md).

### ¿Perderé mis cambios al actualizar?
No si usas Git correctamente. Haz `git stash` antes de actualizar.

---

## 🧪 Testing

### ¿Cómo sé si mi instalación funciona correctamente?
```bash
python tests/test_e2e_regresion.py
```
Todos los tests deben pasar (PASSED).

### ¿Hay datos de prueba?
Sí, en `tests/data/bitacora_test.tsv.xlsx`.

---

## 📁 Archivos de Salida

### ¿Qué es el archivo de hashes?
Contiene SHA-256 de los archivos generados para verificar integridad. Úsalo para demostrar que los archivos no han sido modificados.

### ¿Para qué sirve el archivo de errores?
Lista los registros que no pudieron procesarse (coordenadas inválidas, fechas mal formateadas, etc.).

### ¿Puedo borrar los archivos `.kml` si ya tengo el `.kmz`?
Sí, el `.kmz` es un `.kml` comprimido. El `.kml` sin comprimir es solo para debugging.

---

## 🛡️ Seguridad y Privacidad

### ¿Los datos se envían a algún servidor?
**NO**. Todo el procesamiento es local. Solo se requiere internet para cargar librerías de mapas en el HTML.

### ¿Se guardan mis datos en algún lado?
Solo en la carpeta de salida que tú selecciones. Nada se guarda en la nube ni se envía a terceros.

### ¿Puedo usar esto en entorno sin internet?
Sí para el procesamiento. No para ver los mapas interactivos del HTML (necesitan Leaflet.js).

---

## 🔧 Personalización

### ¿Puedo cambiar los rangos horarios (madrugada, mañana, etc.)?
Sí, edita `config.json`:
```json
{
  "rango_horario": {
    "madrugada": [0, 6],
    "mañana": [6, 12],
    "tarde": [12, 18],
    "noche": [18, 24]
  }
}
```

### ¿Puedo agregar nuevos campos al mapeo?
Técnicamente sí, pero requiere modificar el código fuente. No recomendado sin experiencia en Python.

---

## 🐛 Reportar Problemas

### ¿Cómo reporto un bug?
1. Ve a [GitHub Issues](https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0/issues)
2. Haz clic en "New Issue"
3. Incluye:
   - Descripción del problema
   - Pasos para reproducirlo
   - Mensaje de error completo
   - Versión de Python
   - Sistema operativo

### ¿Qué información debo incluir en un reporte?
```
Sistema: Windows 11
Python: 3.12.8
Versión TZ: 1.0.0
Error: [copiar mensaje completo]
Pasos:
1. ...
2. ...
```

---

## 💡 Mejores Prácticas

### ¿Cuál es el flujo de trabajo recomendado?
1. Preparar Excel con estructura correcta
2. Verificar coordenadas y fechas
3. Probar con una muestra pequeña primero
4. Procesar bitácora completa
5. Verificar resultados en Google Earth e HTML

### ¿Debo guardar los archivos de configuración?
Sí, especialmente `config.json` si lo personalizaste.

### ¿Con qué frecuencia debo actualizar?
Verifica actualizaciones semanalmente. Lee el `TODO.md` para ver nuevas features.

---

## 📞 Contacto

### ¿Dónde puedo conseguir soporte?
1. Lee esta documentación
2. Consulta [GitHub Issues](https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0/issues)
3. Crea un nuevo issue si tu problema no está documentado

### ¿Puedo contribuir al proyecto?
Sí, lee [Principios de Desarrollo](../development/PRINCIPIOS_DESARROLLO_PROFESIONAL.md) y envía Pull Requests.

---

**Última actualización**: 27 de octubre de 2025
