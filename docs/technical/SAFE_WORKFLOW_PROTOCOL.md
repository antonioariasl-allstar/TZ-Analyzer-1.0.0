# 🚨 PROTOCOLO DE TRABAJO SEGURO - NO MÁS MAIN DIRECTO

## REGLA DE ORO: NUNCA TRABAJAR EN MAIN

### ✅ FLUJO CORRECTO OBLIGATORIO

```bash
# 1. SIEMPRE crear branch desde main limpio
git checkout main
git pull origin main
git checkout -b feature/nombre-descriptivo

# 2. Trabajar SOLO en la branch feature
git add .
git commit -m "descripción clara"

# 3. Push a branch remota (NO main)
git push origin feature/nombre-descriptivo

# 4. Crear Pull Request en GitHub
# 5. Review + CI verification
# 6. Merge SOLO después de aprobación
```

### ❌ PROHIBIDO TERMINANTEMENTE

```bash
git checkout main          # ❌ NO trabajar aquí
git commit -m "cambio"     # ❌ NO commitear en main
git push origin main       # ❌ NO pushear directo a main
```

## PROTECCIONES A IMPLEMENTAR

### 1. Branch Protection Rules (GitHub)
- [ ] Require pull request reviews
- [ ] Require status checks (CI) 
- [ ] Require branches to be up to date
- [ ] Restrict pushes to main

### 2. Git Hooks Locales
- [ ] pre-push hook que bloquee push directo a main
- [ ] mensaje de warning si estás en main

### 3. Workflow Mental
- [ ] ANTES de cualquier trabajo: ¿Estoy en branch feature?
- [ ] ANTES de commit: ¿Es esto para una branch feature?
- [ ] ANTES de push: ¿Voy a una branch NO-main?

## NOMBRES DE BRANCH ESTÁNDAR

```
feature/funcionalidad-nueva
bugfix/descripcion-problema  
hotfix/emergencia-critica
refactor/area-especifica
docs/tipo-documentacion
```

## COMANDOS DE VERIFICACIÓN

```bash
# Verificar branch actual
git branch

# Verificar que NO estés en main
git branch | grep "^\*" | grep -v main || echo "⚠️  ESTÁS EN MAIN - CAMBIA YA"

# Crear branch inmediatamente si estás en main
git checkout -b feature/trabajo-actual
```

---
**COMPROMISO:** Nunca más trabajar directamente en main. 
**CONSECUENCIA:** Si se viola, revertir inmediatamente todo el trabajo.