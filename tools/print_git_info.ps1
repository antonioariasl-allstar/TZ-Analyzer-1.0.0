# print_git_info.ps1
# Muestra la rama actual y el commit SHA corto para pegar en HANDOFF.md

try {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    $sha = git rev-parse --short HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "No se pudo obtener información de git. Asegúrate de ejecutar desde un repo git." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Branch: $branch"
    Write-Host "Commit: $sha"
} catch {
    Write-Host "Error al ejecutar git: $_" -ForegroundColor Red
    exit 2
}
