# SPEC_OPERATIVA_KMZ_IMPLEMENTACION_v1_1.md

**TZ Analyzer — Spec operativa de implementación**
**Módulo:** `tz_core/kml_generator.py` + `tz_core/geo_utils.py`
**Estado:** v3 — APROBADA
**Fecha:** Agosto 2026
**Basado en:** `ESPECIFICACION_KMZ_ANTENAS_ACTIVACIONES_v1_1.md`
**Commit base:** `ddb11ff`
**Revisión GPT ronda 1:** Bloqueantes 1–5 incorporados. D1 cerrado. D2 cerrado.
**Revisión GPT ronda 2:** Correcciones C1 (sort), C2 (azimut NaN), C3 (ScreenOverlay) incorporadas. Tests fortalecidos.
**Estado de implementación:** IMPLEMENTADA — implementación y tests completos (agosto 2026).

---

## 0. Prerequisito: copiar specs al repo

```powershell
Copy-Item "<ruta>\ESPECIFICACION_KMZ_ANTENAS_ACTIVACIONES_v1_1.md" `
          "C:\TZ-Analyzer-1.0.0\docs\"
Copy-Item "<ruta>\SPEC_OPERATIVA_KMZ_IMPLEMENTACION_v1_1.md" `
          "C:\TZ-Analyzer-1.0.0\docs\"
git add docs/
git commit -m "docs: agregar especificacion cerrada KMZ y spec operativa de implementacion"
git push
```

---

## 1. Diagnóstico del estado actual

### geo_utils.py

| Función | Estado |
|---|---|
| `grados_a_radianes()` | ✅ Correcta |
| `calcular_punto_final(lat, lon, azimut, distancia_km)` → `(lat, lon)` | ✅ Correcta |
| `generar_cono()` | ⚠️ Legacy — no la llama kml_generator.py |
| Polígono circular | ❌ No existe — debe crearse |

### kml_generator.py — brechas vs spec (verificadas contra código)

| # | Brecha | Ubicación exacta | Severidad |
|---|---|---|---|
| B1 | Sort por string `"dd/mm/yyyy"`, no por datetime real | `sort_values(by=["fecha", "hora"])` | 🔴 Bug funcional |
| B2 | `_crear_feature_kml()` retorna sin dibujar nada si azimut es None/NaN — pin y círculo omitidos | Bloque "VALIDACIÓN DE AZIMUT" | 🔴 Viola spec |
| B3 | Círculo completamente ausente | `_crear_feature_kml()` — no existe lógica de círculo | 🔴 Viola spec |
| B4 | Sin subcarpeta por activación dentro de carpeta de fecha | Loop "Poblar todas_las_antenas" | 🟡 Estructura |
| B5 | Numeración de días usa día del año (`tm_yday`), no secuencial | `obtener_carpeta_fecha()` | 🟡 Estructura |
| B6 | Sin numeración global de activaciones | `generar_kml()` | 🟡 Estructura |
| B7 | Padding sin mínimos fijados — 9 activaciones → `"1"`, no `"0001"` | `generar_kml()` | 🟡 Estructura |
| B8 | `folder.open = 0` ausente en todas las carpetas | Todas las llamadas a `newfolder()` | 🟡 Visual |
| B9 | Carpeta "LEA PRIMERO" ausente | `generar_kml()` | 🟡 Advertencias |
| B10 | ScreenOverlay ausente | `generar_kml()` | 🟡 Advertencias |
| B11 | Advertencia no bloqueante > 300 activaciones ausente | `generar_kml()` | 🟢 Feature |
| B12 | Registros sin fecha no tienen carpeta destino — activación perdida | Loop "Poblar todas_las_antenas" | 🟡 Integridad |

### Decisiones cerradas

| # | Decisión | Resolución |
|---|---|---|
| D1 | Defaults radio y apertura | **1 km / 120° (cone_half = 60)**. Elimina contradicción código–diseño. |
| D2 | ScreenOverlay | **PNG estático en `tz_core/assets/kmz_aviso_orientativo.png`**, embebido en KMZ. Sin Pillow. Sin dependencias nuevas. |

---

## 2. Sub-fase 1: Nueva utilidad en geo_utils.py

**Archivo:** `tz_core/geo_utils.py`
**Tipo:** Adición pura
**Riesgo:** 🟢 Ninguno

Insertar después de `calcular_punto_final()`:

```python
def generar_coordenadas_circulo(
    lat: float,
    lon: float,
    radio_km: float,
    paso_grados: int = 5
) -> list:
    """Genera coordenadas de un polígono circular para KML.

    Llama a calcular_punto_final() en intervalos de paso_grados alrededor
    de 360° y cierra el polígono repitiendo el primer punto al final.

    Args:
        lat: Latitud del centro en grados decimales
        lon: Longitud del centro en grados decimales
        radio_km: Radio del círculo en kilómetros
        paso_grados: Resolución angular (default 5° → 72 vértices + cierre)

    Returns:
        list: Lista de tuplas (lon, lat) en formato simplekml.
              Con paso_grados=5: 73 elementos (72 vértices + 1 de cierre).
    """
    coords = []
    for angulo in range(0, 360, paso_grados):
        lat_p, lon_p = calcular_punto_final(lat, lon, float(angulo), radio_km)
        coords.append((lon_p, lat_p))
    coords.append(coords[0])  # cerrar el polígono
    return coords
```

Actualizar import en `kml_generator.py`:

```python
# Reemplaza: from tz_core.geo_utils import calcular_punto_final
from tz_core.geo_utils import calcular_punto_final, generar_coordenadas_circulo
```

**Commit:** `feat(geo_utils): agregar generar_coordenadas_circulo para circulos KML`

---

## 3. Sub-fase 2: Corrección de ordenamiento cronológico

**Archivo:** `tz_core/kml_generator.py` — función `generar_kml()`
**Tipo:** Bug fix (B1)
**Riesgo:** 🟢 Bajo

### Secuencia de cambios (orden es crítico)

El código actual tiene tres bloques separados: normalización de fecha, normalización de hora, sort.
La columna `_datetime_kml` debe construirse **después de ambas normalizaciones**.

**Paso A — Reemplazar el bloque de normalización de fecha:**

```python
# ANTES:
    if "fecha" in df.columns:
        try:
            df["fecha"] = parse_date_series(
                df["fecha"],
                dayfirst=True,
            ).dt.strftime("%d/%m/%Y")
            df["fecha"] = df["fecha"].fillna("Sin Inf.")
        except Exception:
            df["fecha"] = "Sin Inf."
    else:
        df["fecha"] = "Sin Inf."

# DESPUÉS:
    if "fecha" in df.columns:
        try:
            _dt_series = parse_date_series(df["fecha"], dayfirst=True)
            df["_dt_kml_fecha"] = _dt_series
        except Exception:
            df["_dt_kml_fecha"] = pd.NaT
        try:
            df["fecha"] = df["_dt_kml_fecha"].dt.strftime("%d/%m/%Y")
            df["fecha"] = df["fecha"].fillna("Sin Inf.")
        except Exception:
            df["fecha"] = "Sin Inf."
    else:
        df["_dt_kml_fecha"] = pd.NaT
        df["fecha"] = "Sin Inf."
```

**Paso B — Insertar después del bloque de normalización de hora** (después de `df["hora"] = horas_norm.where(...)`):

```python
    # Columnas auxiliares para ordenamiento cronológico robusto
    df["_fila_original"] = range(len(df))
    try:
        # Convertir hora a timedelta para comparación numérica
        # "Sin Inf." → NaT (registro sin hora queda al final de su día)
        df["_hora_kml_sort"] = pd.to_timedelta(
            df["hora"].replace("Sin Inf.", pd.NA),
            errors="coerce"
        )
        df["_hora_ausente"] = df["_hora_kml_sort"].isna()
    except Exception:
        df["_hora_kml_sort"] = pd.NaT
        df["_hora_ausente"] = True
```

**Paso C — Reemplazar el sort existente:**

```python
# ANTES:
    try:
        df = df.sort_values(by=["fecha", "hora"])
    except Exception:
        pass

# DESPUÉS:
    try:
        df = df.sort_values(
            by=["_dt_kml_fecha", "_hora_ausente", "_hora_kml_sort", "_fila_original"],
            kind="stable",
            na_position="last"
        )
    except Exception:
        pass
```

**Resultado del ordenamiento:**
- `_dt_kml_fecha`: fecha real cronológica (NaT va al final)
- `_hora_ausente`: `False` primero → registros con hora válida antes que los sin hora
- `_hora_kml_sort`: hora numérica dentro de cada fecha (NaT va al final de su día)
- `_fila_original`: desempate en timestamps idénticos respeta orden del Excel

**Criterios de aceptación:**
- `"02/12/2026"` y `"10/01/2026"` → `10/01/2026` sale primero en el KMZ
- Mismo timestamp → respetan orden de fila original del Excel
- Registro con fecha válida y hora ausente → aparece al final de ese día, no al final de toda la bitácora

**Commit:** `fix(kml_generator): ordenar activaciones por fecha y hora normalizadas`

---

## 4. Sub-fase 3: Reestructurar `_crear_feature_kml()`

**Archivo:** `tz_core/kml_generator.py`
**Tipo:** Refactor de lógica central (B2, B3, D1)
**Riesgo:** 🟡 Medio

### Alcance real del cambio

`_crear_feature_kml()` es llamada desde tres puntos dentro de `kml_generator.py`:
1. Modo flat
2. Poblar `todas_las_antenas` (a través de la subcarpeta de activación — Sub-fase 4)
3. `_crear_dedup()` — también afecta `top_N` y rangos horarios

**El círculo aparecerá en todos los usos.** Esto es correcto e intencional: la spec no restringe el círculo a ninguna carpeta específica.

### Verificar callers antes de tocar

```powershell
Select-String -Path "C:\TZ-Analyzer-1.0.0\tz_core\kml_generator.py" `
              -Pattern "_crear_feature_kml" -SimpleMatch
```

Resultado esperado: exactamente 3 coincidencias. `generar_kml_puntos_libres()` **no** llama a `_crear_feature_kml()` — sin riesgo allí.

### Cambio en `_REUSABLE_STYLES`

En el bloque `if _REUSABLE_STYLES is None:`, agregar `s_circle` antes de construir el dict:

```python
        # AGREGAR — estilo para círculo de referencia
        s_circle = sk.Style()
        s_circle.polystyle.color = hex_to_kml_color(theme_hex, 30)
        s_circle.polystyle.fill = 1
        s_circle.polystyle.outline = 1
        s_circle.linestyle.color = hex_to_kml_color(theme_hex, 200)
        s_circle.linestyle.width = 1.5

        _REUSABLE_STYLES = {
            "pin":    s_pin,
            "line":   s_line,
            "cone":   s_cone,
            "circle": s_circle,   # NUEVO
        }
```

**Nota sobre la caché global:** `_REUSABLE_STYLES` persiste entre llamadas a `generar_kml()` dentro del mismo proceso. Si dos bitácoras usan colores distintos, la segunda reutilizará los estilos de la primera. Agregar al inicio de `generar_kml()`:

```python
    global _REUSABLE_STYLES
    _REUSABLE_STYLES = None  # reset para que cada bitácora use su propio color
```

### Cambio en la validación de azimut

**Eliminar** el bloque "VALIDACIÓN DE AZIMUT" actual (el que hace `return`):

```python
# ELIMINAR este bloque completo:
    try:
        az = float(azimut_float)
    except Exception:
        return
    if isinstance(az, float) and math.isnan(az):
        return
    az = az % 360.0
    az_int = int(round(az)) % 360
```

**Reemplazar por:**

```python
    # === DETERMINAR SI HAY AZIMUT VÁLIDO ===
    az_valido = False
    az = None
    try:
        _az_c = float(azimut_float)
        if not math.isnan(_az_c):
            az = _az_c % 360.0
            az_valido = True
    except Exception:
        pass
```

### Insertar círculo después del pin

Inmediatamente después de `p.style = _REUSABLE_STYLES["pin"]`:

```python
    # === SIEMPRE: círculo de referencia ===
    try:
        _radio = float((config or {}).get("kml", {}).get("azimuth_km", 1.0))
        coords_circulo = generar_coordenadas_circulo(lat, lon, _radio)
        circulo = container.newpolygon(name="Radio de referencia")
        circulo.outerboundaryis = coords_circulo
        circulo.style = _REUSABLE_STYLES["circle"]
    except Exception:
        pass
```

### Cambio en la sección de línea y cono

Reemplazar el bloque "CREAR LÍNEA Y CONO DE AZIMUT" existente por:

```python
    # === SOLO SI AZIMUT VÁLIDO: línea y cono ===
    if az_valido:
        try:
            az_dist_km = float((config or {}).get("kml", {}).get("azimuth_km", 1.0))
            cone_half = (
                (config or {}).get("kml", {}).get("cone", {}).get("half_degrees")
                or (config or {}).get("style", {}).get("cone_half_degrees", 60)
            )
            cone_half = int(cone_half)
        except Exception:
            az_dist_km = 1.0
            cone_half = 60

        latf, lonf = calcular_punto_final(lat, lon, az, az_dist_km)
        linea = container.newlinestring(
            name=f"Azimut {int(round(az))}°",
            coords=[(lon, lat), (lonf, latf)]
        )
        linea.style = _REUSABLE_STYLES["line"]

        paso = 5
        coords_cono = []
        for ang in range(-cone_half, cone_half + 1, paso):
            lat_p, lon_p = calcular_punto_final(lat, lon, az + ang, az_dist_km)
            coords_cono.append((lon_p, lat_p))
        coords_cono.append((lon, lat))
        pol = container.newpolygon(name=f"Cono Azimut {int(round(az))}°")
        pol.outerboundaryis = coords_cono
        pol.style = _REUSABLE_STYLES["cone"]

        # Azimuts secundarios — conservar lógica existente sin cambios
        if azimuts_extra:
            for az_s in azimuts_extra:
                try:
                    az_s = float(az_s)
                except Exception:
                    continue
                # ... (mismo código existente)
```

**Criterios de aceptación:**

| Caso | Resultado esperado |
|---|---|
| Antena sin azimut | 1 pin + 1 círculo. Sin línea, sin cono. |
| Antena con azimut 90° | 1 pin + 1 círculo + 1 línea + 1 cono |
| Círculo y cono | Mismo radio (`azimuth_km`) |

**Commit:** `fix(kml_generator): pin y circulo siempre presentes; cono y linea solo con azimut valido`

---

## 5. Sub-fase 4: Subcarpetas + numeración + padding + sin-fecha

**Archivo:** `tz_core/kml_generator.py` — función `generar_kml()`
**Tipo:** Refactor de estructura de salida (B4–B8, B12)
**Riesgo:** 🟡 Medio — cambia solo el output KMZ, no el HTML ni la interfaz Python

### Pre-calcular antes de construir carpetas

Insertar después de que se construye la lista `items`:

```python
    # Pre-calcular numeración con mínimos de la spec (días: 3, activaciones: 4)
    total_activaciones = len(items)
    fechas_validas_set = {
        it["fecha"] for it in items
        if isinstance(it.get("fecha"), str) and it["fecha"] != "Sin Inf."
    }
    total_dias = len(fechas_validas_set)

    padding_dias = max(3, len(str(total_dias)))
    padding_act  = max(4, len(str(total_activaciones)))

    if total_activaciones > 300:
        log(f"[WARNING] KMZ: {total_activaciones} activaciones — puede afectar rendimiento en Google Earth.")
        print(f"\n[AVISO KMZ] {total_activaciones} activaciones detectadas. "
              f"El KMZ puede tardar en cargar en Google Earth.")
```

### Crear carpetas de fecha con numeración secuencial

Reemplazar el loop `for fch in fechas_unicas:` y la función `obtener_carpeta_fecha()`:

```python
    # Crear carpetas de fecha en orden cronológico con numeración secuencial
    from datetime import datetime as _dt

    fechas_validas_dt = sorted([
        _dt.strptime(f, "%d/%m/%Y")
        for f in fechas_validas_set
    ])

    for num_dia_idx, fch in enumerate(fechas_validas_dt, start=1):
        num_dia = str(num_dia_idx).zfill(padding_dias)
        nombre_dia = f"{num_dia} — {fch.strftime('%Y-%m-%d')}"
        carpeta_dia = f_todas.newfolder(name=nombre_dia)
        carpeta_dia.open = 0
        # Clave = formato display para lookup posterior
        folders_por_fecha[fch.strftime("%d/%m/%Y")] = carpeta_dia

    # Carpeta para registros sin fecha (se crea solo si se necesita)
    folder_sin_fecha = None
```

### Reemplazar loop de poblar todas_las_antenas

Obtener parámetros compartidos antes del loop:

```python
    _radio_kml    = float((config or {}).get("kml", {}).get("azimuth_km", 1.0))
    _radio_origen = (config or {}).get("kml", {}).get("radio_origen", "predeterminado")
    _cone_half_kml = int(
        (config or {}).get("kml", {}).get("cone", {}).get("half_degrees")
        or (config or {}).get("style", {}).get("cone_half_degrees", 60)
    )
```

Reemplazar el loop completo:

```python
    contador_act = 0
    for it in items:
        contador_act += 1
        num_act       = str(contador_act).zfill(padding_act)
        hora_display  = str(it.get("hora", "SinInf"))[:8]
        antena_truncada = str(it.get("antena", "Antena"))[:30]
        nombre_carpeta_act = f"{num_act} — {hora_display} — {antena_truncada}"

        # Resolver carpeta destino
        _carpeta_fecha = folders_por_fecha.get(it["fecha"])
        if _carpeta_fecha is None:
            # Activación sin fecha — crear carpeta especial si no existe
            if folder_sin_fecha is None:
                folder_sin_fecha = f_todas.newfolder(name="Sin fecha determinada")
                folder_sin_fecha.open = 0
            _carpeta_fecha = folder_sin_fecha

        # Crear subcarpeta de activación
        _carpeta_act = _carpeta_fecha.newfolder(name=nombre_carpeta_act)
        _carpeta_act.open = 0

        # Descripción de la carpeta (spec sección 2.4)
        # Validación robusta: _az_val puede ser None, float("nan") o un número válido
        _az_val = it.get("azimut_f")
        _az_desc_valido = False
        _az_desc = None
        try:
            _az_desc = float(_az_val)
            _az_desc_valido = not math.isnan(_az_desc)
        except (TypeError, ValueError):
            pass
        _az_line = (
            f"<b>Azimut:</b> {int(round(_az_desc)) % 360}°<br>"
            if _az_desc_valido else ""
        )
        _apertura_line = (
            f"<b>Apertura:</b> {_cone_half_kml * 2}°<br>"
            if _az_desc_valido else ""
        )
        _carpeta_act.description = (
            f"<b>Activación global:</b> {num_act}<br>"
            f"<b>Fecha y hora:</b> {it.get('fecha', 'Sin Inf.')} {hora_display}<br>"
            f"<b>Antena:</b> {it.get('antena', '')}<br>"
            f"{_az_line}"
            f"<b>Radio gráfico:</b> {_radio_kml} km<br>"
            f"{_apertura_line}"
            f"<b>Origen del radio:</b> {_radio_origen}<br>"
            f"<hr>"
            f"<i>Representación orientativa. No delimita la cobertura real "
            f"ni determina la ubicación exacta del terminal.</i>"
        )

        # Pin, círculo y geometrías dentro de la subcarpeta
        n_all = pair_counter_all.get((it["antena"], it["azimut_i"]), 1)
        desc_comp = armar_descripcion_compacta(
            it, n_all,
            suprimir_direccion_si_igual=True,
            config=config,
            hr_compact=HR_COMPACT
        )
        _crear_feature_kml(
            _carpeta_act,
            it["antena"], it["lon"], it["lat"],
            desc_comp, it["azimut_f"], config
        )
```

### folder.open = 0 en carpetas top

```python
    f_todas.open        = 0
    f_top_global.open   = 0
    f_top_por_rango.open = 0
    for folder in top_rango_folders.values():
        folder.open = 0
    if incluir_rango:
        for folder in rango_folders.values():
            folder.open = 0
```

**Criterios de aceptación:**

| Check | Resultado esperado |
|---|---|
| 9 activaciones, 1 día | `001 — 2026-01-10` / `0001 — 09:00:00 — ...` |
| 300 activaciones | padding 3 días, padding 4 activaciones |
| Activación del día 2 | número mayor que cualquier activación del día 1 |
| Registro sin fecha | aparece en "Sin fecha determinada", no desaparece |
| Todas las carpetas en Google Earth | cerradas por defecto |

**Commit:** `feat(kml_generator): subcarpetas por activacion, numeracion global, padding dinamico, carpeta sin-fecha`

---

## 6. Sub-fase 5: Carpeta "LEA PRIMERO"

**Archivo:** `tz_core/kml_generator.py`
**Tipo:** Adición (B9)
**Riesgo:** 🟢 Ninguno

Insertar **después de** `raiz = kml.newfolder(name=nombre_raiz)` y **antes de** crear cualquier otra carpeta:

```python
    # Leer parámetros para LEA PRIMERO (ya calculados arriba)
    f_lea = raiz.newfolder(name="⚠ LEA PRIMERO")
    f_lea.open = 0
    f_lea.description = (
        f"<b>Parámetros del análisis</b><br><br>"
        f"<b>Radio gráfico:</b> {_radio_kml} km<br>"
        f"<b>Apertura del sector:</b> {_cone_half_kml * 2}° "
        f"(±{_cone_half_kml}°)<br>"
        f"<b>Origen del radio:</b> {_radio_origen}<br><br>"
        f"<b>¿Qué significa el círculo?</b><br>"
        f"Zona de referencia orientativa. No representa la cobertura "
        f"real de la antena.<br><br>"
        f"<b>¿Qué significa el sector?</b><br>"
        f"Dirección aproximada según el azimut registrado. Solo aparece "
        f"cuando el dato de azimut está disponible en la bitácora.<br><br>"
        f"<b>ADVERTENCIA</b><br>"
        f"Esta representación es orientativa. El radio gráfico no delimita "
        f"la cobertura real ni determina la ubicación exacta del terminal."
    )
```

Nota: `_radio_kml`, `_radio_origen` y `_cone_half_kml` deben calcularse antes de este bloque. Mover el cálculo de esas variables al inicio de la sección "MODO CARPETAS" si no se movieron en la Sub-fase 4.

**Commit:** `feat(kml_generator): agregar carpeta LEA PRIMERO con parametros y advertencias`

---

## 7. Sub-fase 6: ScreenOverlay con PNG estático

**Archivos:** `tz_core/assets/kmz_aviso_orientativo.png` (nuevo) + `tz_core/kml_generator.py`
**Tipo:** Adición (B10, D2)
**Riesgo:** 🟢 Bajo — si el PNG no existe, se omite silenciosamente

### Paso A: Crear el PNG

Crear manualmente una imagen PNG con las siguientes características:

- Dimensiones sugeridas: **360 × 60 px**
- Fondo: negro o gris oscuro semi-transparente
- Texto en blanco, fuente legible:

```
REPRESENTACIÓN ORIENTATIVA
No representa cobertura real ni ubicación exacta.
```

Guardar en: `C:\TZ-Analyzer-1.0.0\tz_core\assets\kmz_aviso_orientativo.png`

```powershell
# Verificar que existe antes de continuar:
Test-Path "C:\TZ-Analyzer-1.0.0\tz_core\assets\kmz_aviso_orientativo.png"
```

### Paso B: Código en kml_generator.py

Insertar **inmediatamente después de** `kml = Kml()` al inicio de `generar_kml()`:

```python
    # ScreenOverlay permanente (Nivel 1 de advertencia — spec sección 2.8)
    _assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    _png_path   = os.path.join(_assets_dir, "kmz_aviso_orientativo.png")
    if os.path.exists(_png_path):
        try:
            # addfile() primero: devuelve el nombre interno en el KMZ
            _png_href = kml.addfile(_png_path)
            _overlay = kml.newscreenoverlay(name="Representación orientativa")
            _overlay.icon.href = _png_href          # usar retorno, no hardcodear nombre
            _overlay.overlayxy = sk.OverlayXY(
                x=0, y=1,
                xunits=sk.Units.fraction, yunits=sk.Units.fraction
            )
            _overlay.screenxy = sk.ScreenXY(
                x=0.01, y=0.96,
                xunits=sk.Units.fraction, yunits=sk.Units.fraction
            )
            _overlay.size = sk.Size(          # tamaño explícito = tamaño real del PNG
                x=360, y=60,
                xunits=sk.Units.pixels, yunits=sk.Units.pixels
            )
        except Exception:
            pass  # Si simplekml no soporta ScreenOverlay, continuar sin él
```

### Paso C: Commit

```powershell
git add tz_core/assets/kmz_aviso_orientativo.png
git add tz_core/kml_generator.py
git commit -m "feat(kml_generator): agregar ScreenOverlay permanente con PNG estatico"
```

---

## 8. Tests unitarios

**Archivo:** `tests/test_kml_implementation.py` (archivo nuevo)

```python
"""Tests implementación KMZ v1.1 — TZ Analyzer"""
import math
import zipfile
import pytest
import pandas as pd


# ── GEO_UTILS ──────────────────────────────────────────────────────────────

def test_circulo_count():
    from tz_core.geo_utils import generar_coordenadas_circulo
    coords = generar_coordenadas_circulo(13.7, -89.2, 1.0)
    assert len(coords) == 73  # 72 vértices + 1 cierre


def test_circulo_cerrado():
    from tz_core.geo_utils import generar_coordenadas_circulo
    coords = generar_coordenadas_circulo(13.7, -89.2, 1.0)
    assert coords[0] == coords[-1]


def test_circulo_radio_aproximado():
    """Todos los vértices deben estar a ≈ radio_km del centro."""
    from tz_core.geo_utils import generar_coordenadas_circulo
    radio = 1.0
    lat_c, lon_c = 13.7, -89.2
    for lon_p, lat_p in generar_coordenadas_circulo(lat_c, lon_c, radio)[:-1]:
        dlat = math.radians(lat_p - lat_c)
        dlon = math.radians(lon_p - lon_c)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat_c))
             * math.cos(math.radians(lat_p))
             * math.sin(dlon / 2) ** 2)
        dist = 6371.0 * 2 * math.asin(math.sqrt(a))
        assert abs(dist - radio) < 0.005, f"Vértice fuera de radio: {dist:.4f} km"


# ── ORDENAMIENTO CRONOLÓGICO ────────────────────────────────────────────────

_CONFIG_KMZ = {
    "kml": {"azimuth_km": 1.0},
    "style": {"theme_hex": "#ff0000"},
    "salida": {"solo_kmz": True},
}


def _generar_y_leer_kml(df, tmp_path, config=None):
    """Helper: genera KMZ y devuelve el contenido del doc.kml como string."""
    import tz_core.kml_generator as kml_mod
    from tz_core.kml_generator import generar_kml
    kml_mod._REUSABLE_STYLES = None
    out = str(tmp_path / "test.kml")
    generar_kml(df, out, config or _CONFIG_KMZ)
    kmz = str(tmp_path / "test.kmz")
    assert (tmp_path / "test.kmz").exists(), "KMZ no generado"
    with zipfile.ZipFile(kmz, "r") as z:
        with z.open("doc.kml") as f:
            return f.read().decode("utf-8")


def test_ordenamiento_carpetas_cronologico(tmp_path):
    """
    '02/12/2026' < '10/01/2026' alfabéticamente.
    Cronológicamente: 10/01/2026 < 02/12/2026.
    La carpeta '001 — 2026-01-10' debe aparecer antes que '002 — 2026-12-02'.
    """
    df = pd.DataFrame({
        "fecha":  ["02/12/2026", "10/01/2026"],
        "hora":   ["10:00:00",   "09:00:00"],
        "lat":    [13.7,         13.8],
        "long":   [-89.2,        -89.3],
        "antena": ["A",          "B"],
        "azimut": [90,           180],
    })
    kml_content = _generar_y_leer_kml(df, tmp_path)
    pos_jan = kml_content.find("2026-01-10")
    pos_dec = kml_content.find("2026-12-02")
    assert pos_jan != -1, "No se encontró fecha 2026-01-10 en el KMZ"
    assert pos_dec != -1, "No se encontró fecha 2026-12-02 en el KMZ"
    assert pos_jan < pos_dec, "Orden incorrecto: dic-2026 aparece antes que ene-2026"


def test_ordenamiento_mismo_timestamp_respeta_fila_original(tmp_path):
    """Dos registros con idéntica fecha y hora → orden por fila original."""
    df = pd.DataFrame({
        "fecha":  ["10/01/2026", "10/01/2026"],
        "hora":   ["09:00:00",   "09:00:00"],
        "lat":    [13.7,         13.8],
        "long":   [-89.2,        -89.3],
        "antena": ["PRIMERO",    "SEGUNDO"],
        "azimut": [90,           180],
    })
    kml_content = _generar_y_leer_kml(df, tmp_path)
    pos_a = kml_content.find("PRIMERO")
    pos_b = kml_content.find("SEGUNDO")
    assert pos_a != -1 and pos_b != -1
    assert pos_a < pos_b, "Orden de fila original no respetado en timestamps iguales"


def test_ordenamiento_fecha_valida_sin_hora_al_final_de_su_dia(tmp_path):
    """Registro con fecha válida pero sin hora → al final de ese día, no de la bitácora."""
    df = pd.DataFrame({
        "fecha":  ["10/01/2026", "10/01/2026", "11/01/2026"],
        "hora":   ["09:00:00",   "Sin Inf.",    "08:00:00"],
        "lat":    [13.7,         13.8,           13.9],
        "long":   [-89.2,        -89.3,          -89.4],
        "antena": ["CON_HORA",   "SIN_HORA",     "DIA2"],
        "azimut": [90,           90,              90],
    })
    kml_content = _generar_y_leer_kml(df, tmp_path)
    pos_con = kml_content.find("CON_HORA")
    pos_sin = kml_content.find("SIN_HORA")
    pos_d2  = kml_content.find("DIA2")
    assert pos_con < pos_sin, "Registro sin hora debe aparecer después del registro con hora"
    assert pos_sin < pos_d2,  "Registro sin hora del día 1 debe aparecer antes que cualquier activación del día 2"


# ── _CREAR_FEATURE_KML ──────────────────────────────────────────────────────

_CFG = {
    "kml": {"azimuth_km": 1.0, "cone": {"half_degrees": 60}},
    "style": {"theme_hex": "#ff0000", "cone_opacity": 0.4},
}


def _reset_and_import():
    import tz_core.kml_generator as kml_mod
    kml_mod._REUSABLE_STYLES = None
    from tz_core.kml_generator import _crear_feature_kml
    return _crear_feature_kml


def test_sin_azimut_solo_pin_y_circulo():
    """azimut=None: exactamente 1 pin + 1 polígono (círculo). Sin líneas."""
    import simplekml
    _crear = _reset_and_import()
    kml_obj = simplekml.Kml()
    _crear(kml_obj, "Test", -89.2, 13.7, None, None, _CFG)
    assert len(list(kml_obj.points))   == 1, "Esperado 1 pin"
    assert len(list(kml_obj.lines))    == 0, "Sin líneas (no hay azimut)"
    assert len(list(kml_obj.polygons)) == 1, "Esperado 1 polígono (círculo)"


def test_azimut_nan_solo_pin_y_circulo():
    """azimut=float('nan'): mismo comportamiento que None."""
    import simplekml
    _crear = _reset_and_import()
    kml_obj = simplekml.Kml()
    _crear(kml_obj, "Test", -89.2, 13.7, None, float("nan"), _CFG)
    assert len(list(kml_obj.points))   == 1, "Esperado 1 pin"
    assert len(list(kml_obj.lines))    == 0, "Sin líneas (azimut NaN)"
    assert len(list(kml_obj.polygons)) == 1, "Esperado 1 polígono (círculo)"


def test_con_azimut_genera_todo():
    """Con azimut válido: 1 pin + 2 polígonos (círculo + cono) + 1 línea."""
    import simplekml
    _crear = _reset_and_import()
    kml_obj = simplekml.Kml()
    _crear(kml_obj, "Test", -89.2, 13.7, None, 90.0, _CFG)
    assert len(list(kml_obj.points))   == 1, "Esperado 1 pin"
    assert len(list(kml_obj.lines))    == 1, "Esperado 1 línea de azimut"
    assert len(list(kml_obj.polygons)) == 2, "Esperado 2 polígonos (círculo + cono)"


def test_registro_sin_fecha_aparece_en_kmz(tmp_path):
    """Registro con fecha 'Sin Inf.' no debe perderse — debe aparecer en el KMZ."""
    df = pd.DataFrame({
        "fecha":  ["10/01/2026", "Sin Inf."],
        "hora":   ["09:00:00",   "10:00:00"],
        "lat":    [13.7,         13.8],
        "long":   [-89.2,        -89.3],
        "antena": ["CON_FECHA",  "SIN_FECHA"],
        "azimut": [90,           90],
    })
    kml_content = _generar_y_leer_kml(df, tmp_path)
    assert "SIN_FECHA" in kml_content, "Registro sin fecha desapareció del KMZ"
    assert "Sin fecha determinada" in kml_content, "Carpeta 'Sin fecha determinada' no creada"


# ── PADDING ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("total_dias,total_act,esperado_dia,esperado_act", [
    (1,     1,     "001",   "0001"),    # mínimos
    (999,   9999,  "999",   "9999"),    # justo en los límites de los mínimos
    (1000,  10000, "1000",  "10000"),   # superan mínimos → padding crece
])
def test_padding_dinamico(total_dias, total_act, esperado_dia, esperado_act):
    pad_dias = max(3, len(str(total_dias)))
    pad_act  = max(4, len(str(total_act)))
    assert str(total_dias).zfill(pad_dias) == esperado_dia
    assert str(total_act).zfill(pad_act)   == esperado_act
```

---

## 9. Secuencia de implementación

| Sub-fase | Archivo(s) | Cambio | Riesgo | Commit |
|---|---|---|---|---|
| 0 | `docs/` | Copiar specs | 🟢 | `docs:` |
| 1 | `geo_utils.py` | `generar_coordenadas_circulo()` | 🟢 | `feat(geo_utils):` |
| 2 | `kml_generator.py` | Bug fix ordenamiento | 🟢 | `fix(kml_generator):` |
| 3 | `kml_generator.py` | `_crear_feature_kml()` + círculo + reset caché | 🟡 | `fix(kml_generator):` |
| 4 | `kml_generator.py` | Subcarpetas + numeración + padding + sin-fecha + descripción carpeta | 🟡 | `feat(kml_generator):` |
| 5 | `kml_generator.py` | Carpeta "LEA PRIMERO" | 🟢 | `feat(kml_generator):` |
| 6 | `tz_core/assets/` + `kml_generator.py` | PNG estático + ScreenOverlay | 🟢 | `feat(kml_generator):` |

**Validación obligatoria entre sub-fases:**

```powershell
py -m py_compile tz_core\kml_generator.py
pytest -x -q
# Baseline al redactar esta especificación: 342 passing.
# Estado posterior verificado en agosto de 2026: 427 passed, 2 skipped.
# → generar KMZ con bitácora real TEL_61758498
# → revisión visual en Google Earth
```

---

## 10. Prueba con bitácora real — criterios visuales

Abrir KMZ en Google Earth y verificar:

1. ScreenOverlay visible en esquina superior izquierda con texto de advertencia
2. Primera carpeta en panel lateral: `⚠ LEA PRIMERO`
3. Segunda carpeta: `todas_las_antenas`
4. Todas las carpetas cerradas por defecto
5. Dentro de `todas_las_antenas`: subcarpetas `001 — YYYY-MM-DD` (numeración secuencial, no día del año)
6. Dentro de cada día: subcarpetas `0001 — HH:MM:SS — nombre_antena`
7. Descripción de subcarpeta de activación muestra: N° global, fecha/hora, antena, azimut si aplica, radio, origen
8. Antena sin azimut: solo pin + círculo (sin sector ni línea)
9. Antena con azimut: pin + círculo + sector + línea, mismo radio para ambos
10. Registros sin fecha: aparecen en "Sin fecha determinada"
11. El informe HTML generado junto al KMZ no cambia (protegido por `df.copy(deep=True)`)

---

## 11. Riesgos de regresión

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| `_REUSABLE_STYLES` persiste entre tests | Alta | `kml_mod._REUSABLE_STYLES = None` en `_reset_and_import()` y en setup de `generar_kml()` |
| Columnas auxiliares `_dt_kml_fecha`, `_hora_kml_sort`, `_hora_ausente`, `_fila_original` colisionan con columna real | Muy baja | `df.copy(deep=True)` al inicio de `generar_kml()` protege el DataFrame original |
| Modo flat no recibe subcarpetas — correcto por diseño | N/A | Modo flat no itera sobre carpetas de fecha |
| `generar_kml_puntos_libres()` afectado | N/A | No llama a `_crear_feature_kml()` — sin impacto |
| `folder.open = 0` no soportado por versión de simplekml | Baja | `pip show simplekml` — soportado desde 1.2+. Verificar antes de S4. |
| `kml.addfile()` no soportado | Baja | Wrapped en `try/except` — si falla, el KMZ se genera sin ScreenOverlay |
| Círculo aparece también en top_N y rangos | Intencional | Documentado. La spec no restringe el círculo a `todas_las_antenas`. |

---

## 12. Lo que esta spec NO cubre

- Lógica interna de `_crear_dedup()` (carpetas top_N) — conservar sin cambios excepto que recibe círculo por herencia
- `generar_kml_puntos_libres()` — no modificar
- Pipeline HTML — sin dependencia directa
- Cálculo de cobertura real
- Detector de saltos atípicos
- Versión compacta vs detallada de KMZ (futuro)
