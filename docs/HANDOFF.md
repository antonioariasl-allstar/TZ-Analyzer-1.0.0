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

## Configuración rápida (PowerShell)
> Ejecuta todo desde la raíz del repo: `c:\python_proyectos\TZ_Analysis_1.0.0_REPO`.

```powershell
# 1) Verifica Python 3.12
py -3.12 --version

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
