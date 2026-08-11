<#
setup.ps1
Script para crear y activar un entorno virtual en Windows PowerShell.
Requiere el intérprete canónico de release: CPython 3.12.8 x64.

Uso: Ejecutar desde la raíz del repo:
    .\setup.ps1

#>
Write-Host "Iniciando setup del entorno..." -ForegroundColor Cyan

$requiredPythonIdentity = 'CPython|3.12.8|64|win-amd64'
$repoRoot = $PSScriptRoot
$venvName = '.venv312'
$venvPath = Join-Path $repoRoot $venvName
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
$runtimeRequirements = Join-Path $repoRoot 'requirements.txt'
$testRequirements = Join-Path $repoRoot 'requirements-test.txt'


# Función auxiliar: obtener el ejecutable Python 3.12 mediante el launcher.
function Get-PyExecutableByLauncher($ver) {
    try {
        $out = & py -$ver -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -Last 1).Trim() }
    } catch {}
    return $null
}

# El nombre 3.12 del launcher no garantiza el patch ni la arquitectura.
function Test-CanonicalPython($executable) {
    try {
        $identity = & $executable -c "import platform, struct, sysconfig; print('|'.join((platform.python_implementation(), platform.python_version(), str(struct.calcsize('P') * 8), sysconfig.get_platform())))" 2>$null
        return $LASTEXITCODE -eq 0 -and ($identity | Select-Object -Last 1).Trim() -eq $requiredPythonIdentity
    } catch {
        return $false
    }
}

# 1) Buscar CPython 3.12 x64 mediante py y validar 3.12.8 exacto.
$pythonExe = Get-PyExecutableByLauncher '3.12-64'
if ($pythonExe -and -not (Test-CanonicalPython $pythonExe)) {
    Write-Host "El Python 3.12 del launcher no es CPython 3.12.8 x64 (win-amd64)." -ForegroundColor Yellow
    $pythonExe = $null
}

# 2) Si 'py' no entrega el intérprete canónico, probar 'python' en PATH.
if (-not $pythonExe) {
    try {
        $pathPython = (& python -c "import sys; print(sys.executable)" 2>$null) -replace "[\r\n]+",""
        if ($LASTEXITCODE -eq 0 -and $pathPython -and (Test-CanonicalPython $pathPython)) {
            $pythonExe = $pathPython
        }
    } catch {}
}

if (-not $pythonExe) {
    Write-Host "No se encontró CPython 3.12.8 x64 (win-amd64)." -ForegroundColor Red
    Write-Host "Instala esa versión para desarrollo/build; no se admite fallback 3.11 ni otro patch de 3.12." -ForegroundColor Red
    exit 1
}

Write-Host "Usando CPython 3.12.8 x64: $pythonExe" -ForegroundColor Green

if (-not (Test-Path -LiteralPath $venvPath)) {
    Write-Host "Creando entorno virtual $venvName..." -ForegroundColor Yellow
    & $pythonExe -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { Write-Host "Error creando venv con $pythonExe" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "Entorno virtual $venvName ya existe." -ForegroundColor Yellow
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "No se encontró $venvPython después de crear el venv. Revisa permisos y rutas." -ForegroundColor Red
    exit 1
}

if (-not (Test-CanonicalPython $venvPython)) {
    Write-Host "El entorno $venvName existente no usa CPython 3.12.8 x64 (win-amd64)." -ForegroundColor Red
    Write-Host "Retíralo manualmente y vuelve a ejecutar setup.ps1." -ForegroundColor Red
    exit 1
}

Write-Host "Activando (intento) el entorno virtual..." -ForegroundColor Cyan
try {
    . (Join-Path $venvPath 'Scripts\Activate.ps1')
} catch {
    Write-Host "No se pudo activar el venv automáticamente. Ejecuta '.\\$venvName\\Scripts\\Activate.ps1' manualmente o ajusta la política de ejecución: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass" -ForegroundColor Yellow
}

Write-Host "Fijando pip 24.3.1 para el entorno canónico..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip==24.3.1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error fijando pip 24.3.1." -ForegroundColor Red
    exit 1
}

Write-Host "Instalando dependencias runtime y de pruebas con versiones exactas..." -ForegroundColor Cyan
& $venvPython -m pip install -r $testRequirements
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error instalando requirements-test.txt." -ForegroundColor Red
    exit 1
}

$expectedPackages = @(
    Get-Content -LiteralPath $runtimeRequirements -Encoding UTF8
    Get-Content -LiteralPath $testRequirements -Encoding UTF8
) | ForEach-Object { $_.Trim() } |
    Where-Object { $_ -match '^[A-Za-z0-9_.-]+==[^=].+$' } |
    Sort-Object -Unique

$installedPackages = @(& $venvPython -m pip freeze)
if ($LASTEXITCODE -ne 0) {
    Write-Host "No se pudo inventariar el entorno instalado." -ForegroundColor Red
    exit 1
}
$installedPackages = $installedPackages |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ } |
    Sort-Object -Unique

$dependencyDelta = @(Compare-Object -ReferenceObject $expectedPackages -DifferenceObject $installedPackages)
if ($dependencyDelta.Count -gt 0) {
    Write-Host "El venv contiene paquetes faltantes, sobrantes o con otra versión:" -ForegroundColor Red
    $dependencyDelta | ForEach-Object { Write-Host "  $($_.SideIndicator) $($_.InputObject)" -ForegroundColor Red }
    Write-Host "Retira manualmente $venvName y vuelve a ejecutar setup.ps1; el script no elimina entornos automáticamente." -ForegroundColor Red
    exit 1
}

Write-Host "Verificando consistencia de dependencias..." -ForegroundColor Cyan
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip check detectó dependencias incompatibles." -ForegroundColor Red
    exit 1
}

Write-Host "Setup completado. Para activar manualmente el entorno en futuras sesiones:" -ForegroundColor Green
Write-Host "    .\\$venvName\\Scripts\\Activate.ps1" -ForegroundColor Green
Write-Host "Suite completa:" -ForegroundColor Green
Write-Host "    .\\$venvName\\Scripts\\python.exe -m pytest -q" -ForegroundColor Green
