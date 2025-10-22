<#
setup_env.ps1
Automatiza la creación de un virtualenv con Python 3.12.8, instalación de dependencias
y ejecución de la auditoría mínima del proyecto.

Uso (PowerShell):
  #1 Ejecutar con el Python por defecto del PATH
  .\scripts\setup_env.ps1

  #2 Especificar ejecutable Python (p.ej. ruta a python 3.12.8)
  .\scripts\setup_env.ps1 -PythonExe 'C:\\Python312\\python.exe' -VenvName '.env312'

Parámetros:
  -PythonExe: Ruta o alias al ejecutable Python a usar (por defecto: 'python')
  -VenvName: Nombre de la carpeta del virtualenv a crear (por defecto: '.env312')
  -InstallRequirements: Switch, instalará paquetes desde requirements.txt si existe
  -RunAudit: Switch, ejecutará tests/audit_kml_checks.py al final si existe
#>

param(
    [string]$PythonExe = 'python',
    [string]$VenvName = '.env312',
    [switch]$InstallRequirements = $true,
    [switch]$RunAudit = $true
)

function Write-Ok($msg){ Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg){ Write-Host "[ERR] $msg" -ForegroundColor Red }

# 1) Verificar ejecutable Python
try{
    $ver = & $PythonExe --version 2>&1
    Write-Ok "Python detectado: $ver"
} catch {
    Write-Err "No se pudo ejecutar '$PythonExe'. Asegúrate de que la ruta es correcta o instala Python 3.12.8."
    exit 1
}

if ($ver -notmatch '3\.12'){
    Write-Warn "La versión detectada no es 3.12.x. Continuando, pero revisa compatibilidad. (Detectado: $ver)"
}

# 2) Crear virtualenv
if (Test-Path $VenvName){
    Write-Warn "La carpeta '$VenvName' ya existe. Se conservará (no se sobrescribirá)."
} else {
    Write-Host "Creando virtualenv '$VenvName' con $PythonExe ..."
    & $PythonExe -m venv $VenvName
    if ($LASTEXITCODE -ne 0){ Write-Err "Error creando virtualenv"; exit 1 }
    Write-Ok "Virtualenv creado: $VenvName"
}

# 3) Activar entorno (en esta sesión)
$activate = Join-Path $VenvName 'Scripts\Activate.ps1'
if (Test-Path $activate){
    Write-Host "Activando entorno: $activate"
    . $activate
} else {
    Write-Err "No se encontró el script de activación: $activate"
    exit 1
}

# 4) Actualizar pip e instalar requirements
& python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0){ Write-Warn "Fallo actualizando pip/setuptools/wheel" }

if ($InstallRequirements -and (Test-Path 'requirements.txt')){
    Write-Host "Instalando dependencias desde requirements.txt ..."
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0){ Write-Warn "La instalación de dependencias devolvió un error. Revisa la salida." }
    else { Write-Ok "Dependencias instaladas" }
} else {
    Write-Warn "No se instalaron dependencias: requirements.txt no encontrado o -InstallRequirements false"
}

# 5) pip check
try{
    pip check
} catch { Write-Warn "pip check devolvió un error o no hay paquetes instalados" }

# 6) Ejecutar auditoría si existe
if ($RunAudit -and (Test-Path 'tests/audit_kml_checks.py')){
    Write-Host "Ejecutando auditoría: tests/audit_kml_checks.py"
    python tests/audit_kml_checks.py
} else {
    Write-Warn "No se ejecutó auditoría: archivo no encontrado o -RunAudit false"
}

# 7) Sugerencia VS Code
$vscodeFolder = Join-Path '.vscode' 'settings.json'
if (-not (Test-Path '.vscode')){ New-Item -ItemType Directory -Path '.vscode' | Out-Null }
$settings = @{ 'python.defaultInterpreterPath' = "${PWD}\$VenvName\Scripts\python.exe" }
$settings | ConvertTo-Json | Out-File -Encoding UTF8 $vscodeFolder
Write-Ok "Archivo .vscode/settings.json generado. Selecciona el intérprete en VS Code si es necesario."

Write-Host "\n---\nListo. Para activar manualmente en esta sesión usa:` .\$VenvName\Scripts\Activate.ps1`"
Write-Host "Para desactivar: `deactivate`"

Write-Ok "script setup_env.ps1 finalizado"