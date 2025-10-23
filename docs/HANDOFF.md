# Handoff y guía de entorno

Este documento es la bitácora de comunicación y relevo entre sesiones/equipos. Úsalo para: qué cambió, cómo continuar, comandos, rama activa, y próximos pasos.

## Objetivo rápido
- Poner a punto el entorno en Windows (PowerShell) y ejecutar el proyecto.
- Dejar un rastro claro de lo que se hizo y lo que sigue.

## Requisitos del entorno
- Windows 10/11
- Python 3.12.x instalado en el sistema
- PowerShell (predeterminado)
- Git configurado (con acceso al repo)
- Conexión a Internet (Leaflet y el plugin de calor se cargan vía CDN en los reportes HTML)

Nota: si en tu laptop personal no tienes Python 3.12 instalado, las instrucciones más abajo incluyen una ruta de fallback para Python 3.11. Ajusta la versión (`py -3.12` → `py -3.11`) según lo que tengas disponible.

## Configuración rápida (PowerShell)
> Ejecuta todo desde la raíz del repo (ajusta la ruta a tu equipo): por ejemplo `c:\Users\Omar Arias\OneDrive - mail.utec.edu.sv\Documentos\GitHub\TZ-Analysis-1.0.0`.

```powershell
# 1) Verifica Python 3.12
py -3.12 --version

# Si no tienes 3.12, intenta 3.11 como fallback:
# py -3.11 --version

# 2) Crea el entorno virtual
py -3.12 -m venv .venv312

# 3) Activa el entorno virtual
.\.venv312\Scripts\Activate.ps1
# Si tu política de ejecución lo bloquea temporalmente:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4) Actualiza pip y dependencias
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si prefieres automatizar estos pasos, en la raíz del repo hay un script `setup.ps1` que intenta usar Python 3.12 y cae a 3.11 si es necesario. Ejecuta `.
setup.ps1` desde PowerShell (con permisos de ejecución para el proceso) para crear/activar el venv e instalar dependencias.

## Sincronización de código (rama activa)
```powershell
git fetch --all
# Rama de trabajo actual
git checkout exploracion-movilidad
# Trae últimos cambios
git pull
```

## Ejecución y verificación rápida
```powershell
# Opción A: script principal
python script_principal_bitacoras_refactory.py

# Opción B: runner si aplica
python run.py
```
- Salida esperada: generación del reporte HTML (con índice, secciones de antenas, "Mapa de calor de actividad" con pines Top, y "Contactos").
- Nota: el mapa usa Leaflet + heatlayer desde CDN; requiere Internet para que se vean las teselas/capas.

## Estructura y archivos clave
- `script_principal_bitacoras_refactory.py`: genera el reporte HTML y artefactos.
- `config.json`: branding/texto legal del reporte.
- `requirements.txt`: dependencias de Python.
- `docs/`: documentación del proyecto.

## Bitácora de relevo (plantilla)
Copia y pega este bloque en cada pase de relevo.

```
[FECHA y HORA]
Contexto: ¿qué se hizo en este bloque?
Cambios relevantes: ramas, archivos, secciones HTML afectadas.
Cómo probar: comandos ejecutados, datos usados, resultado esperado.
Pendientes inmediatos: bullets cortos.
Riesgos/Notas: observaciones, TODOs, decisiones tomadas.
Responsable: nombre/alias.
```

Por favor, incluir siempre estos campos cuando se haga un relevo:
- Rama/Branch: (ej. `exploracion-movilidad`)
- Commit SHA (corto): (ej. `a1b2c3d`) — permite identificar el estado exacto del repo.

## Próximo paso prioritario
- Historial de cambios de antena:
  - Extraer secuencia de saltos (origen → destino, timestamp, distancia) desde el DataFrame principal, orden cronológico.
  - Generar bloque HTML con encabezado, nota explicativa y tabla; insertar tras las tablas de antenas.
  - Validar que no rompe el índice ni el orden actual (debe quedar después de "Antenas más activadas"/heatmap y antes de "Contactos", según decisión final).

## Solución de problemas
- Activación del venv bloqueada por políticas:
  - Usar: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y reintentar activar.
- Dependencias que faltan:
  - Ejecuta de nuevo `pip install -r requirements.txt` con el venv activo.
- Mapas no se ven:
  - Verifica conexión a Internet (Leaflet/teselas/heat se cargan por CDN).

---
Documento vivo. Mantén este archivo actualizado en cada relevo.

## Registro corto de la sesión (para el siguiente relevo)

[FECHA: 2025-10-22]
- Responsable: sesión con asistente VSCode (local)
- Acciones realizadas:
  - Añadido `setup.ps1` para crear/activar `.venv312` e instalar dependencias.
  - Añadida `.vscode/settings.json` apuntando al intérprete del venv.
  - Agregado script `tools/move_ip_backup.ps1` para mover restos `~ip*` a `.venv312\site-packages-backup`.
  - Movidos `~ip` y `~ip-24.3.1.dist-info` al backup y verificado que `pip list` y `pip check` no reportan problemas.
- Pendientes/no logrados:
  - No se ejecutó la suite de tests completa con `pytest` (pytest no estaba instalado en el venv local). Se recomienda instalar `pytest` localmente si se quiere CI local.
  - No se automatizó la interacción completa de `run.py` (el script es interactivo y requiere respuestas de usuario para color, modo, intervalo, etc.).
- Recomendaciones para proteger/reproducir el proyecto (mínimo y al grano):
  1) Mantener `requirements.txt` y además generar/commitear `requirements.lock` (output de `pip freeze`) para reproducibilidad exacta.
  2) Añadir `tools/move_ip_backup.ps1` a la documentación y usarlo antes de borrar venvs; mejor mover que borrar sin revisar.
  3) Evitar ubicar el repo en carpetas con sincronización automática (OneDrive/Dropbox) para evitar ficheros temporales en `site-packages` y contenciones de I/O; si se queda en OneDrive, documentar la política de exclusión o usar una copia local para venvs.
  4) Incluir `python -m pip install pytest` como paso de verificación en `setup.ps1` o un `dev-requirements.txt` para pruebas.
  5) Documentar en HANDOFF.md cómo ejecutar `run.py` en modo no interactivo (si existe flag) o proveer un runner `run_noninteractive.py` con valores por defecto para CI.
  6) Añadir un simple `check_env.ps1` que compruebe presencia de `.venv312`, `python.exe` e `requirements.lock` y falle con código de salida si falta algo (útil para CI).

Si quieres, pongo estos cambios en un commit y doy instrucciones rápidas para que el otro asistente los recoja.

---

## Sesión 2025-10-22 (Noche) - Mapas dinámicos por día

**Responsable:** GitHub Copilot (Claude Sonnet 3.5)  
**Rama:** `exploracion-movilidad`  
**Archivos principales modificados:** `script_principal_bitacoras_refactory.py`

### ✅ Acciones completadas:

1. **Mini-mapas por día implementados**
   - Agregados mapas Leaflet después de las tablas de contactos de cada día
   - Cada mapa muestra TODAS las antenas únicas activadas ese día
   - Iconos mejorados (📍 de 28px con bordes blancos y sombra)
   - Popup informativo con nombre de antena, activaciones y coordenadas
   - Márgenes laterales (max-width: 95%, padding: 0 20px)

2. **Optimización de Leaflet**
   - Dependencias de Leaflet movidas al `<head>` del HTML (carga única)
   - Eliminadas dependencias duplicadas del mapa principal de calor
   - CSS agregado para clase `.map-notice`

3. **Logging y debug mejorado**
   - Agregado logging detallado de antenas mapeadas por día
   - Console.log en JavaScript para verificar marcadores agregados
   - Logs muestran: registros procesados, antenas únicas, nombre y coordenadas

4. **Análisis del problema de discrepancia tabla vs mapa**
   - **IDENTIFICADO:** La tabla muestra "antena top por contacto" (más frecuente)
   - **IDENTIFICADO:** El mapa muestra "todas las antenas del día" (todas las interacciones)
   - Esto genera confusión cuando un contacto tiene múltiples antenas
   - Ejemplo: Contacto con 5 llamadas (3 desde Antena A, 2 desde Antena B)
     - Tabla: Muestra "Antena A" (es el top)
     - Mapa: Muestra ambas antenas A y B

### 🎯 Decisión tomada: OPCIÓN 2 - Rediseño con pestañas

**Qué mantener sin cambios:**
- Header/Logo/Metadata
- Resumen General
- Indicadores
- Top Contactos (ranking global del período)
- Top Antenas (ranking global del período)
- Mapa de calor de actividad (el grande, con todas las antenas del período)
- Antenas por rango horario
- Todos los contactos (lista completa al final)

**Qué rediseñar:**
- Sección "Interacciones de los últimos días registrados en bitácora"
- Nueva estructura por día con 3 pestañas:
  1. **📊 Resumen:** Alertas + tabla de antenas del día
  2. **👥 Contactos:** Lista expandible por contacto con detalles de cada interacción
  3. **📍 Antenas:** Lista expandible por antena con registros
- Mapa dinámico que responde a la pestaña activa y a las expansiones

### 📋 Pendientes inmediatos:

1. **Diseñar UX del sistema de pestañas** (DECISIÓN NECESARIA)
   - Límite de días por defecto: ¿5, 10, todos?
   - Columnas en tabla expandida: Hora, Tipo, Duración, Antena, Lat, Lon, Azimut, ¿Dirección?
   - Esquema de colores/tema
   - Comportamiento del mapa dinámico al cambiar pestañas
   - Navegación entre días si hay muchos (paginación, selector)

2. **Implementar Fase 1: Estructura de pestañas**
   - HTML/CSS/JS para las 3 pestañas por día
   - Lógica de mostrar/ocultar contenido según pestaña activa
   - Tabla de antenas para pestaña Resumen
   - Listas expandibles para Contactos y Antenas

3. **Implementar Fase 2: Mapa dinámico**
   - Mapa responde a pestaña activa
   - Filtrado de antenas al expandir contacto
   - Zoom a antena al expandir en vista Antenas
   - Posible: líneas conectando antenas si hay movimiento

4. **Implementar Fase 3: Navegación y filtros**
   - Selector de día
   - Paginación inteligente (si > 10 días)
   - Optimización de performance

### 🔧 Código clave modificado:

**Función:** `_construir_seccion_interacciones_recientes()` en `script_principal_bitacoras_refactory.py`

**Sección del mini-mapa** (líneas ~2840-2945):
```python
def render_heatmap_html_for_day(df_day, day_id):
    # Agrupa antenas por (lat, lon, nombre)
    # Genera marcadores con popups informativos
    # Retorna HTML con div del mapa + script JavaScript
```

**Ubicación:** El mapa se genera DESPUÉS de:
- Tabla de contactos del día
- Alertas de concentración/movilidad/calidad

### ⚠️ Notas importantes:

1. **El comportamiento actual es técnicamente correcto** pero puede confundir:
   - El mapa muestra toda la información disponible (todas las antenas)
   - La tabla resume por contacto (solo antena más frecuente)
   - Ambas vistas son válidas pero sirven propósitos diferentes

2. **Sistema de pestañas propuesto solucionará la confusión:**
   - Vista Resumen: Para análisis rápido del día
   - Vista Contactos: Para análisis de comunicaciones (enfoque en QUIÉN)
   - Vista Antenas: Para análisis de movilidad (enfoque en DÓNDE)
   - Mapa dinámico: Se adapta a la vista activa

3. **Performance:** Con muchos días, considerar:
   - Lazy loading de días no visibles
   - Límite por defecto (ej: últimos 5 días)
   - Opción de "cargar más" o paginación

### 🎨 Propuesta de diseño (acordada con usuario):

```
┌─────────────────────────────────────────────┐
│ 📅 ANÁLISIS DIARIO                          │
│ 🔍 [Filtro: Todos ▼] [26/03] [27/03] ...   │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ 27/03/2022 (Viernes)                    │ │
│ │ Interacciones: 8 | Duración: 00:56:44   │ │
│ │                                         │ │
│ │ [📊 Resumen] [👥 Contactos] [📍 Antenas]│ │
│ │ ┌─────────────────────────────────────┐ │ │
│ │ │ Contenido según pestaña             │ │ │
│ │ └─────────────────────────────────────┘ │ │
│ │ 🗺️ Mapa Dinámico                        │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 📚 Referencias útiles:

- **Leaflet docs:** https://leafletjs.com/
- **Leaflet.heat plugin:** https://github.com/Leaflet/Leaflet.heat
- **Función validadora de coordenadas:** `_es_valida_latlon()` y `_es_valida_latlon_row()`
- **Función antena top:** `_antena_top(gr)` - devuelve antena más frecuente de un grupo

### 🚀 Para continuar en próxima sesión:

1. Decidir detalles de UX (límites, columnas, colores)
2. Crear mockup HTML estático de una pestaña para validar diseño
3. Implementar lógica de cambio de pestañas
4. Conectar mapa dinámico con eventos de pestañas
5. Probar con dataset real de múltiples días

### ✉️ Mensaje para el siguiente asistente:

El usuario quiere mejorar la claridad del reporte. Hemos identificado que la discrepancia entre tabla (resumen por contacto) y mapa (todas las antenas) genera confusión. La solución acordada es implementar un sistema de pestañas que ofrezca múltiples perspectivas de los datos. Todo el análisis está documentado en esta sesión. El código actual funciona bien, solo falta implementar el nuevo diseño.

---
