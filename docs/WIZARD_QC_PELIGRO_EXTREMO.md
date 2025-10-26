# ⚡ WIZARD QC MANUAL - ZONA DE PELIGRO EXTREMO

## 🚨 ADVERTENCIA CRÍTICA PARA DESARROLLADORES

**CUALQUIER MODIFICACIÓN A `_wizard_qc_mapeo()` PUEDE CAUSAR FALLA SISTÉMICA TOTAL**

**Ubicación**: `script_principal_bitacoras_refactory.py` líneas 353-735  
**Tamaño**: 382 líneas de código crítico  
**Nivel de riesgo**: 🔴 **ROJO ABSOLUTO - CONTRAINDICADO**

## Resumen Ejecutivo

Durante la evaluación extendida de Fase 5.3b se descubrió que el wizard QC manual es un **componente crítico masivo** que requiere intervención especializada avanzada, no refactorización convencional.

## ⚡ Evaluación de Riesgo

### Complejidad Estructural
- **382 líneas** de lógica interconectada
- **Múltiples subsistemas** en una sola función
- **Estado mutable global** (modificaciones a CONFIG)
- **Interactividad masiva** (múltiples puntos input())

### Dependencias Críticas
```python
# Dependencia del sistema dual extraído en Fase 5.3a
cols_menu = list(map(str, getattr(df, "_orig_cols", list(df.columns))))

# Persistencia en configuración global
cfg_add_user_synonym(CONFIG, canonico, encabezado_crudo, ruta_cfg)

# Interactividad compleja
sel = input(f"→ Elegí columna para **{canonico}** (número, menú arriba): ")
```

### Efectos Secundarios
1. **Modificación CONFIG**: Persiste mapeos de usuario
2. **Estado DataFrame**: Modifica `df._orig_cols` 
3. **Sinónimos dinámicos**: Actualiza sistema de mapeo
4. **Validación columnas**: Evita duplicados en asignaciones

## 🔬 Análisis Técnico

### ¿Por qué es tan peligroso?

1. **Componente crítico único**: Sin esta función, el mapeo manual colapsa
2. **Interdependencias complejas**: Conectado a 4+ sistemas críticos
3. **Testing imposible**: Múltiples input() sin estrategia de mocking
4. **Zero fault tolerance**: Cualquier error rompe workflow completo

### ¿Qué hace exactamente?

El wizard permite al usuario mapear columnas de Excel a campos canónicos:

```
Columnas disponibles en Excel:
[1] Telefono    [2] Latitud    [3] Longitud    [4] Fecha_Hora
[5] Azimut      [6] IMEI       [7] Contacto    [8] Direccion

→ Elegí columna para **tel** (número, menú arriba): 1
→ Elegí columna para **lat** (número, menú arriba): 2
→ Elegí columna para **long** (número, menú arriba): 3
```

Después persiste estas decisiones en CONFIG para futuras ejecuciones.

## 🚫 Contraindicaciones Absolutas

### ❌ NO Intentar Ahora
- **Extracción directa**: Demasiado complejo para refactoring estándar
- **Testing unitario**: Imposible sin framework de mocking avanzado
- **Modularización simple**: Requiere estrategia arquitectónica especializada

### ❌ NO Tocar Líneas
- **353-735**: Función principal wizard
- **7568**: `df._orig_cols` (dependencia crítica del sistema dual)
- Variables `MANUAL_QC_MAPPING`, `asignadas`, `usadas`

## 🩺 Estrategia de Intervención Diferida

### Fase 12-13: Preparación Especializada
1. **Desarrollo framework mocking**: Para input() múltiples
2. **Estrategia de testing**: Scenarios de mapeo completos
3. **Arquitectura modular**: División en subfunciones manejables

### Pre-requisitos Obligatorios
- ✅ Todas las funciones simples extraídas
- ✅ Sistema de testing maduro 
- ✅ Framework de mocking interactivo
- ✅ Experiencia en 10+ extracciones exitosas

### Estrategia Tentativa
```
tz_core/
├── ui_components/
│   ├── interactive_mapper.py      # Core del wizard
│   ├── column_selector.py         # Selección de columnas  
│   └── mapping_persistence.py    # Persistencia CONFIG
└── column_processor/
    ├── mapping_engine.py          # Lógica de mapeo
    └── synonym_manager.py         # Sistema de sinónimos
```

## 🔄 Re-evaluación Obligatoria

Antes de cualquier intervención futura:

1. **Evaluación de dependencias**: ¿Han cambiado las conexiones?
2. **Testing preparedness**: ¿Tenemos framework adecuado?
3. **Rollback strategy**: ¿Plan de recuperación completo?
4. **User impact**: ¿Cómo preservar workflow actual?

## 📋 Registro de Decisiones

| Fecha | Decisión | Razón |
|-------|----------|--------|
| 2025-10-25 | Diferir intervención | Riesgo extremo, complejidad masiva |
| TBD | Re-evaluación | Cuando pre-requisitos estén listos |

## 💡 Para Desarrolladores Futuros

Si llegaste aquí buscando modificar el wizard:

1. **STOP** - Lee todo este documento primero
2. **Consulta TODO.md** - Revisa el estado actual del proyecto  
3. **Evalúa alternativas** - ¿Realmente necesitas tocar esto?
4. **Planifica extensively** - Si es inevitable, diseña con 3+ meses de anticipación

## 🆘 En Caso de Emergencia

Si el wizard falla y necesitas intervención inmediata:

1. **Git checkout**: Rollback al último commit estable
2. **Backup restoration**: Usar respaldos automáticos
3. **Contact team**: Este no es trabajo para una sola persona

---

**Recuerda**: La valentía médica no es actuar sin miedo, sino actuar con el miedo apropiado para la situación. El wizard QC merece nuestro máximo respeto y precaución.