# Fix Campo Usuario KML

## Fecha: 27 de octubre de 2025
## Branch: feature/validation-utils

### Problema Identificado
El campo "Usuario" aparecía solo en la carpeta `todas_las_antenas` pero NO en las carpetas `top_las_mas_activadas` y `top_por_rango_horario` del archivo KMZ.

### Causa Raíz
Inconsistencia entre dos flujos de generación de burbujas KML:

1. **Carpeta "todas_las_antenas":** Usa `_armar_descripcion_compacta()` que busca `campos.get("usuario")`
2. **Carpetas "top":** Usa `_crear_dedup_top()` con template hardcodeado `campos.get("nombre_usuario", "")`

El diccionario `campos` solo contenía `"nombre_usuario"` pero faltaba `"usuario"`.

### Solución Aplicada

#### Cambio 1: Diccionario campos (línea ~2204)
```python
# ANTES:
campos = {
    "nombre_usuario": None,
    "abonado": None,
    "alias": None,
}

# DESPUÉS:
campos = {
    "nombre_usuario": None,
    "usuario": None,  # 🔧 FIX: Agregar campo "usuario" para compatibilidad
    "abonado": None,
    "alias": None,
}
```

#### Cambio 2: Template de burbuja (línea ~2296)
```python
# ANTES:
<b>Nombre de Usuario:</b> {campos.get("nombre_usuario", "")}<br>

# DESPUÉS:
<b>Usuario:</b> {usuario}<br>
```

### Validación del Usuario
- ✅ Ejecutado `run.py` por el usuario
- ✅ Campo "Usuario" ahora aparece en todas las carpetas KML
- ✅ Funcionalidad completa confirmada

### Tests Realizados
- ✅ Script principal: Importa correctamente
- ✅ Tests unitarios: 44/44 PASSED (baseline dorado mantenido)
- ✅ Módulos tz_core: time_utils y validation_utils funcionando
- ✅ Test usuario real: run.py ejecuta perfectamente

### Tipo de Fix
**SOLUCIÓN PERMANENTE** - No es temporal:
- Arregla inconsistencia de diseño entre funciones
- Utiliza la misma lógica `getv_group()` para extraer datos
- Mantiene compatibilidad total hacia atrás
- Fix estructural que resuelve el problema raíz

### Impacto
- **POSITIVO:** Campo Usuario visible en todas las carpetas KML
- **RIESGO:** MÍNIMO (solo unifica comportamiento existente)
- **COMPATIBILIDAD:** Total hacia atrás