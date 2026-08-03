# ESPECIFICACION_KMZ_ANTENAS_ACTIVACIONES_v1_1.md

**TZ Analyzer — Especificación de diseño**
**Módulo: KMZ — Estructura de antenas y activaciones**
**Estado: CERRADA — lista para implementación**
**Fecha: Agosto 2026**
**Autores: Tony (Omar Arias) + Claude + GPT**

---

## 1. Alcance

Este documento especifica el comportamiento del módulo KMZ de TZ Analyzer
para la representación de antenas y activaciones. Cubre ordenamiento, numeración,
estructura de carpetas en Google Earth, representación geométrica y advertencias.

No cubre: cálculo de cobertura real, simulación radioeléctrica, clasificación
automática de entorno urbano/rural.

---

## 2. Decisiones de diseño cerradas

### 2.1 Ordenamiento cronológico

**Regla:** TZ Analyzer construirá una columna interna de fecha-hora normalizada
antes de generar el KMZ. Todas las activaciones se ordenarán cronológicamente
por esa columna.

El orden original del archivo Excel **no** determina el orden del KMZ.

**Desempate en timestamps iguales:** cuando dos o más registros tienen exactamente
el mismo timestamp, el criterio de desempate es el orden de fila original del
archivo entregado por la operadora. Fundamento pericial: es un hecho del caso,
no una decisión del sistema.

**Secuencia de construcción obligatoria:**
```
1. Construir fecha-hora normalizada
2. Ordenar por fecha-hora normalizada
3. Aplicar desempate por fila original cuando corresponda
4. Asignar numeración de días y activaciones
5. Generar carpetas del KMZ
```

---

### 2.2 Numeración y padding

**Numeración de días:** secuencial global en orden cronológico.

**Numeración de activaciones:** secuencial global en orden cronológico,
independiente del día. Una activación del día 2 tiene un número mayor que
cualquier activación del día 1.

**Padding dinámico:** el ancho del número se determina a partir del total
antes de asignar la numeración.

```python
# Días
padding_dias = len(str(total_dias))
numero_dia = str(n).zfill(padding_dias)

# Activaciones
padding_act = len(str(total_activaciones))
numero_act = str(n).zfill(padding_act)
```

Esto evita que Google Earth ordene `10` antes que `9` por comparación
alfabética en bitácoras grandes.

---

### 2.3 Estructura de carpetas en el KMZ

```
📁 Todas las antenas
  📁 001 — 2026-05-10
    📁 0001 — 14:32:05 — ANT-39512
      📍 Pin (antena)
      ⭕ Círculo de referencia
      🔺 Sector 120°          [solo si existe azimut]
      ➡ Línea de azimut      [solo si existe azimut]
    📁 0002 — 15:45:12 — ANT-40123
      ...
  📁 002 — 2026-05-11
    📁 0003 — 08:10:44 — ANT-39512
      ...
```

**Nombre de carpeta de activación:** `{numero} — {hora} — {id_antena}`

**Las carpetas de días y activaciones estarán cerradas por defecto** en Google
Earth para evitar saturación visual en bitácoras grandes. Las geometrías estarán
activas pero no expandidas en el panel lateral.

---

### 2.4 Descripción de cada activación

Cada carpeta de activación incluirá una descripción con:

```
Activación global: 0001
Fecha y hora: 2026-05-10 14:32:05
Antena: ANT-39512
Azimut: 90°                    [omitir si no hay azimut]
Radio gráfico: 1 km
Apertura: 120°                 [omitir si no hay azimut]

Representación orientativa. No delimita la cobertura real
ni determina la ubicación exacta del terminal.
```

---

### 2.5 Representación geométrica

**Cuando existe azimut:**
- Pin de antena
- Círculo de referencia
- Cono sectorial de 120° centrado en el azimut (azimut ± 60°)
- Línea central del azimut

**Cuando no existe azimut:**
- Pin de antena
- Círculo de referencia únicamente

No se generará un cono con azimut inventado o por defecto cuando el dato
no está presente en la bitácora.

**Regla de distancia:** círculo, cono y línea de azimut terminan a la
**misma distancia** desde la antena. No existe separación entre el borde
del cono y el límite del círculo. Una línea de azimut que sobresale del
cono implicaría una segunda estimación de cobertura.

---

### 2.6 Parámetros de radio gráfico

| Parámetro | Valor |
|---|---|
| Predeterminado | 1 km |
| Presets disponibles | 1 km / 3 km / 5 km / personalizado |
| Apertura nominal | 120° (fija) |
| Origen del valor | predeterminado / manual / dato de operadora |

El radio gráfico no representa cobertura real. Se denomina explícitamente
**radio gráfico** en todas las advertencias.

Si la operadora proporciona datos técnicos reales (apertura, distancia),
esos valores prevalecen sobre los predeterminados y deben registrarse como
origen en los metadatos.

---

### 2.7 Estilo visual

| Elemento | Estilo |
|---|---|
| Círculo | borde fino, sin relleno o transparencia muy alta |
| Cono | relleno al 40 % de opacidad |
| Línea de azimut | sólida |
| Pin | estándar |
| Color | mismo color para todos los elementos de la misma bitácora |

---

### 2.8 Advertencias en el KMZ

**Nivel 1 — ScreenOverlay permanente:**
Visible en una esquina mientras se visualiza el KMZ. Se incluye en cualquier
captura de pantalla.

```
REPRESENTACIÓN ORIENTATIVA
Apertura: 120° | Radio gráfico: 1 km
No representa cobertura real ni ubicación exacta del terminal.
```

**Nivel 2 — Carpeta "LEA PRIMERO":**
Primera carpeta del panel lateral. Al seleccionarla muestra:
- parámetros usados (radio, apertura, origen del valor)
- qué significa el círculo
- qué significa el cono cuando existe
- aviso de que la distancia es gráfica, no de cobertura

**Nivel 3 — Descripción de cada activación:**
Ver sección 2.4. Incluye advertencia breve en cada elemento.

---

### 2.9 Rendimiento en bitácoras grandes

**Carpetas cerradas por defecto:**
Cada `<Folder>` de día y cada `<Folder>` de activación debe incluir `<open>0</open>`.
Es comportamiento estándar de la especificación KML, compatible con Google Earth
desktop y visores KML/KMZ.

```xml
<Folder>
  <name>001 — 2026-05-10</name>
  <open>0</open>
  ...
</Folder>
```

**Umbral de advertencia:**
- Umbral inicial: 300 activaciones.
- Efecto: advertencia no bloqueante al analista antes de generar el KMZ.
- Fundamento: una activación sin azimut produce 2 placemarks (pin + círculo);
  con azimut produce 4 (pin + círculo + cono + línea). A 300 activaciones el
  peor caso es 1,200 placemarks — dentro del límite cómodo para Google Earth.
- Ajustabilidad: el umbral es revisable mediante pruebas con bitácoras reales.
  No es un valor definitivo, es un punto de partida conservador.

**Versión futura:** opción de generar KMZ detallado (una carpeta por activación)
o KMZ compacto (sin subcarpetas por activación).

---

## 3. Lo que esta especificación NO incluye

- Código de implementación
- Instrucciones para Copilot
- Cálculo de cobertura real
- Clasificación automática urbano / periurbano / rural
- Detector de saltos atípicos (candidato a especificación separada)

---

## 4. Estado

| Elemento | Estado |
|---|---|
| Ordenamiento cronológico | ✅ Cerrado |
| Desempate por fila original | ✅ Cerrado |
| Numeración global post-ordenamiento | ✅ Cerrado |
| Padding dinámico | ✅ Cerrado |
| Estructura de carpetas (día + activación) | ✅ Cerrado |
| Círculo siempre | ✅ Cerrado |
| Cono y línea solo con azimut | ✅ Cerrado |
| Misma distancia para todos los elementos | ✅ Cerrado |
| Radio predeterminado 1 km con presets | ✅ Cerrado |
| Apertura fija 120° | ✅ Cerrado |
| Color por bitácora | ✅ Cerrado |
| Carpetas cerradas por defecto (`<open>0</open>`) | ✅ Cerrado |
| Umbral de advertencia (300 activaciones) | ✅ Cerrado |
| Advertencias (3 niveles) | ✅ Cerrado |
| Implementación | ⏸ Pendiente |
| Tests | ⏸ Pendiente |

---

## 5. Historial

| Fecha | Qué se decidió |
|---|---|
| Agosto 2026 | Diseño completo cerrado — Claude + GPT + Tony |
