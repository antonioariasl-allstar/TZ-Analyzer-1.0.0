# 📚 Reorganización de Documentación - Propuesta

## 📊 Estado Actual (DESORDENADO)

### Raíz del proyecto (8 archivos .md):
- ❌ `AUDITORIA.md`
- ❌ `AUDITORIA_SENIOR_COMPLETA.md`
- ❌ `DISENO_GUI.md`
- ✅ `ESTRATEGIA_SYNC.md`
- ❌ `FASE_8B_DEPENDENCIAS.md`
- ✅ `README.md` (DEBE estar en raíz)
- ❌ `RECOVERY_POINTS.md`
- ✅ `TODO.md` (DEBE estar en raíz)

### Carpeta docs/ (10 archivos .md):
- `ARQUITECTURA_HIBRIDA_PERMANENTE.md`
- `COLUMN_PROCESSOR_ANALISIS_FORENSE.md`
- `FILE_PROCESSOR_ESTADO_ACTUAL.md`
- `MAPA_ARCHIVOS_COMPLETO.md`
- `MAPA_ARCHIVOS_KML.md`
- `PLAN_MAESTRO_REFACTORIZACION.md`
- `PRINCIPIOS_DESARROLLO_PROFESIONAL.md`
- `SISTEMA_DUAL_COLUMNAS.md`
- `SUPRESION_DIRECCION.md`
- `WIZARD_QC_PELIGRO_EXTREMO.md`

### Carpeta docs/backups/:
- `FASE_8B_COMPLETADA.md`

### Otros archivos de documentación:
- `HANDOFF_CASA.txt` (raíz)

---

## ✅ Estructura Propuesta (ORGANIZADA)

```
TZ_Analysis_1.0.0_REPO/
│
├── README.md                           ← Usuario final (cómo usar)
├── TODO.md                             ← Estado actual y pendientes
├── HANDOFF_CASA.txt                    ← Sincronización trabajo
│
├── docs/
│   ├── README.md                       ← Índice de toda la documentación
│   │
│   ├── user/                           ← Documentación para usuarios
│   │   ├── GUIA_INSTALACION.md
│   │   ├── GUIA_USO_BASICO.md
│   │   └── FAQ.md
│   │
│   ├── development/                    ← Documentación para desarrolladores
│   │   ├── ARQUITECTURA_HIBRIDA_PERMANENTE.md
│   │   ├── PRINCIPIOS_DESARROLLO_PROFESIONAL.md
│   │   ├── PLAN_MAESTRO_REFACTORIZACION.md
│   │   ├── ESTRATEGIA_SYNC.md          ← Movido desde raíz
│   │   └── CONTRIBUCION.md
│   │
│   ├── technical/                      ← Documentación técnica detallada
│   │   ├── arquitectura/
│   │   │   ├── SISTEMA_DUAL_COLUMNAS.md
│   │   │   ├── COLUMN_PROCESSOR_ANALISIS_FORENSE.md
│   │   │   └── FILE_PROCESSOR_ESTADO_ACTUAL.md
│   │   │
│   │   ├── features/
│   │   │   ├── SUPRESION_DIRECCION.md
│   │   │   └── WIZARD_QC_PELIGRO_EXTREMO.md
│   │   │
│   │   └── mapas/
│   │       ├── MAPA_ARCHIVOS_COMPLETO.md
│   │       └── MAPA_ARCHIVOS_KML.md
│   │
│   ├── planning/                       ← Planificación y diseño
│   │   ├── DISENO_GUI.md               ← Movido desde raíz
│   │   └── ROADMAP.md
│   │
│   ├── audits/                         ← Auditorías y análisis
│   │   ├── AUDITORIA.md                ← Movido desde raíz
│   │   ├── AUDITORIA_SENIOR_COMPLETA.md ← Movido desde raíz
│   │   └── RECOVERY_POINTS.md          ← Movido desde raíz
│   │
│   └── legacy/                         ← Documentación histórica
│       ├── FASE_8B_DEPENDENCIAS.md     ← Movido desde raíz
│       └── backups/
│           └── FASE_8B_COMPLETADA.md
│
└── config.json
```

---

## 🎯 Ventajas de la Nueva Estructura

### Para Usuarios:
✅ `README.md` en raíz - Primera cosa que ven  
✅ Documentación de usuario separada y clara  
✅ FAQ para problemas comunes

### Para Desarrolladores:
✅ Documentación técnica bien organizada por categorías  
✅ Arquitectura y principios fáciles de encontrar  
✅ Historia del proyecto preservada en `legacy/`

### Para Mantenimiento:
✅ Fácil agregar nueva documentación (categorías claras)  
✅ Fácil archivar documentación obsoleta  
✅ Estructura escalable

---

## 🔄 Plan de Migración (Paso a Paso)

### Fase 1: Crear estructura de carpetas
```powershell
mkdir docs\user
mkdir docs\development
mkdir docs\technical\arquitectura
mkdir docs\technical\features
mkdir docs\technical\mapas
mkdir docs\planning
mkdir docs\audits
mkdir docs\legacy
```

### Fase 2: Mover archivos (con git mv para preservar historia)
```powershell
# User docs (crear nuevos)
# Se crearán: GUIA_INSTALACION.md, GUIA_USO_BASICO.md, FAQ.md

# Development
git mv ESTRATEGIA_SYNC.md docs\development\
# ARQUITECTURA_HIBRIDA_PERMANENTE.md ya está en docs/
# PRINCIPIOS_DESARROLLO_PROFESIONAL.md ya está en docs/
# PLAN_MAESTRO_REFACTORIZACION.md ya está en docs/

# Technical - Arquitectura
git mv docs\SISTEMA_DUAL_COLUMNAS.md docs\technical\arquitectura\
git mv docs\COLUMN_PROCESSOR_ANALISIS_FORENSE.md docs\technical\arquitectura\
git mv docs\FILE_PROCESSOR_ESTADO_ACTUAL.md docs\technical\arquitectura\

# Technical - Features
git mv docs\SUPRESION_DIRECCION.md docs\technical\features\
git mv docs\WIZARD_QC_PELIGRO_EXTREMO.md docs\technical\features\

# Technical - Mapas
git mv docs\MAPA_ARCHIVOS_COMPLETO.md docs\technical\mapas\
git mv docs\MAPA_ARCHIVOS_KML.md docs\technical\mapas\

# Planning
git mv DISENO_GUI.md docs\planning\

# Audits
git mv AUDITORIA.md docs\audits\
git mv AUDITORIA_SENIOR_COMPLETA.md docs\audits\
git mv RECOVERY_POINTS.md docs\audits\

# Legacy
git mv FASE_8B_DEPENDENCIAS.md docs\legacy\
git mv docs\backups docs\legacy\
```

### Fase 3: Crear README.md principal en docs/
```markdown
# 📚 Documentación TZ Analyzer

## 📖 Para Usuarios
- [Guía de Instalación](user/GUIA_INSTALACION.md)
- [Guía de Uso Básico](user/GUIA_USO_BASICO.md)
- [Preguntas Frecuentes (FAQ)](user/FAQ.md)

## 👨‍💻 Para Desarrolladores
- [Arquitectura Híbrida](development/ARQUITECTURA_HIBRIDA_PERMANENTE.md)
- [Principios de Desarrollo](development/PRINCIPIOS_DESARROLLO_PROFESIONAL.md)
- [Plan Maestro de Refactorización](development/PLAN_MAESTRO_REFACTORIZACION.md)
- [Estrategia de Sincronización](development/ESTRATEGIA_SYNC.md)

## 🔧 Documentación Técnica
### Arquitectura
- [Sistema Dual de Columnas](technical/arquitectura/SISTEMA_DUAL_COLUMNAS.md)
- [Column Processor](technical/arquitectura/COLUMN_PROCESSOR_ANALISIS_FORENSE.md)
- [File Processor](technical/arquitectura/FILE_PROCESSOR_ESTADO_ACTUAL.md)

### Features
- [Supresión de Dirección](technical/features/SUPRESION_DIRECCION.md)
- [Wizard QC](technical/features/WIZARD_QC_PELIGRO_EXTREMO.md)

### Mapas del Sistema
- [Mapa Completo de Archivos](technical/mapas/MAPA_ARCHIVOS_COMPLETO.md)
- [Mapa de Archivos KML](technical/mapas/MAPA_ARCHIVOS_KML.md)

## 📋 Planificación
- [Diseño de GUI](planning/DISENO_GUI.md)

## 📊 Auditorías
- [Auditoría Básica](audits/AUDITORIA.md)
- [Auditoría Senior Completa](audits/AUDITORIA_SENIOR_COMPLETA.md)
- [Recovery Points](audits/RECOVERY_POINTS.md)

## 🗄️ Legacy
- [Fase 8B - Dependencias](legacy/FASE_8B_DEPENDENCIAS.md)
- [Backups](legacy/backups/)
```

### Fase 4: Actualizar README.md principal
Agregar sección que apunte a `docs/README.md`:
```markdown
## 📚 Documentación

Para documentación completa, consulta [docs/README.md](docs/README.md)

- **Usuarios**: [Guías de uso](docs/user/)
- **Desarrolladores**: [Documentación técnica](docs/development/)
```

### Fase 5: Commit y push
```powershell
git add .
git commit -m "docs: reorganizar estructura de documentación

- Crear categorías: user, development, technical, planning, audits, legacy
- Mover archivos a ubicaciones apropiadas
- Crear índice principal en docs/README.md
- Actualizar README.md raíz"
git push origin main
```

---

## ⚠️ Archivos que DEBEN permanecer en raíz

- ✅ `README.md` - Primera impresión del proyecto
- ✅ `TODO.md` - Estado actual rápido
- ✅ `HANDOFF_CASA.txt` - Workflow de sincronización
- ✅ `.gitignore`, `requirements.txt`, `config.json` - Archivos de configuración

---

## 🤔 Decisión

¿Quieres que proceda con esta reorganización?

**Opción A:** Hacer la reorganización completa ahora  
**Opción B:** Solo crear la estructura y mover gradualmente  
**Opción C:** Dejar como está (no recomendado)

¿Qué prefieres?
