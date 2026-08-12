"""tz_core.folder_dialog — selector nativo de carpeta en subprocess aislado.

MICROBLOQUE 6: invoca el diálogo de carpeta de Windows en un proceso hijo
separado, nunca dentro del hilo/proceso del servidor Waitress.

Por qué un subprocess y no Tkinter embebido en el proceso del servidor
(como hacía ``tz_core.ui_utils.seleccionar_carpeta`` en el flujo de
consola): Waitress despacha cada petición en uno de un pool fijo de hilos
de trabajo (``tz_web.server.ManagedServer`` usa ``threads=4``); un diálogo
modal es, por naturaleza, una espera de duración indefinida controlada por
el usuario. Si esa espera ocurriera dentro de un hilo de Waitress con
Tkinter inicializado en ese mismo proceso, arriesgaría: (a) agotar el pool
de hilos si el usuario tarda o dos peticiones concurrentes intentan abrir
un diálogo a la vez — Tkinter no soporta múltiples intérpretes ``Tk()``
concurrentes de forma fiable entre hilos distintos de un mismo proceso —, y
(b) interferir con el bucle de aceptación de conexiones o el mecanismo de
cierre (``tz_web.server._drain_and_close``), que ya depende de un manejo
cuidadoso de qué corre en qué hilo. Un subprocess aislado evita ambos
problemas: el diálogo corre en su propio intérprete Python, con su propio
GIL y su propio bucle de eventos Tk, y solo el hilo de Waitress que atendió
esta petición particular se bloquea esperando su salida (uno de los 4 del
pool, nunca el proceso completo ni el bucle de aceptación) — acotado además
por ``timeout``, para nunca bloquear indefinidamente el backend.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from tz_core.user_paths import is_frozen

# Contrato de códigos de salida del script auxiliar (ver
# tz_folder_dialog_helper.py, única fuente de verdad de estos valores).
_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_CANCELLED = 3
_EXIT_NO_GUI = 4

_HELPER_SCRIPT_NAME = "tz_folder_dialog_helper.py"

# Plazo por defecto para que el usuario decida en el diálogo. Generoso a
# propósito (no es una operación que deba "sentirse" instantánea) pero
# acotado: nunca debe poder colgar el hilo de Waitress que lo espera para
# siempre (sección de seguridad/concurrencia del encargo MB6).
DEFAULT_TIMEOUT_SECONDS = 600.0


class FolderDialogUnavailableError(RuntimeError):
    """El selector nativo no pudo invocarse o terminó de forma anómala.

    Nunca se lanza por cancelación del usuario (eso es un resultado válido,
    ``pick_folder`` devuelve ``None``) — solo cuando el subproceso no pudo
    arrancar, no respondió a tiempo, no tiene GUI disponible, o terminó con
    un error inesperado.
    """


def _default_helper_script() -> Path:
    return Path(__file__).resolve().parent.parent / _HELPER_SCRIPT_NAME


def pick_folder(
    *,
    initial_dir: Optional[str] = None,
    title: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    helper_script: Optional[Path] = None,
    run_subprocess: Callable[..., "subprocess.CompletedProcess[str]"] = subprocess.run,
    is_frozen_fn: Callable[[], bool] = is_frozen,
) -> Optional[str]:
    """Abre el selector nativo de carpetas en un subproceso aislado.

    Devuelve la ruta elegida, o ``None`` si el usuario canceló el diálogo
    (resultado válido, no un error). Lanza ``FolderDialogUnavailableError``
    para cualquier otra condición que impida completar la selección.

    ``run_subprocess``/``is_frozen_fn``/``helper_script`` son inyectables
    para poder probar cada rama (éxito/cancelación/timeout/error) sin
    depender de un entorno gráfico real ni de Tkinter.
    """
    if is_frozen_fn():
        # Empaquetado PyInstaller ONEDIR: fuera de alcance de MB6 (el
        # encargo excluye explícitamente el empaquetado en esta entrega).
        # Cuando se implemente, este proceso deberá reinvocarse a sí mismo
        # (``sys.executable`` ya apunta al propio ejecutable empaquetado)
        # con un argumento dedicado que ejecute únicamente
        # ``tz_folder_dialog_helper.main()`` antes de levantar Flask/
        # Waitress — mismo contrato de códigos de salida que el path de
        # abajo, sin depender de un intérprete de Python separado en disco.
        raise FolderDialogUnavailableError(
            "El selector nativo de carpetas en modo empaquetado se implementará "
            "junto con el empaquetado PyInstaller (fuera de alcance de este "
            "microbloque)."
        )

    script = helper_script if helper_script is not None else _default_helper_script()
    if not Path(script).is_file():
        raise FolderDialogUnavailableError(
            f"No se encontró el script auxiliar del selector de carpetas: {script}"
        )

    cmd = [sys.executable, str(script)]
    if title:
        cmd.append(f"--title={title}")
    if initial_dir:
        cmd.append(initial_dir)

    # CREATE_NO_WINDOW evita un parpadeo de consola si en el futuro
    # ``sys.executable`` fuera un ejecutable "windowed" (pythonw/exe
    # empaquetado); inofensivo hoy, cuando el padre ya corre en consola.
    extra_kwargs = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = run_subprocess(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            **extra_kwargs,
        )
    except subprocess.TimeoutExpired as exc:
        raise FolderDialogUnavailableError(
            "El selector de carpetas no respondió dentro del plazo esperado. "
            "Ciérrelo (si sigue abierto) e intente nuevamente."
        ) from exc
    except OSError as exc:
        raise FolderDialogUnavailableError(
            f"No se pudo iniciar el selector de carpetas: {exc}"
        ) from exc

    if result.returncode == _EXIT_CANCELLED:
        return None

    if result.returncode == _EXIT_NO_GUI:
        detalle = (result.stderr or "").strip()
        raise FolderDialogUnavailableError(
            "El selector nativo de carpetas no está disponible en este entorno "
            f"(sin interfaz gráfica). {detalle}".strip()
        )

    if result.returncode != _EXIT_OK:
        detalle = (result.stderr or "").strip() or f"código de salida {result.returncode}"
        raise FolderDialogUnavailableError(
            f"El selector de carpetas terminó con un error inesperado: {detalle}"
        )

    seleccionada = (result.stdout or "").strip()
    return seleccionada or None
