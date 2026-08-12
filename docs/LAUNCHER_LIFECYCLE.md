# Launcher, instancia única y ciclo de vida (v1)

MICROBLOQUE 5 de la auditoría de preempaquetado. Cierra AUD-01
(lifecycle/shutdown), AUD-02 (instancia única/puerto) y AUD-03 (servidor de
producción / launcher) para la aplicación web local de TZ Analyzer.

Decisión de producto para v1: navegador externo, no `pywebview`. El
launcher es dueño del proceso; el navegador es solo un cliente que el
usuario puede cerrar sin que eso determine el ciclo de vida del backend.

## Piezas y responsabilidades

| Módulo | Responsabilidad | Lo que explícitamente NO hace |
|---|---|---|
| `tz_launcher.py` (raíz) | Orquesta: decide arrancar/reutilizar, levanta el servidor, abre el navegador, espera el cierre, limpia. | No conoce rutas Flask ni Waitress a bajo nivel. |
| `tz_web/instance.py` | Lock de instancia a nivel de SO, metadata (`instance.json`), health-check HTTP, `resolve_startup_plan()`. | No abre navegador, no levanta servidor. |
| `tz_web/lifecycle.py` | Estado `RUNNING` / `CLOSE_WHEN_IDLE` / `SHUTTING_DOWN`, heartbeat + watchdog, hook de apagado. | No sabe qué es Waitress ni Flask — solo *cuándo*, nunca *cómo*. |
| `tz_web/server.py` | Envoltorio de Waitress: `start()`, `wait_until_ready()`, `stop()`. | No decide instancia única ni cuándo cerrar. |
| `tz_web/internal_routes.py` | `/internal/health`, `/internal/heartbeat`, `/internal/shutdown`, todas con guardia de token + loopback. | No expone datos de caso. |
| `tz_web/app.py` | Fábrica `create_app()` de la aplicación Flask. | Ya no arranca ningún servidor (ver su docstring). |

## Instancia única — por qué un lock de SO y no un PID en un archivo

`tz_web.instance.InstanceLock` usa `msvcrt.locking()` sobre un archivo fijo
(`instance.lock`) en `%LOCALAPPDATA%\TZ Analyzer\run\`. La propiedad clave:
el bloqueo está atado al *handle* abierto por el proceso, no a un valor
escrito en disco. Si el proceso muere — limpio o por crash — Windows libera
el handle (y por lo tanto el lock) automáticamente al terminar el proceso.

Esto significa que "instancia stale" y "PID reciclado" dejan de ser casos
especiales que haya que detectar a mano: el siguiente lanzamiento
simplemente **puede volver a adquirir el lock**, sin inspeccionar PID, sin
mirar la edad del archivo, sin escanear puertos.

### Decisión de arranque (`resolve_startup_plan`)

```
¿try_acquire() consigue el lock?
├── Sí → "start": esta es la nueva instancia (nadie más lo tenía, o el
│        dueño anterior murió y el SO ya liberó el handle).
└── No → alguien más lo tiene ahora mismo. Se lee instance.json y se
         valida con GET /internal/health autenticado (con reintentos
         breves, por si la otra instancia recién está terminando de
         levantar su propio servidor):
         ├── responde 200 y su instance_id coincide → "reuse": se abre
         │    el navegador contra esa instancia; NO se levanta un
         │    segundo backend.
         └── no responde, responde con otro instance_id, o la
              metadata no puede leerse → "blocked": nunca se fuerza el
              lock, nunca se escanean otros puertos, nunca se asume que
              el PID de la metadata sigue vivo. Se informa el error al
              usuario y no se arranca nada.
```

`resolve_startup_plan()` es una función pura respecto de I/O real (lock,
`health_checker` y `sleep` inyectables), así que cada rama tiene prueba
unitaria directa sin procesos ni red reales (`tests/web/test_instance.py`).

### Metadata (`instance.json`)

```json
{
  "schema_version": 1,
  "instance_id": "…",
  "pid": 12345,
  "port": 54321,
  "token": "…",
  "created_at": 1735000000.0,
  "app_version": "1.1",
  "launcher_version": "1.0"
}
```

Nunca dentro del repositorio ni de Program Files: vive en
`%LOCALAPPDATA%\TZ Analyzer\run\`, la misma carpeta de usuario que
`tz_core.user_paths` ya usa para configuración editable (subcarpeta propia
para no mezclar archivos de vida corta con config persistente). Esto no
resuelve AUD-14 por completo, pero ya cumple su restricción central.

### Puerto

Puerto efímero asignado por el sistema operativo (`port=0` al crear el
servidor Waitress; `effective_port` después de enlazar). No hay rango fijo
ni reintento "5175, 5176, 5177…" — ese patrón queda explícitamente
descartado como mecanismo normal de segunda instancia.

## Ciclo de vida (`tz_web/lifecycle.py`)

Tres estados:

```
RUNNING ──(cierre pedido, sin análisis activo)──────────────► SHUTTING_DOWN
   │                                                                ▲
   │ (cierre pedido CON análisis activo)                            │
   ▼                                                                │
CLOSE_WHEN_IDLE ──(ese análisis termina)───────────────────────────┘
```

Invariante central: **un cierre nunca mata un análisis activo.** Por eso
toda decisión que depende de "¿hay un análisis activo?" se toma bajo
`tz_web.state.run_lock()` — el mismo lock que ya serializa
`try_start_run()`/`terminal_run()` — en vez de que `lifecycle` mantenga su
propia señal, potencialmente desincronizada, del mismo hecho.

**Bloqueo de análisis nuevos con cierre pendiente.** Fuera de `RUNNING`,
ningún análisis nuevo puede arrancar — solo el que ya estaba activo (si lo
había) sigue hasta terminar. `tz_web.state.set_run_start_guard()` registra
un veto (`tz_web.lifecycle._run_start_guard`) que `try_start_run_detailed()`
evalúa dentro de la misma adquisición de `state._RUNNING_LOCK` que reserva
la ejecución — el mismo lock que `request_shutdown()`/el watchdog ya
adquieren antes de escribir el estado. No hay ventana entre "¿puedo
iniciar?" y "reservar": ambas decisiones están serializadas por el mismo
lock, nunca por dos señales independientes que puedan desincronizarse. El
motivo del rechazo (`RUN_START_REJECTED_BUSY` vs. `RUN_START_REJECTED_
SHUTDOWN`) viaja hasta la capa web (`tz_web/routes.py`,
`_flash_start_rejected`) para mostrar el mensaje correcto: "hay un análisis
en curso" no es lo mismo que "hay un cierre pendiente", y confundirlos
induce al usuario a esperar por la razón equivocada.

- **Cierre explícito** (botón "Cerrar TZ Analyzer" → `POST
  /internal/shutdown` → `lifecycle.request_shutdown()`): idle, cierra de
  inmediato; con análisis activo, pasa a `CLOSE_WHEN_IDLE` y no toca el
  worker.
- **Heartbeat**: la interfaz llama `POST /internal/heartbeat` cada 60 s
  mientras la pestaña sigue abierta (`tz_web/static/js/app.js`,
  `tzStartHeartbeat`). Un hilo *watchdog* (`start_watchdog`, cada 30 s por
  defecto) revisa si pasaron más de `DEFAULT_HEARTBEAT_TIMEOUT_SECONDS`
  (15 minutos) desde el último heartbeat:
  - sin análisis activo → cierre inmediato;
  - con análisis activo → `CLOSE_WHEN_IDLE`, nunca mata el worker.
- **El análisis termina** (`tz_web.state.terminal_run`/`finish_run`, ya sea
  éxito, fallo o cancelación de arranque): se invoca
  `lifecycle.on_run_finished()` vía un hook registrado una sola vez en
  `tz_web.state._ON_RUN_RELEASED` — si había un cierre diferido y ya no
  queda ningún análisis activo, se completa el cierre ahí mismo.

El "hook de apagado" (`lifecycle.set_shutdown_hook(...)`) es lo único que
conecta este estado con un servidor real; `tz_launcher.py` lo conecta a
`ManagedServer.stop`. Sin hook (pruebas), una transición a `SHUTTING_DOWN`
solo cambia el estado.

### Constantes centralizadas (nada de magic numbers dispersos)

| Constante | Valor por defecto | Dónde |
|---|---|---|
| `DEFAULT_HEARTBEAT_TIMEOUT_SECONDS` | 900 (15 min) | `tz_web/lifecycle.py` |
| `DEFAULT_WATCHDOG_INTERVAL_SECONDS` | 30 | `tz_web/lifecycle.py` |
| `TZ_HEARTBEAT_INTERVAL_MS` (JS) | 60000 (60 s) | `tz_web/static/js/app.js` |

## Servidor WSGI (`tz_web/server.py`)

Waitress (`waitress==3.0.2`), no el servidor de desarrollo de Werkzeug:
- `host="127.0.0.1"` siempre — nunca `0.0.0.0` ni una IP de red;
- sin `debug`, sin `use_reloader` (Waitress no tiene ninguno de los dos);
- `ManagedServer.start()` crea y enlaza el socket sincrónicamente y arranca
  el bucle de aceptación en un hilo daemon;
- `ManagedServer.wait_until_ready(token)` confirma, con el mismo health
  autenticado que valida una segunda instancia, que el servidor ya
  despacha pedidos reales — no solo que el socket está enlazado. Solo
  después de esto abre el navegador `tz_launcher.py`;
- `ManagedServer.stop()` es idempotente y segura de llamar desde cualquier
  hilo (incluido el propio hilo que atiende el pedido `/internal/shutdown`
  que la disparó). **No cierra el socket directamente**: en Windows, cerrar
  un socket que el hilo de `server.run()` tiene en ese instante dentro de
  un `select()` es una carrera de Winsock. En vez de eso usa
  `server.trigger.pull_trigger(thunk)` — el mecanismo que el propio
  Waitress expone para encolar un cierre que se ejecute *dentro* del hilo
  del bucle de aceptación, despertando su `select()` de forma segura.

### Diagnóstico del `WinError 10038` (este microbloque)

Una versión anterior de `stop()` solo hacía `pull_trigger(server.close)`
tras un retraso fijo de 0.3 s, con la carrera todavía reproducible en
pruebas manuales (navegador real, heartbeat/recursos estáticos
concurrentes) con relativa frecuencia. Diagnóstico dirigido, leyendo el
código real de Waitress 3.0.2 instalado (`waitress/channel.py`,
`waitress/trigger.py`, `waitress/task.py`, `waitress/server.py`), no
asumido — dos causas distintas, ambas dentro de Waitress y evitables desde
nuestro lado sin parchear la librería:

1. **La carrera del `WinError 10038` en sí.** Cada hilo worker del pool de
   tareas (`ThreadedTaskDispatcher`) llama `server.pull_trigger()` sin
   ninguna sincronización propia de Waitress: al terminar de despachar una
   petición (`HTTPChannel.service()`, línea final) y al escribir una
   respuesta que supera el umbral de buffer (`HTTPChannel.write_soon`/
   `_flush_outbufs_below_high_watermark`). `trigger.pull_trigger()` hace
   `self.trigger.send(...)` sobre el socket interno del trigger sin lock;
   nuestro cierre cierra ese mismo socket. Si un hilo worker todavía vivo
   —sirviendo un heartbeat o un recurso estático concurrente, exactamente
   el escenario que el reporte anterior ya señalaba como el disparador más
   frecuente— alcanza su propio `pull_trigger()` mientras el trigger ya se
   cerró (o se está cerrando), `send()` sobre un socket cerrado produce
   `OSError: [WinError 10038]` en Windows. Es una carrera real dentro de
   Waitress (`trigger.py` no protege `close()` contra `pull_trigger()`
   concurrente de otro hilo) — **categoría D con matiz**: comportamiento
   interno de Waitress, pero evitable desde nuestro lado sin tocar su
   código: basta con no dejar ningún hilo worker vivo antes de cerrar el
   trigger. `ThreadedTaskDispatcher.shutdown()` es el método público que la
   propia Waitress usa para eso — lo llama `MultiSocketServer.close()`
   internamente — pero `BaseWSGIServer.close()` (la ruta de un único
   socket, nuestro caso) no lo invoca. `ManagedServer._drain_and_close()`
   completa esa secuencia: llama `task_dispatcher.shutdown()` **en un hilo
   propio** (nunca en un hilo worker de Waitress: si corriera en el que
   atendió `/internal/shutdown`, `shutdown()` esperaría a que ese mismo
   hilo termine su tarea actual — la que lo está llamando — y se
   autobloquearía hasta agotar el timeout en cada cierre) antes de pedir el
   cierre real. Solo entonces se programa `pull_trigger(thunk)`.
2. **Canales huérfanos tras `task_dispatcher.shutdown()`.** Efecto
   secundario del propio `shutdown()` (no un bug nuestro), encontrado con
   diagnóstico dirigido: con `cancel_pending=True` (su valor por defecto)
   cancela las tareas que ya estaban en cola pero nunca llegaron a
   arrancar — p. ej. un heartbeat/estático que un hilo worker recién había
   aceptado. Cancelar la *tarea* no cierra el *canal* que la esperaba: ese
   canal queda conectado, con una petición pendiente que nadie va a
   servir, para siempre — y `wasyncore.loop()` (el bucle del hilo de
   aceptación, condicionado a `while map: ...`) nunca termina mientras el
   mapa de sockets no quede vacío, por más que el socket de escucha y el
   trigger ya se hayan cerrado. `ManagedServer._close_all_sockets()`
   resuelve esto llamando `waitress.wasyncore.close_all(self._map)` —
   exactamente lo que hace `MultiSocketServer.close()` internamente
   (`task_dispatcher.shutdown(); wasyncore.close_all(self.map)`), aplicado
   a un `map` propio que `ManagedServer` pasa a `create_server(map=...)`
   (parámetro público, no un detalle interno) en vez de depender del
   atributo `_server._map`.

Confirmado con un stress test dedicado (`tests/web/test_shutdown_stress.py`,
12 repeticiones × 6 hilos martillando heartbeat/estático concurrentes,
cierre disparado por el mismo camino HTTP real que usa producción, varias
corridas seguidas): tras el fix, ningún cierre deja una excepción no
controlada en ningún hilo, ningún registro de error del logger `"waitress"`
(donde antes aparecía el `WinError 10038`), y el servidor siempre confirma
su cierre.

**Papel del timeout de 8 s del launcher tras la corrección.** Antes del
fix, ese plazo (`_WAITRESS_JOIN_TIMEOUT_SECONDS` en `tz_launcher.py`) era,
en la práctica, el mecanismo principal que garantizaba que el proceso
terminara pese a la carrera. Después del fix, el cierre se completa de
forma determinista y rápida en el caso normal (el propio
`_TASK_DRAIN_TIMEOUT_SECONDS` de 5 s en `tz_web/server.py` es, a su vez,
solo el peor caso de `task_dispatcher.shutdown()` esperando a un hilo
worker genuinamente lento — no el camino habitual). El timeout de 8 s pasa
a ser lo que la sección M del encargo pedía desde el principio: una **red
de seguridad final**, no el mecanismo que oculta una carrera — cubre casos
verdaderamente patológicos (p. ej. una petición WSGI que nunca retorna) que
ningún cambio de secuencia de cierre puede prevenir del todo, y sigue
delegando la única invariante real ("nunca matar un análisis activo") a la
espera separada sobre `state.is_any_run_active()`, que no depende en
absoluto de este hilo.

### Bug encontrado en el smoke manual: autocierre a los ~8 s sin pedirlo nadie

Antes de esta corrección, `_run_new_instance` (`tz_launcher.py`) llamaba
`managed.wait_for_shutdown(timeout=_WAITRESS_JOIN_TIMEOUT_SECONDS)` **de
forma incondicional**, justo después de abrir el navegador — tratando ese
plazo acotado como si fuera cuánto tiempo debía vivir el proceso, en vez de
una red de seguridad para *después* de que alguien pidiera cerrar. Efecto
real: el launcher se autoterminaba, liberando el lock de instancia, a los
~8 s de arrancar, sin que nadie hubiera pedido cerrar nada — con el
navegador del usuario ya abierto y apuntando a un backend recién muerto.
Ningún test existente lo detectaba porque el único test de ciclo completo
(`test_run_new_instance_ciclo_completo`) siempre dispara `/internal/
shutdown` explícito antes de comprobar que el hilo termina.

Corregido: el proceso ahora espera indefinidamente (sondeando cada
`_SHUTDOWN_WAIT_SAFETY_POLL_SECONDS`) mientras `lifecycle.get_state() !=
SHUTTING_DOWN` — cubre tanto RUNNING normal como CLOSE_WHEN_IDLE con un
análisis todavía activo, sin arriesgar la invariante de la sección M. El
plazo acotado (`_WAITRESS_JOIN_TIMEOUT_SECONDS`) solo se aplica **una vez**
que lifecycle ya confirmó SHUTTING_DOWN (lo que garantiza que el hook de
apagado, `managed.stop`, ya se ejecutó — `lifecycle._do_shutdown_locked` lo
llama sin soltar su lock antes de que un lector externo pueda observar el
nuevo estado). Test de regresión dedicado:
`tests/test_tz_launcher.py::test_run_new_instance_permanece_vivo_sin_cierre_pedido`.

## Seguridad local básica del canal interno

Sin abordar CSRF/Origin todavía (fuera de alcance de este microbloque):

- Las tres rutas bajo `/internal/` exigen **loopback** (`REMOTE_ADDR` en
  `127.0.0.1`/`::1`) **y** el token secreto de la instancia vía cabecera
  `X-TZ-Token` (nunca en la URL — no queda en el historial del navegador ni
  en logs de acceso por query string).
- El token se genera con `secrets.token_hex(32)`
  (`tz_launcher._generate_instance_token`): 32 bytes de `os.urandom` -> 64
  caracteres hex, 256 bits de entropía real. No `uuid.uuid4()` (usado antes,
  concatenando dos): un UUID4 fija 6 bits de versión/variante por diseño,
  así que dos concatenados dan igual 64 caracteres hex pero solo 244 bits de
  entropía real — suficiente en la práctica, pero `secrets` es el módulo que
  la propia documentación de Python señala para secretos, no para
  identificadores. `instance_id` sigue con `uuid4`: no es secreto, solo
  necesita ser distinto entre instancias.
- Sin token configurado en la app (`TZ_INSTANCE_TOKEN` ausente — el caso de
  `create_app()` en pruebas normales que no pasan por el launcher), **todo**
  pedido a `/internal/*` se rechaza: no hay modo abierto por omisión.
- El token llega a la interfaz por un único canal: un `<meta name="tz-token">`
  en `base.html`, leído por JS (`tzGetInstanceToken()`) y mandado por
  cabecera en cada `fetch`.
- El token nunca se registra completo: `InstanceMetadata.log_safe_dict()`
  lo trunca antes de cualquier log; `tz_launcher.py` solo registra
  `instance_id` truncado, nunca el token.
- `/internal/health` nunca devuelve datos de caso — solo identidad de
  instancia y estado de ciclo de vida.

## Recuperación de estados obsoletos

| Situación | Qué pasa |
|---|---|
| Proceso anterior murió limpio | `try_acquire()` de inmediato en el siguiente lanzamiento. |
| Proceso anterior crasheó | Igual: el SO liberó el handle solo. |
| Metadata presente pero el lock está libre | Se ignora — `try_acquire()` ya ganó, se sobrescribe al escribir la metadata nueva. |
| Lock ocupado pero la instancia no responde `/internal/health` | `"blocked"`: no se fuerza nada, se informa el error. |
| Puerto de la metadata ocupado por otra aplicación | El health autenticado no valida (token/`instance_id` no coinciden) → `"blocked"`, nunca se interpreta como "instancia propia". |

## Límites conocidos de v1

- No hay protección CSRF/Origin general (AUD-11 más amplio queda para otro
  microbloque); el canal `/internal/*` tiene su propia mitigación local
  (token + loopback) pero no es un reemplazo de esa auditoría.
- El heartbeat no usa `sendBeacon`/`beforeunload` como complemento — el
  encargo permite que heartbeat + timeout sea la única garantía, y así se
  implementó, para no introducir un segundo canal de autenticación
  (`sendBeacon` no permite cabeceras propias).
- No se aborda todavía Known Folders (AUD-14) más allá de que la metadata
  de instancia ya vive en una ubicación de usuario válida.

Resueltos en el cierre de pendientes de este microbloque (ya no son
límites de v1): el bloqueo de análisis nuevos con cierre pendiente (ver
"Bloqueo de análisis nuevos con cierre pendiente" arriba) y la carrera del
`WinError 10038` (ver "Diagnóstico del `WinError 10038`" arriba).
