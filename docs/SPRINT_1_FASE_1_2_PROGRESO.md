# SPRINT 1 FASE 1.2 - PROGRESO PARCIAL

**Fecha:** 29 octubre 2025  
**Estado:** 🚧 EN PROGRESO (3/5 duplicados resueltos)

## ✅ DUPLICADOS RESUELTOS (3/5)

### 1. `_fmt_az` (3 → 1 implementación)
- **Consolidadas:** L1448, L1566, L1978 
- **Implementación elegida:** L1978 (más robusta con None y redondeo)
- **Nueva función:** `tz_services.validation.fmt_azimuth`
- **Fachadas:** 3 funciones `_fmt_az` → `fmt_azimuth`

### 2. `_es_valida_latlon_row` (2 → 1 implementación)  
- **Consolidadas:** L1782, L1889
- **Implementación elegida:** Reutilizar `es_valida_latlon_row` ya en tz_services
- **Fachadas:** 2 funciones → `es_valida_latlon_row`

### 3. `_fmt_coord` (2 → 1 implementación)
- **Consolidadas:** L1936, L6342
- **Implementación elegida:** L1936 (maneja None, NaN, 6 decimales)
- **Nueva función:** `tz_services.validation.fmt_coordinate`  
- **Fachadas:** 2 funciones `_fmt_coord` → `fmt_coordinate`

## 📊 MÉTRICAS PARCIALES

- **Duplicados resueltos:** 3/5 (60%)
- **Implementaciones consolidadas:** 7 → 3 funciones
- **Líneas reducidas:** ~40 líneas de código duplicado
- **Funciones agregadas a tz_services:** 3 nuevas

## 🧪 VALIDACIÓN  

- ✅ **Checkpoint automático:** 3/3 tests passing
- ✅ **Compatibilidad:** Preservada con fachadas
- ✅ **Script principal:** Funciona normalmente

## 🔄 PENDIENTES FASE 1.2

### 4. `__iter__` y `__len__` (métodos especiales)
- **Ubicación:** L589/L608, L591/L610
- **Estrategia:** Analizar si son de clases diferentes o duplicados reales

### 5. `_copiar_logo_a_salida` (2 implementaciones)
- **Ubicación:** L771, L6288  
- **Estrategia:** Consolidar signatures diferentes

## ✅ CONCLUSIÓN PARCIAL

**Fase 1.2 va por buen camino:** 60% completada con 3 duplicados mayores resueltos. Las fachadas mantienen compatibilidad 100% mientras consolidamos implementaciones dispersas.

**Ready para commit parcial y continuar con últimos 2 duplicados.**