# 🗺️ MAPA DE ARCHIVOS KML - TZ ANALYZER

## 📍 ESTADO ACTUAL DE ARCHIVOS KML

### ✅ ARCHIVO ACTIVO (USAR ESTE)
**📁 `kml_generador.py`** (raíz del proyecto)
- **Estado**: 🟢 EN PRODUCCIÓN
- **Líneas**: 439 líneas funcionales
- **Propósito**: Generación KML/KMZ para Google Earth
- **Funciones principales**:
  - `generar_kml_puntos_libres()`
  - `hex_to_abgr()`
- **Usado por**: `script_principal_bitacoras_refactory.py`

### 🏗️ ARCHIVO ESQUELETO (NO USAR)
**📁 `tz_core/kml_generator.py`** (framework modular)
- **Estado**: 🟡 ESQUELETO PREPARADO
- **Líneas**: 40 líneas (solo estructura)
- **Propósito**: Preparación para migración futura
- **Clase**: `KMLGenerator` (vacía)
- **Usado por**: Nadie (código preparatorio)

## 🎯 ARQUITECTURA HÍBRIDA

### Flujo Actual
```
script_principal.py → kml_generador.py (ACTIVO)
                           ↓
                   Genera archivos KML/KMZ
```

### Flujo Futuro (Opcional)
```
script_principal.py → tz_core/kml_generator.py (MODULAR)
                           ↓
                   Genera archivos KML/KMZ
```

## 🔄 MIGRACIÓN FUTURA (OPCIONAL)

### Pasos para Migrar (Cuando Sea Necesario):
1. **Implementar** funcionalidad en `tz_core/kml_generator.py`
2. **Probar** exhaustivamente la nueva implementación
3. **Actualizar** imports en script principal
4. **Validar** con suite de testing completa
5. **Deprecar** `kml_generador.py` gradualmente

### Criterios para Migrar:
- ✅ Necesidad de optimización KML
- ✅ Requerimientos de testing modular
- ✅ Evolución arquitectónica planificada

## ⚠️ RECOMENDACIONES

### Para Desarrolladores:
1. **USAR SIEMPRE**: `kml_generador.py` (raíz)
2. **NO MODIFICAR**: `tz_core/kml_generator.py` sin planificación
3. **COORDINAR**: Cualquier cambio con arquitectura híbrida

### Para Mantenimiento:
- **Bugs KML**: Arreglar en `kml_generador.py`
- **Nuevas features**: Evaluar si van en raíz o modular
- **Testing**: Validar siempre con archivo activo

## 📊 RESUMEN EJECUTIVO

**ESTADO**: Sistema KML funcional al 100%
**CONFUSIÓN**: Eliminada con documentación clara
**FUTURO**: Migración opcional disponible
**ACCIÓN**: Continuar usando `kml_generador.py` sin cambios

---
**Fecha**: 26 de octubre de 2025  
**Versión**: TZ Analyzer v1.0.0  
**Arquitectura**: Híbrida Permanente