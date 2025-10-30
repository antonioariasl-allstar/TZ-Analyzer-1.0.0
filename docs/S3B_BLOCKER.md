# S3B BLOCKER - CLI Click Import Contract Broken

**Fecha:** 29 de octubre de 2025  
**Sprint:** 3B (CLI Click)  
**Estado:** 🔒 EN CUARENTENA EXPERIMENTAL  

## 🚨 CAUSA RAÍZ

**Problema:** Contrato de import roto entre paquetes

### Arquitectura problemática detectada:
```
tz_cli/main.py intenta:  from tz_cli import cli
tz_cli/__init__.py:      NO exporta 'cli' (solo funciones menu)
cli realmente vive en:   tz_cli_click/main.py
```

### Dependencias cruzadas:
```
tz_cli/commands/*.py esperan: from tz_cli import TZContext, pass_context
Pero TZContext está en:        tz_cli_click/main.py (como TZClickContext)
```

## 🛠️ QUÉ HABRÍA QUE HACER PARA ARREGLAR (PRÓXIMO SPRINT)

### Opción A: Adapter Layer
1. Crear `tz_cli/adapter.py` que:
   - Re-exporte `cli` desde `tz_cli_click.main`
   - Proporcione `TZContext` shim para comandos
   - Unifique contratos de import

### Opción B: Unificar Paquete
1. Mover comandos de `tz_cli/commands/` → `tz_cli_click/commands/`
2. Actualizar imports para usar un solo paquete
3. Deprecar `tz_cli/main.py`

## ⚠️ RIESGOS SI SE FUERZA EL FIX HOY

- **Regresión Sprint 3A:** Menú interactivo podría romperse
- **Import cycles:** Dependencias circulares entre paquetes  
- **Testing incomplete:** Cambios sin validación E2E completa
- **Merge conflicts:** Integración prematura con main

## 🔒 ESTADO ACTUAL

- **tz_cli_click/** → **experimental/tz_cli_click/** (cuarentena)
- **python -m tz_cli.main --help** → No disponible (esperado)
- **python -m tz_cli --help** → ✅ Funcional (Sprint 3A)

## 📋 PRÓXIMOS PASOS RECOMENDADOS

1. **Sprint 3B-Adapter:** Implementar adapter layer controlado
2. **Testing exhaustivo:** Validar integración antes de reactivar
3. **Merge seguro:** Solo después de adapter estable

**Responsable:** Sprint 3B-Adapter (pendiente autorización)