# 📥 Guía de Instalación - TZ Analyzer

## Requisitos del Sistema

### Software Requerido
- **Python 3.12.8** (versión oficial del proyecto)
- **Git** (para clonar el repositorio)
- **10 GB** de espacio en disco (mínimo)
- **4 GB RAM** (mínimo, 8 GB recomendado)

### Sistemas Operativos Soportados
- ✅ Windows 10/11
- ✅ macOS 10.15+
- ✅ Linux (Ubuntu 20.04+, Debian, etc.)

---

## 📋 Instalación Paso a Paso

### 1. Instalar Python 3.12.8

#### Windows:
```powershell
# Descargar desde python.org
# https://www.python.org/downloads/release/python-3128/

# Verificar instalación
python --version
# Debe mostrar: Python 3.12.8
```

#### macOS:
```bash
# Usando Homebrew
brew install python@3.12

# Verificar
python3 --version
```

#### Linux:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv

# Verificar
python3.12 --version
```

---

### 2. Clonar el Repositorio

```bash
# Navegar a tu carpeta de proyectos
cd ~/proyectos  # Linux/Mac
cd C:\proyectos  # Windows

# Clonar repositorio
git clone https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0.git

# Entrar a la carpeta
cd TZ-Analyzer-1.0.0
```

---

### 3. Crear Entorno Virtual

#### Windows (PowerShell):
```powershell
# Crear entorno virtual
python -m venv .venv312

# Activar entorno
.venv312\Scripts\Activate.ps1

# Si hay error de políticas de ejecución:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Linux/macOS:
```bash
# Crear entorno virtual
python3.12 -m venv .venv312

# Activar entorno
source .venv312/bin/activate
```

---

### 4. Instalar Dependencias

```bash
# Actualizar pip
pip install --upgrade pip

# Instalar dependencias del proyecto
pip install -r requirements.txt

# Verificar instalación
pip list
```

### Dependencias Principales:
- `pandas` - Procesamiento de datos
- `simplekml` - Generación de archivos KML/KMZ
- `openpyxl` - Lectura de archivos Excel
- `pillow` - Procesamiento de imágenes (logo)

---

### 5. Verificar Instalación

```bash
# Ejecutar script principal
python script_principal_bitacoras_refactory.py

# Debería aparecer el menú principal
```

---

## ✅ Verificación de la Instalación

### Test Rápido:
```bash
# Ejecutar tests de regresión
python tests/test_e2e_regresion.py

# Si todo está bien, deberías ver:
# ✓ Test 1: PASSED
# ✓ Test 2: PASSED
# ...
```

---

## 🐛 Solución de Problemas Comunes

### Error: "Python no reconocido"
**Solución**: Agregar Python al PATH del sistema
- Windows: Reinstalar Python marcando "Add Python to PATH"
- Linux/Mac: Agregar al `.bashrc` o `.zshrc`

### Error: "No module named 'pandas'"
**Solución**: 
```bash
# Verificar que el entorno virtual esté activado
# Debería aparecer (.venv312) en el prompt
pip install -r requirements.txt
```

### Error: "Permission denied" al activar entorno (Windows)
**Solución**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Error: "simplekml not found"
**Solución**:
```bash
pip install simplekml==1.3.6
```

---

## 🔄 Actualización

Para actualizar a la última versión:

```bash
# Guardar cambios locales (si los hay)
git stash

# Actualizar repositorio
git pull origin main

# Reinstalar dependencias (por si hay nuevas)
pip install -r requirements.txt

# Restaurar cambios locales
git stash pop
```

---

## 📂 Estructura de Archivos Instalados

```
TZ-Analyzer-1.0.0/
├── .venv312/                    ← Entorno virtual (NO tocar)
├── config.json                  ← Configuración del sistema
├── script_principal_bitacoras_refactory.py  ← Script principal
├── requirements.txt             ← Dependencias
├── docs/                        ← Documentación
├── tests/                       ← Tests
└── tz_core/                     ← Framework modular
```

---

## ⚙️ Configuración Inicial (Opcional)

### Personalizar `config.json`:

```json
{
  "style": {
    "theme_hex": "#ff00ff",  ← Color tema (cambiar si deseas)
    "pin_scale": 1.1
  },
  "brand": {
    "logo_path": "Logo TZ.png"  ← Ruta a tu logo
  }
}
```

---

## ✅ Checklist de Instalación

- [ ] Python 3.12.8 instalado
- [ ] Repositorio clonado
- [ ] Entorno virtual creado y activado
- [ ] Dependencias instaladas
- [ ] Script principal ejecuta correctamente
- [ ] Tests de regresión pasan

---

## 📞 ¿Problemas?

Si tienes problemas con la instalación:
1. Consulta el [FAQ](FAQ.md)
2. Revisa los [Issues de GitHub](https://github.com/antonioariasl-allstar/TZ-Analyzer-1.0.0/issues)
3. Crea un nuevo issue con detalles del error

---

## ➡️ Siguiente Paso

Una vez instalado, continúa con la **[Guía de Uso Básico](GUIA_USO_BASICO.md)**
