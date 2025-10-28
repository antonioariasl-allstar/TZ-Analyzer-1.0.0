# 🚨 PROTOCOLO DE SINCRONIZACIÓN OBLIGATORIO
## LEER ESTO ANTES DE CUALQUIER CAMBIO

**⚠️ ATENCIÓN: TODO AGENTE/DESARROLLADOR DEBE EJECUTAR ESTE PROTOCOLO ANTES DE TRABAJAR**

### 📋 CHECKLIST OBLIGATORIO

#### ✅ PASO 1: VERIFICAR SINCRONIZACIÓN
```bash
# 1. Verificar rama actual
git branch

# 2. Verificar estado del repositorio  
git status

# 3. Verificar diferencias con remoto
git fetch
git status

# 4. Si hay divergencias, sincronizar:
git pull

# 5. Resolver conflictos si existen
# 6. Verificar que el workspace está limpio
git status  # Debe mostrar "working tree clean"
```

#### ✅ PASO 2: VERIFICAR ESTRUCTURA ACTUAL
```bash
# Verificar módulos en tz_core/
ls tz_core/

# Verificar documentación organizada
ls docs/

# Verificar tests funcionando
python -m pytest tests/ -v
```

#### ✅ PASO 3: LEER ESTADO ACTUAL
- **OBLIGATORIO:** Leer `docs/development/ESTADO_ACTUAL.md`
- **OBLIGATORIO:** Leer `TODO.md` secciones relevantes
- **OBLIGATORIO:** Verificar últimos commits: `git log --oneline -5`

---

## 🎯 ESTRUCTURA ACTUAL CONFIRMADA

### 📁 Documentación Reorganizada (✅ EXCELENTE TRABAJO)
```
docs/
├── audits/          # Auditorías y evaluaciones  
├── development/     # Documentación técnica/desarrollo
├── legacy/          # Archivos históricos
├── planning/        # Planificación futura
├── technical/       # Documentación técnica específica
├── user/           # Guías para usuarios finales
└── README.md       # Índice principal
```

### 🧩 Módulos tz_core/ Confirmados
```
tz_core/
├── config_manager.py   # ✅ Gestión configuración
├── data_loader.py      # ✅ Carga de datos  
├── geo_utils.py        # 🆕 Utilidades geográficas
├── text_utils.py       # 🆕 Utilidades de texto
├── utils.py           # ✅ Utilidades generales
└── __init__.py        # ✅ Inicialización
```

---

## ⚠️ PROBLEMAS COMUNES Y SOLUCIONES

### 🔴 "Your branch and 'origin/main' have diverged"
```bash
# SOLUCIÓN:
git fetch
git pull
# Resolver conflictos manualmente
git add .
git commit -m "fix: resolve merge conflicts"
```

### 🔴 "No encuentro los módulos mencionados"
```bash
# CAUSA: Repositorio no sincronizado
# SOLUCIÓN: Ejecutar PASO 1 completo
```

### 🔴 "Tests no funcionan"
```bash
# VERIFICAR:
python --version  # Debe ser 3.12.8
pip list | grep pytest
cd tests/
python -m pytest -v
```

---

## 📢 COMUNICACIÓN ENTRE AGENTES

### 🎯 FORMATO ESTÁNDAR DE HANDOFF
```
AGENTE ANTERIOR reporta:
- MÓDULOS ACTIVOS: [lista específica en tz_core/]
- ÚLTIMA FASE COMPLETADA: [fase específica]
- TESTS STATUS: [X/Y pasando]
- COMMITS RECIENTES: [hash] [mensaje]
- PRÓXIMO PASO SUGERIDO: [acción específica]

AGENTE NUEVO confirma:
- ✅ SYNC COMPLETADO
- ✅ MÓDULOS VERIFICADOS
- ✅ TESTS EJECUTADOS  
- ✅ DOCUMENTACIÓN LEÍDA
- 🎯 TRABAJANDO EN: [tarea específica]
```

---

## 🚀 UBICACIÓN DE ESTE PROTOCOLO

**Este archivo debe estar en:**
- ✅ `docs/development/PROTOCOLO_SYNC_OBLIGATORIO.md`
- ✅ Referenciado en `docs/README.md`
- ✅ Mencionado en `docs/planning/HANDOFF_CASA.md`
- ✅ Link en root `README.md`

---

## 💡 REGLAS DE ORO

1. **NUNCA** asumir el estado del repositorio
2. **SIEMPRE** verificar sincronización primero  
3. **OBLIGATORIO** leer documentación actualizada
4. **CONFIRMAR** estructura antes de modificar
5. **DOCUMENTAR** cambios en handoff

---

**🎯 OBJETIVO: CERO CONFUSIÓN, MÁXIMA EFICIENCIA**