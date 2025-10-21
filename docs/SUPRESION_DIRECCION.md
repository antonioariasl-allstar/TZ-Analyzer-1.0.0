# Supresión Contextual de "Dirección" en KML

**Fecha de implementación**: 21 de octubre de 2025  
**Versión**: TZ-Analysis 1.0.0  
**Branch**: packaging/prep

---

## 📋 Resumen

Esta funcionalidad evita la duplicación de información cuando el usuario mapea la misma columna de datos tanto para "antena" como para "direccion" en el KML generado.

### Problema Original

Cuando se mapea la misma columna para ambos campos:
```
Columna en CSV: "Torre Central, Av. Principal, San Salvador"
Mapeo: antena → Torre Central, Av. Principal, San Salvador
       direccion → Torre Central, Av. Principal, San Salvador
```

Resultado antes de la corrección:
```
Antena: Torre Central, Av. Principal, San Salvador
...
Direccion: Torre Central, Av. Principal, San Salvador  ← DUPLICADO
```

### Solución Implementada

La línea de "Dirección" se oculta automáticamente cuando es **idéntica** a "Antena" (comparación normalizada sin tildes, espacios extra ni mayúsculas).

---

## 🎯 Comportamiento por Contexto

### 1. Carpeta "todas_las_antenas"
**Supresión**: ✅ ACTIVA

```python
desc_comp = _armar_descripcion_compacta(it, n_all, suprimir_direccion_si_igual=True)
```

**Razón**: Esta carpeta muestra todos los registros sin filtrar. La duplicación aquí es más evidente y menos útil.

### 2. Carpetas "top_N_las_mas_activadas" y "top_N_por_rango"
**Supresión**: ❌ DESACTIVADA

```python
# En _crear_dedup_top, la dirección SIEMPRE se muestra
_dir_line = ""
if direccion not in (None, "", "SinInf"):
    _dir_line = f"<b>{_label_dir_top}:</b> {direccion}<br>"  # Sin verificar igualdad
```

**Razón**: Las carpetas "top" muestran información crítica consolidada. Es preferible mostrar toda la información disponible, incluso si es redundante.

### 3. Modo Plano (flat=True)
**Supresión**: ❌ DESACTIVADA

```python
desc_comp = _armar_descripcion_compacta(it, n_all, suprimir_direccion_si_igual=False)
```

**Razón**: En modo plano no hay jerarquía de carpetas. La información debe estar completamente visible.

---

## 🔧 Configuración

### Etiqueta de "Dirección"

Edita `config.json`:

```json
{
  "kml": {
    "labels": {
      "direccion": "Direccion"
    }
  }
}
```

Puedes cambiar a:
- `"Ubicación"`
- `"Lugar"`
- `"Localización"`
- O cualquier otro texto

---

## 🧪 Validación

### Script de Auditoría Automatizada

Ejecuta `tests/audit_kml_checks.py` para validar los casos:

```powershell
python tests/audit_kml_checks.py
```

**Casos validados**:
- ✅ **Caso 1**: Dirección == Antena → se oculta en "todas_las_antenas"
- ✅ **Caso 2**: Dirección ≠ Antena → se muestra siempre
- ✅ **Caso 3**: Compactación de nombres por coma
- ✅ **Caso 4**: Límite de palabras/caracteres en nombres

---

## 📝 Normalización de Texto

La comparación usa normalización Unicode para eliminar diferencias irrelevantes:

```python
def _norm_text(s):
    if s is None:
        return ""
    try:
        s = str(s)
        s = unicodedata.normalize("NFKD", s)  # Descomponer caracteres
        s = "".join(ch for ch in s if not unicodedata.combining(ch))  # Quitar tildes
        s = re.sub(r"\s+", " ", s).strip().lower()  # Normalizar espacios y minúsculas
        return s
    except Exception:
        return str(s).strip().lower()
```

**Ejemplos de textos considerados "iguales"**:
- `"Calle Principal"` == `"calle principal"`
- `"Avenida José"` == `"Avenida Jose"` (sin tilde)
- `"Torre  Centro"` == `"Torre Centro"` (espacios extra)

---

## 🐛 Bug Corregido (Sangría)

Durante la implementación se detectó y corrigió un bug crítico de indentación que causaba que solo el último registro se procesara en "todas_las_antenas":

**ANTES** (Bug):
```python
for it in items:
    n_all = pair_counter_all.get((it["antena"], it["azimut_i"]), 1)
desc_comp = _armar_descripcion_compacta(it, n_all, suprimir_direccion_si_igual=True)  # ❌ Fuera del loop
_crear_feature_kml(...)  # ❌ Fuera del loop
```

**DESPUÉS** (Corregido):
```python
for it in items:
    n_all = pair_counter_all.get((it["antena"], it["azimut_i"]), 1)
    desc_comp = _armar_descripcion_compacta(it, n_all, suprimir_direccion_si_igual=True)  # ✅ Dentro del loop
    _crear_feature_kml(...)  # ✅ Dentro del loop
```

---

## 💡 Recomendación de Uso

**Ideal**: Mapear columnas distintas para "antena" y "direccion"
```
antena → Nombre corto de la torre/sitio
direccion → Dirección completa con referencias
```

**Aceptable**: Mapear la misma columna (la supresión evitará duplicación)
```
antena → Dirección completa
direccion → Dirección completa  ← Se ocultará automáticamente en "todas_las_antenas"
```

---

## 📚 Referencias

- **Código fuente**: `script_principal_bitacoras_refactory.py`
  - Función `_armar_descripcion_compacta()` (línea ~1429)
  - Modo plano (línea ~1990)
  - Carpeta todas_las_antenas (línea ~2084)
  - Carpetas top (línea ~2227-2311)
- **Configuración**: `config.json` → `kml.labels.direccion`
- **Auditoría**: `tests/audit_kml_checks.py`
- **Documentación completa**: `AUDITORIA.md` → Fase 4

---

**Mantenido por**: GitHub Copilot  
**Última actualización**: 21 de octubre de 2025
