# Entorno canónico de release v1

Este documento define el entorno reproducible para desarrollar, probar y
construir TZ Analyzer v1. No impone Python al usuario final de la aplicación
empaquetada.

## Plataforma canónica

- Sistema operativo de desarrollo/build: Windows x64.
- Intérprete: CPython 3.12.8 x64 exacto.
- Instalador de paquetes: pip 24.3.1.
- Formato Excel de entrada soportado: `.xlsx`.
- pandas: 2.2.2.

No se admite como baseline de v1 otro patch de Python 3.12, Python 3.11 ni
Python 3.13. La compatibilidad con pandas 3 y `StringDtype` queda como deuda
futura y no forma parte de este contrato.

## Dependencias runtime

`requirements.txt` es la fuente autoritativa del runtime y usa únicamente
versiones exactas:

```text
blinker==1.9.0
click==8.4.2
colorama==0.4.6
et_xmlfile==2.0.0
Flask==3.1.3
itsdangerous==2.2.0
Jinja2==3.1.6
MarkupSafe==3.0.3
numpy==2.3.4
openpyxl==3.1.5
pandas==2.2.2
python-dateutil==2.9.0.post0
pytz==2025.2
simplekml==1.3.6
six==1.17.0
tzdata==2025.2
Werkzeug==3.1.8
```

`colorama` se fija porque es una dependencia runtime condicional de Click en
Windows. TZ Analyzer no contiene imports ni funciones activas que requieran
`lxml`, `pillow` o `xlsxwriter`; eran residuos del árbol histórico de
`python-pptx` y no forman parte del entorno canónico.

## Dependencias de pruebas

`requirements-test.txt` incluye el runtime anterior y fija pytest y todas sus
dependencias transitivas aplicables a CPython 3.12 en Windows.

## Recreación

Desde la raíz del repositorio, en PowerShell:

```powershell
# Verificar implementación, versión y plataforma antes de continuar.
py -3.12-64 -c "import platform, struct, sys, sysconfig; assert platform.python_implementation() == 'CPython' and sys.version_info[:3] == (3, 12, 8) and struct.calcsize('P') * 8 == 64 and sysconfig.get_platform() == 'win-amd64'"
if ($LASTEXITCODE -ne 0) { throw "Se requiere CPython 3.12.8 x64 (win-amd64)" }

if (Test-Path -LiteralPath '.\.venv312') { throw "Retire manualmente .venv312 antes de recrear el entorno" }
py -3.12-64 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install --upgrade pip==24.3.1
.\.venv312\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv312\Scripts\python.exe -m pip check
```

`setup.ps1` automatiza el mismo contrato y falla si el intérprete o un venv
preexistente no es CPython 3.12.8 x64. También rechaza paquetes faltantes,
sobrantes o con otra versión; no elimina automáticamente el entorno. El script
fija explícitamente pip 24.3.1 y no genera un `requirements.lock` local no
versionado.

## Validación

```powershell
.\.venv312\Scripts\python.exe -m pytest tests/web -q
.\.venv312\Scripts\python.exe -m pytest -q
git diff --check
```

Criterio de suite verde para release:

- cero pruebas fallidas;
- el único skip histórico conocido puede permanecer si conserva su razón;
- `pip check` sin dependencias rotas;
- ninguna modificación involuntaria producida por las pruebas.

El golden KML se compara mediante canonicalización XML. Diferencias léxicas
equivalentes, como una comilla literal frente a `&quot;` dentro de texto XML,
deben pasar; cambios semánticos en elementos, atributos o coordenadas deben
fallar. Los archivos golden no se actualizan solo por cambiar de serializador.
