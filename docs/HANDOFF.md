# Handoff y guía de entorno

Este documento es la bitácora de comunicación y relevo entre sesiones/equipos. Úsalo para: qué cambió, cómo continuar, comandos, rama activa, y próximos pasos.

## Objetivo rápido
- Poner a punto el entorno en Windows (PowerShell) y ejecutar el proyecto.
- Dejar un rastro claro de lo que se hizo y lo que sigue.

## Requisitos del entorno
- Windows 10/11
- Python 3.12.x instalado en el sistema
- PowerShell (predeterminado)
- Git configurado (con acceso al repo)
- Conexión a Internet (Leaflet y el plugin de calor se cargan vía CDN en los reportes HTML)

Nota: si en tu laptop personal no tienes Python 3.12 instalado, las instrucciones más abajo incluyen una ruta de fallback para Python 3.11. Ajusta la versión (`py -3.12` → `py -3.11`) según lo que tengas disponible.

## Configuración rápida (PowerShell)
> Ejecuta todo desde la raíz del repo (ajusta la ruta a tu equipo): por ejemplo `c:\Users\Omar Arias\OneDrive - mail.utec.edu.sv\Documentos\GitHub\TZ-Analysis-1.0.0`.

```powershell
# 1) Verifica Python 3.12
py -3.12 --version

# Si no tienes 3.12, intenta 3.11 como fallback:
# py -3.11 --version

# 2) Crea el entorno virtual
py -3.12 -m venv .venv312

# 3) Activa el entorno virtual
.\.venv312\Scripts\Activate.ps1
# Si tu política de ejecución lo bloquea temporalmente:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4) Actualiza pip y dependencias
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si prefieres automatizar estos pasos, en la raíz del repo hay un script `setup.ps1` que intenta usar Python 3.12 y cae a 3.11 si es necesario. Ejecuta `.
setup.ps1` desde PowerShell (con permisos de ejecución para el proceso) para crear/activar el venv e instalar dependencias.

## Sincronización de código (rama activa)
```powershell
git fetch --all
# Rama de trabajo actual
git checkout exploracion-movilidad
# Trae últimos cambios
git pull
```

## Ejecución y verificación rápida
```powershell
# Opción A: script principal
python script_principal_bitacoras_refactory.py

# Opción B: runner si aplica
python run.py
```
- Salida esperada: generación del reporte HTML (con índice, secciones de antenas, "Mapa de calor de actividad" con pines Top, y "Contactos").
- Nota: el mapa usa Leaflet + heatlayer desde CDN; requiere Internet para que se vean las teselas/capas.

## Estructura y archivos clave
- `script_principal_bitacoras_refactory.py`: genera el reporte HTML y artefactos.
- `config.json`: branding/texto legal del reporte.
- `requirements.txt`: dependencias de Python.
- `docs/`: documentación del proyecto.

## Bitácora de relevo (plantilla)
Copia y pega este bloque en cada pase de relevo.

```
[FECHA y HORA]
Contexto: ¿qué se hizo en este bloque?
Cambios relevantes: ramas, archivos, secciones HTML afectadas.
Cómo probar: comandos ejecutados, datos usados, resultado esperado.
Pendientes inmediatos: bullets cortos.
Riesgos/Notas: observaciones, TODOs, decisiones tomadas.
Responsable: nombre/alias.
```

Por favor, incluir siempre estos campos cuando se haga un relevo:
- Rama/Branch: (ej. `exploracion-movilidad`)
- Commit SHA (corto): (ej. `a1b2c3d`) — permite identificar el estado exacto del repo.

## Próximo paso prioritario
- Historial de cambios de antena:
  - Extraer secuencia de saltos (origen → destino, timestamp, distancia) desde el DataFrame principal, orden cronológico.
  - Generar bloque HTML con encabezado, nota explicativa y tabla; insertar tras las tablas de antenas.
  - Validar que no rompe el índice ni el orden actual (debe quedar después de "Antenas más activadas"/heatmap y antes de "Contactos", según decisión final).

## Solución de problemas
- Activación del venv bloqueada por políticas:
  - Usar: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y reintentar activar.
- Dependencias que faltan:
  - Ejecuta de nuevo `pip install -r requirements.txt` con el venv activo.
- Mapas no se ven:
  - Verifica conexión a Internet (Leaflet/teselas/heat se cargan por CDN).

---
Documento vivo. Mantén este archivo actualizado en cada relevo.

## Registro corto de la sesión (para el siguiente relevo)

[FECHA: 2025-10-22]
- Responsable: sesión con asistente VSCode (local)
- Acciones realizadas:
  - Añadido `setup.ps1` para crear/activar `.venv312` e instalar dependencias.
  - Añadida `.vscode/settings.json` apuntando al intérprete del venv.
  - Agregado script `tools/move_ip_backup.ps1` para mover restos `~ip*` a `.venv312\site-packages-backup`.
  - Movidos `~ip` y `~ip-24.3.1.dist-info` al backup y verificado que `pip list` y `pip check` no reportan problemas.
- Pendientes/no logrados:
  - No se ejecutó la suite de tests completa con `pytest` (pytest no estaba instalado en el venv local). Se recomienda instalar `pytest` localmente si se quiere CI local.
  - No se automatizó la interacción completa de `run.py` (el script es interactivo y requiere respuestas de usuario para color, modo, intervalo, etc.).
- Recomendaciones para proteger/reproducir el proyecto (mínimo y al grano):
  1) Mantener `requirements.txt` y además generar/commitear `requirements.lock` (output de `pip freeze`) para reproducibilidad exacta.
  2) Añadir `tools/move_ip_backup.ps1` a la documentación y usarlo antes de borrar venvs; mejor mover que borrar sin revisar.
  3) Evitar ubicar el repo en carpetas con sincronización automática (OneDrive/Dropbox) para evitar ficheros temporales en `site-packages` y contenciones de I/O; si se queda en OneDrive, documentar la política de exclusión o usar una copia local para venvs.
  4) Incluir `python -m pip install pytest` como paso de verificación en `setup.ps1` o un `dev-requirements.txt` para pruebas.
  5) Documentar en HANDOFF.md cómo ejecutar `run.py` en modo no interactivo (si existe flag) o proveer un runner `run_noninteractive.py` con valores por defecto para CI.
  6) Añadir un simple `check_env.ps1` que compruebe presencia de `.venv312`, `python.exe` e `requirements.lock` y falle con código de salida si falta algo (útil para CI).

Si quieres, pongo estos cambios en un commit y doy instrucciones rápidas para que el otro asistente los recoja.
