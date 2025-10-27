# 🛡️ GUÍA: Configuración Branch Protection en GitHub

**⚠️ CRÍTICO:** Estas reglas previenen el error que casi cometemos (trabajar directo en main)

## 📋 Pasos para configurar en GitHub.com:

### 1. Ir a Settings del repositorio
```
https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0/settings/branches
```

### 2. Hacer clic en "Add rule" 

### 3. Configurar regla para rama `main`:

#### **Branch name pattern:**
```
main
```

#### **✅ Protecciones OBLIGATORIAS a activar:**

- [x] **Restrict pushes that create files greater than 100 MB**
- [x] **Require a pull request before merging**
  - [x] Require approvals: **1**
  - [x] Dismiss stale PR approvals when new commits are pushed
  - [x] Require review from code owners
- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - Buscar y agregar: `tests-windows` (de nuestro CI)
- [x] **Require conversation resolution before merging**
- [x] **Restrict pushes that create files greater than 100 MB**

#### **🚫 Protecciones OPCIONALES (recomendadas):**

- [x] **Require signed commits** (seguridad extra)
- [x] **Include administrators** (nadie puede saltarse las reglas)
- [x] **Allow force pushes** = ❌ **DISABLED**
- [x] **Allow deletions** = ❌ **DISABLED**

### 4. Hacer clic en "Create" para guardar

---

## 🎯 **Resultado esperado:**

✅ **Imposible hacer push directo a main**  
✅ **Obligatorio usar Pull Requests**  
✅ **CI debe pasar antes de merge**  
✅ **Requiere 1 review de aprobación**  

---

## 🚨 **Workflow futuro obligatorio:**

```bash
# ✅ Así SÍ (seguro)
git checkout main
git pull origin main
git checkout -b feature/nueva-funcionalidad
# ... trabajar ...
git push origin feature/nueva-funcionalidad
# Crear PR en GitHub, esperar review y CI green, luego merge

# ❌ Así NO (será rechazado)
git checkout main
git commit -m "cambio directo"
git push origin main  # <- RECHAZADO por branch protection
```

---

**⚠️ IMPORTANTE:** Una vez configurado, ya no podremos hacer push directo a main. **¡Esto es exactamente lo que queremos!**