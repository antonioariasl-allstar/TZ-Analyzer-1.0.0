# Ejecuta análisis estático localmente en Windows PowerShell
Write-Host "== Flake8 (errores duros) =="
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

Write-Host "== Flake8 (estilo, no bloqueante) =="
flake8 . --count --exit-zero --max-complexity=30 --max-line-length=120 --statistics

Write-Host "== mypy =="
mypy . --install-types --non-interactive || Write-Host "mypy terminó con advertencias"

Write-Host "== vulture =="
vulture . --min-confidence 60 | Tee-Object -FilePath .\reports\vulture.txt

Write-Host "== radon =="
radon cc -s -a . | Tee-Object -FilePath .\reports\radon_cc.txt
radon mi . | Tee-Object -FilePath .\reports\radon_mi.txt

Write-Host "== bandit =="
bandit -r -q . -f txt -o .\reports\bandit.txt

Write-Host "Reportes en carpeta .\\reports"