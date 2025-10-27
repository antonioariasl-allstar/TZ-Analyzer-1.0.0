# 🚀 Guía de Uso Básico - TZ Analyzer

Esta guía te enseñará a usar TZ Analyzer paso a paso para procesar bitácoras telefónicas y generar reportes forenses.

---

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener:
- ✅ TZ Analyzer instalado ([Ver Guía de Instalación](GUIA_INSTALACION.md))
- ✅ Archivo Excel con bitácora telefónica
- ✅ Entorno virtual activado

---

## 🎯 Flujo de Trabajo Básico

```
1. Ejecutar programa
   ↓
2. Seleccionar archivo Excel
   ↓
3. Mapear columnas
   ↓
4. Configurar opciones
   ↓
5. Generar reportes
```

---

## 1️⃣ Iniciar el Programa

### Activar entorno virtual:

**Windows:**
```powershell
cd C:\ruta\al\proyecto\TZ-Analyzer-1.0.0
.venv312\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
cd ~/ruta/al/proyecto/TZ-Analyzer-1.0.0
source .venv312/bin/activate
```

### Ejecutar:
```bash
python script_principal_bitacoras_refactory.py
```

Verás el menú principal:
```
===============================================
           T  Z   A N A L Y Z E R
    Bitacoras -> KML/KMZ + Informe HTML
===============================================

Seleccione el modo de operación:
1. Modo Completo (todos los filtros disponibles)
2. Modo Solo Tiempo (filtrar por fecha/hora)
3. Modo Manual (generar puntos libres desde CSV)
0. Salir

Opción:
```

---

## 2️⃣ Seleccionar Archivo Excel

### Opción 1: Modo Completo (Recomendado)

Ingresa `1` y presiona Enter.

Se abrirá un diálogo para seleccionar tu archivo `.xlsx` o `.xls`.

**Formato esperado del Excel:**
```
| TELEFONO | FECHA      | HORA     | LATITUD  | LONGITUD | AZIMUT | ...
|----------|------------|----------|----------|----------|--------|----
| 555-1234 | 01/01/2025 | 14:30:00 | 13.6929  | -89.2182 | 45     | ...
| 555-1234 | 01/01/2025 | 15:00:00 | 13.7000  | -89.2200 | 90     | ...
```

---

## 3️⃣ Mapeo de Columnas

El sistema te mostrará las columnas disponibles en tu Excel:

```
Columnas detectadas en el archivo:
1. TELEFONO
2. FECHA_LLAMADA
3. HORA_LLAMADA
4. LAT
5. LON
6. AZIMUT
7. DESTINO
8. DURACION
...

Asigne las columnas esenciales:
```

### Campos Esenciales (Obligatorios):

```
Teléfono (columna): 1      ← Número de la columna TELEFONO
Fecha (columna): 2         ← Número de la columna FECHA
Hora (columna): 3          ← Número de la columna HORA
Latitud (columna): 4       ← Número de la columna LAT
Longitud (columna): 5      ← Número de la columna LON
Azimut (columna): 6        ← Número de la columna AZIMUT
```

### Campos Opcionales:

```
¿Mapear campos opcionales? (s/n): s

Alias (columna o fijo): ALIAS_SOSPECHOSO
Usuario (columna): 0       ← 0 = omitir
Abonado (columna): 0
IMEI (columna): 0
Contacto/Destino (columna): 7
Interacción/Tipo (columna): 0
Duración (columna): 8
```

**Tip**: Si un campo no existe en tu Excel, ingresa `0` para omitirlo.

---

## 4️⃣ Opciones de Filtrado

### A. Filtros Temporales

```
Seleccione filtro temporal:
1. Sin filtro (toda la bitácora)
2. Día específico
3. Rango de días
4. Rango de horas

Opción: 2

Ingrese día específico (dd/mm/yyyy): 15/10/2025
```

### B. Top N de Antenas y Contactos

```
¿Cuántas antenas top desea incluir? (0-50): 10
¿Cuántos contactos top desea incluir? (0-100): 20
```

---

## 5️⃣ Seleccionar Carpeta de Salida

Se abrirá un diálogo para seleccionar dónde guardar los resultados.

**Ejemplo**: `C:\Reportes\Caso_2025_10_15\`

---

## 6️⃣ Generación de Reportes

El sistema procesará los datos y generará:

```
Procesando datos...
✓ Datos validados: 1,250 registros
✓ Generando KML/KMZ...
✓ Generando informe HTML...
✓ Calculando hashes SHA-256...

Archivos generados:
📁 bitacora_2025_10_15_14h30m/
   ├── bitacora_2025_10_15_14h30m.kmz       ← Para Google Earth
   ├── bitacora_2025_10_15_14h30m.html      ← Informe HTML
   ├── hashes_bitacora_2025_10_15.txt       ← Integridad
   └── errores_bitacora_2025_10_15.txt      ← Errores (si hay)
```

---

## 🗺️ Ver Resultados en Google Earth

1. Abre **Google Earth Pro**
2. Archivo → Abrir → Selecciona el archivo `.kmz`
3. Navega por las carpetas:
   - **todas_las_antenas** - Todos los registros
   - **por_fecha** - Agrupados por día
   - **por_rango_horario** - Agrupados por horario
   - **top_N_las_mas_activadas** - Antenas principales

---

## 📊 Ver Informe HTML

1. Abre el archivo `.html` con cualquier navegador
2. Verás secciones:
   - Resumen general
   - Mapa de calor interactivo
   - Historial de cambios de antena
   - Tablas de frecuencia
   - Contactos más frecuentes

---

## 💡 Ejemplos de Uso Común

### Ejemplo 1: Análisis de un día específico

```
Opción: 1 (Modo Completo)
Filtro: 2 (Día específico)
Día: 20/10/2025
Top antenas: 5
Top contactos: 10
```

### Ejemplo 2: Análisis de horario nocturno

```
Opción: 2 (Modo Solo Tiempo)
Filtro: 4 (Rango de horas)
Desde: 22:00
Hasta: 06:00
```

### Ejemplo 3: Bitácora completa sin filtros

```
Opción: 1 (Modo Completo)
Filtro: 1 (Sin filtro)
Top antenas: 20
Top contactos: 50
```

---

## ⚙️ Configuración del Color Tema

Al inicio, puedes elegir un color para los íconos del KML:

```
Seleccione color de la paleta:
1. Magenta (#ff00ff)
2. Verde (#00ff00)
3. Azul (#0000ff)
4. Rojo (#ff0000)
5. Personalizado (ingrese código HEX)

Opción: 1
```

---

## 🔄 Procesamiento Múltiple

Después de procesar una bitácora, el menú pregunta:

```
¿Desea procesar otra bitácora? (s/n): s
```

Puedes procesar múltiples archivos en la misma sesión.

---

## 📁 Estructura de Salida

```
carpeta_salida/
└── bitacora_2025_10_15_14h30m/
    ├── bitacora_2025_10_15_14h30m.kmz
    │   ├── todas_las_antenas/
    │   ├── por_fecha/
    │   │   ├── 2025-10-01_Lun/
    │   │   ├── 2025-10-02_Mar/
    │   │   └── ...
    │   ├── por_rango_horario/
    │   │   ├── Madrugada (00-06h)/
    │   │   ├── Mañana (06-12h)/
    │   │   ├── Tarde (12-18h)/
    │   │   └── Noche (18-24h)/
    │   └── top_10_las_mas_activadas/
    │
    ├── bitacora_2025_10_15_14h30m.html
    ├── hashes_bitacora_2025_10_15.txt
    └── errores_bitacora_2025_10_15.txt (solo si hay errores)
```

---

## ⚠️ Puntos Importantes

### ✅ Hacer:
- Revisar que las columnas estén mapeadas correctamente
- Verificar coordenadas (latitud: -90 a 90, longitud: -180 a 180)
- Usar fechas consistentes en el Excel
- Guardar resultados en carpeta organizada

### ❌ Evitar:
- Archivos Excel con celdas combinadas
- Fechas en formatos inconsistentes
- Coordenadas fuera de rango
- Cerrar el programa mientras procesa

---

## 🐛 Errores Comunes

### "No se encontraron registros válidos"
**Causa**: Coordenadas fuera de rango o formato de fecha incorrecto  
**Solución**: Revisar el archivo `errores_*.txt` para detalles

### "Error al leer archivo Excel"
**Causa**: Archivo corrupto o con formato incorrecto  
**Solución**: Abrir y guardar de nuevo en Excel, verificar extensión

### "Columna no encontrada"
**Causa**: Mapeo incorrecto de columnas  
**Solución**: Verificar números de columna (empieza en 1, no en 0)

---

## 📞 ¿Necesitas Ayuda?

- 📖 Consulta el [FAQ](FAQ.md)
- 🐛 Reporta problemas en [GitHub Issues](https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0/issues)

---

## ➡️ Próximos Pasos

- Lee sobre [features avanzadas](../technical/features/) en la documentación técnica
- Explora la [configuración avanzada](../development/) del sistema
