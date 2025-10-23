<#
setup.ps1
Script para crear y activar un entorno virtual en Windows PowerShell.
Intenta usar Python 3.12 y cae a 3.11 si no está disponible.

Uso: Ejecutar desde la raíz del repo:
    .\setup.ps1

#>
Write-Host "Iniciando setup del entorno..." -ForegroundColor Cyan


# Función auxiliar: intentar obtener el ejecutable Python para una versión con 'py'
function Get-PyExecutableByLauncher($ver) {
    try {
        $out = & py -$ver -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
    } catch {}
    return $null
}

# 1) Buscar py -3.12, luego py -3.11
$pythonExe = Get-PyExecutableByLauncher '3.12'
if (-not $pythonExe) { $pythonExe = Get-PyExecutableByLauncher '3.11' }

# 2) Si 'py' no está disponible, intentar 'python' en PATH y comprobar versión
if (-not $pythonExe) {
    try {
        $ver = & python -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) {
            $ver = $ver.Trim()
            if ($ver -in @('3.12','3.11')) {
                $pythonExe = (& python -c "import sys; print(sys.executable)") -replace "[\r\n]+",""
            }
        }
    } catch {}
}

if (-not $pythonExe) {
    Write-Host "No se encontró un ejecutable Python 3.12/3.11 automático. Instala Python o ajusta el script para apuntar a un ejecutable específico." -ForegroundColor Red
    exit 1
}

Write-Host "Usando ejecutable Python: $pythonExe" -ForegroundColor Green

$venvName = '.venv312'
if (-not (Test-Path $venvName)) {
    Write-Host "Creando entorno virtual $venvName..." -ForegroundColor Yellow
    & $pythonExe -m venv $venvName
    if ($LASTEXITCODE -ne 0) { Write-Host "Error creando venv con $pythonExe" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "Entorno virtual $venvName ya existe." -ForegroundColor Yellow
}

# Ruta al python dentro del venv
$venvPython = Join-Path $venvName 'Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host "No se encontró $venvPython después de crear el venv. Revisa permisos y rutas." -ForegroundColor Red
    exit 1
}

Write-Host "Activando (intento) el entorno virtual..." -ForegroundColor Cyan
try {
    .\$venvName\Scripts\Activate.ps1
} catch {
    Write-Host "No se pudo activar el venv automáticamente. Ejecuta '.\\$venvName\\Scripts\\Activate.ps1' manualmente o ajusta la política de ejecución: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass" -ForegroundColor Yellow
}

Write-Host "Actualizando pip e instalando dependencias usando el python del venv..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

Write-Host "Creando requirements.lock (freeze) con el python del venv..." -ForegroundColor Cyan
& $venvPython -m pip freeze | Out-File -FilePath requirements.lock -Encoding utf8

Write-Host "Setup completado. Para activar manualmente el entorno en futuras sesiones:" -ForegroundColor Green
Write-Host "    .\\$venvName\\Scripts\\Activate.ps1" -ForegroundColor Green
