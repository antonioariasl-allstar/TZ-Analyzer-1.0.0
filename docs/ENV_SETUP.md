# Configuración de entorno (Windows PowerShell) - Python 3.12.8

Este documento explica cómo crear un entorno virtual local con Python 3.12.8,
instalar dependencias y configurar VS Code para usarlo.

Requisitos previos
- Python 3.12.8 instalado en el sistema. Si no lo tienes: https://www.python.org/downloads/
- PowerShell
- VS Code (opcional)

1) Crear un virtualenv dentro del proyecto (recomendado: `.venv`)

Abre PowerShell en la carpeta raíz del proyecto y ejecuta:

```powershell
# Crear entorno virtual con el ejecutable de Python 3.12.8
python -m venv .venv

# Activar el entorno
.\.venv\Scripts\Activate.ps1

# Verificar versión
python --version
```

Nota: si tienes múltiples versiones de Python, reemplaza `python` por la ruta al 3.12.8,
por ejemplo: `C:\Python312\python.exe -m venv .venv`.

2) Instalar dependencias del proyecto

```powershell
# Activado el entorno
pip install --upgrade pip
pip install -r requirements.txt

# Verificar compatibilidad de paquetes
pip check
```

3) Configurar VS Code

- Abre la carpeta del proyecto en VS Code
- Presiona Ctrl+Shift+P → "Python: Select Interpreter" → selecciona ".venv\Scripts\python.exe"
- (Opcional) crea `.vscode/settings.json` con:

```json
{
  "python.pythonPath": ".venv\\Scripts\\python.exe",
  "python.defaultInterpreterPath": ".venv\\Scripts\\python.exe"
}
```

4) Ejecutar pruebas de compatibilidad

```powershell
# Activar entorno
.\.venv\Scripts\Activate.ps1

# Ejecutar auditoría
python tests/audit_kml_checks.py
```

5) Añadir notas de Copilot u otros txt

Coloca cualquier archivo de notas dentro de `docs/` para que no lo ignore `.gitignore`.

---

Si quieres, puedo generar un script PowerShell que automatice estos pasos y lo añadimos al repo.