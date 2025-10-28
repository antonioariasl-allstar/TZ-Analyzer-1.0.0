# 🔄 Estrategia de Sincronización: Casa ↔ Oficina

**Fecha creación**: 27 de octubre de 2025  
**Objetivo**: Mantener sincronizados dos ambientes de trabajo sin perder cambios

---

## 📍 Situación Actual

### Dos ambientes de trabajo:
1. **CASA** - Carpeta local completa con trabajo experimental
2. **OFICINA** - Esta carpeta (C:\python_proyectos\TZ_Analysis_1.0.0_REPO)

### El problema:
- Archivos de test se generan en ambos lados (.gitignore los excluye)
- No sabes qué cambios están en qué lado
- Commits y merges pueden estar desincronizados

---

## ✅ SOLUCIÓN: Flujo de trabajo con Git como fuente de verdad

### Regla de Oro:
> **GitHub es la ÚNICA fuente de verdad**  
> Todo lo que importa DEBE estar en un commit y pusheado

---

## 🔄 Protocolo de Sincronización

### Al INICIAR sesión (Casa o Oficina):

```powershell
# 1. Ver en qué rama estás
git branch

# 2. Traer TODOS los cambios del servidor
git fetch --all --prune

# 3. Ver qué está desactualizado
git status

# 4. Si estás detrás de origin/main:
git pull origin main

# 5. Si hay conflictos, Git te lo dirá
# Resolver manualmente y luego:
git add .
git commit -m "merge: resolved conflicts"
```

### Al TERMINAR sesión:

```powershell
# 1. Ver qué cambios hiciste
git status

# 2. Ver diferencias específicas
git diff

# 3. Agregar cambios importantes (NO archivos de test)
git add script_principal_bitacoras_refactory.py
git add config.json
git add docs/
git add *.md

# 4. Commit descriptivo
git commit -m "feat: descripción clara de lo que hiciste"

# 5. Subir al servidor
git push origin main

# 6. Verificar que se subió
git status
# Debe decir: "Your branch is up to date with 'origin/main'"
```

---

## 📁 ¿Qué archivos SÍ sincronizar?

### ✅ SIEMPRE incluir:
- `script_principal_bitacoras_refactory.py`
- `utilidades.py`, `validaciones.py`, `kml_generador.py`
- `config.json`
- `requirements.txt`
- `README.md`, `TODO.md`, `HANDOFF_CASA.txt`
- `docs/*.md`
- Archivos en `tests/` que sean código (`.py`)

### ❌ NUNCA incluir (ya están en .gitignore):
- `.venv*` (entornos virtuales)
- `__pycache__/`
- `*.pyc`, `*.pyo`
- Archivos de salida (`reportes/`, `output/`, `*.kmz`, `*.html`)
- Archivos de test temporal (`test_output_*.txt`)
- `.vscode/`, `.idea/`

---

## 🚨 ¿Qué hacer si te confundiste?

### Escenario 1: No recuerdas qué cambios hiciste
```powershell
# Ver archivos modificados
git status

# Ver cambios línea por línea
git diff

# Si no entiendes los cambios, comparar con GitHub:
# Ir a: https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0/commits/main
```

### Escenario 2: Hiciste commits en casa y en oficina (divergencia)
```powershell
# Git te dirá: "Your branch and 'origin/main' have diverged"

# Opción A: Merge (conserva ambos historiales)
git pull origin main --no-rebase
# Resolver conflictos si aparecen
git add .
git commit -m "merge: integrated changes from other location"
git push origin main

# Opción B: Rebase (historial lineal, MÁS LIMPIO)
git pull origin main --rebase
# Resolver conflictos si aparecen
git add .
git rebase --continue
git push origin main
```

### Escenario 3: Hiciste cambios importantes pero no recuerdas si los commiteaste
```powershell
# Ver últimos commits
git log --oneline -10

# Buscar commits por mensaje
git log --grep="palabra clave"

# Ver cambios de un commit específico
git show <hash>

# Ejemplo:
git show 900d78c
```

### Escenario 4: Quieres empezar limpio sin perder nada
```powershell
# 1. Crear backup de seguridad
git stash save "backup antes de sincronizar"

# 2. Traer la versión del servidor
git fetch --all
git reset --hard origin/main

# 3. Ver tu backup
git stash list

# 4. Si necesitas algo del backup:
git stash show
git stash pop  # Aplica el backup
```

---

## 📝 Checklist Antes de Cambiar de Ubicación

### Antes de irte de OFICINA:
- [ ] `git status` (ver si hay cambios pendientes)
- [ ] `git add` (archivos importantes)
- [ ] `git commit -m "..."`
- [ ] `git push origin main`
- [ ] Actualizar `HANDOFF_CASA.txt` con estado actual
- [ ] Commit del HANDOFF: `git add HANDOFF_CASA.txt && git commit -m "docs: updated handoff" && git push`

### Antes de irte de CASA:
- [ ] `git status`
- [ ] `git add` (archivos importantes)
- [ ] `git commit -m "..."`
- [ ] `git push origin main`
- [ ] Actualizar `HANDOFF_CASA.txt`
- [ ] Commit del HANDOFF

### Al llegar a OFICINA/CASA:
- [ ] `git fetch --all`
- [ ] `git pull origin main`
- [ ] Leer `HANDOFF_CASA.txt`
- [ ] Continuar trabajo

---

## 🎯 Estrategia de Ramas (Recomendado)

Para evitar conflictos, puedes usar ramas separadas:

```powershell
# En CASA:
git checkout -b trabajo-casa
# ... hacer cambios ...
git add .
git commit -m "feat: cambios hechos en casa"
git push origin trabajo-casa

# En OFICINA:
git checkout -b trabajo-oficina
# ... hacer cambios ...
git add .
git commit -m "feat: cambios hechos en oficina"
git push origin trabajo-oficina

# Cuando quieras unificar (desde cualquier lado):
git checkout main
git pull origin main
git merge trabajo-casa
git merge trabajo-oficina
# Resolver conflictos si hay
git push origin main
```

---

## 🔍 Comandos Útiles de Diagnóstico

```powershell
# Ver estado completo
git status -v

# Ver diferencias con el servidor
git fetch
git diff main origin/main

# Ver historial gráfico
git log --oneline --graph --all -20

# Ver qué archivos cambiaron en último commit
git show --name-only

# Ver rama actual y tracking
git branch -vv

# Ver todos los remotos
git remote -v
```

---

## 🆘 SOS: Comandos de Emergencia

### Si todo está muy confundido:
```powershell
# 1. Crear snapshot completo de tu carpeta actual
# (Copiar toda la carpeta a C:\backup_TZ_yyyy_mm_dd\)

# 2. Clonar repositorio fresco
cd C:\python_proyectos\
git clone https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0.git TZ_FRESH

# 3. Comparar carpetas y copiar manualmente archivos importantes
# (script principal, config, docs)

# 4. Hacer commit limpio desde la carpeta fresca
cd TZ_FRESH
git add .
git commit -m "sync: manual merge from local changes"
git push origin main
```

---

## 📞 Comunicación con IA Agents

Cuando trabajes con un agente de IA, dale este contexto:

```
Estoy trabajando en TZ-Analyzer-1.0.0.
Tengo dos ambientes (casa/oficina).
Por favor, antes de hacer cambios:
1. Verifica git status
2. Verifica git log --oneline -5
3. Lee HANDOFF_CASA.txt
4. Pregúntame si hay dudas sobre sincronización
```

---

## ✅ Resumen de Mejores Prácticas

1. **SIEMPRE** `git pull` al empezar
2. **SIEMPRE** `git push` al terminar
3. **NUNCA** forzar push (`git push -f`) a menos que sepas lo que haces
4. **ACTUALIZAR** `HANDOFF_CASA.txt` en cada sesión
5. **USAR** commits descriptivos
6. **VERIFICAR** `git status` frecuentemente
7. **BACKUP** manual antes de operaciones complejas

---

**Creado**: 2025-10-27  
**Mantenedor**: GitHub Copilot + Usuario  
**Última actualización**: 2025-10-27
