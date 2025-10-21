# TODO – TZ Analysis
Rama: copilot/pase-3  
Pase: 3 (migración a Python 3.12.8)  
Fecha: 2025-10-21  

> **📋 Handoff para casa:** Ver archivo `HANDOFF_CASA.txt` en la raíz del repo con instrucciones paso a paso para continuar el trabajo en casa.

## ✅ Migración a Python 3.12.8 (completada)
**Fecha:** 21 de octubre de 2025  
**Estado:** ✅ Completada exitosamente

### Cambios realizados:
- ✅ Entorno virtual `.venv312` creado con Python 3.12.8
- ✅ Todas las dependencias instaladas (incluido `simplekml` que faltaba)
- ✅ Test de regresión `test_kml_regresion.py` ejecutado exitosamente
- ✅ README.md actualizado con la versión de Python requerida
- ✅ `requirements.txt` actualizado con `simplekml==1.3.6`
- ✅ `.gitignore` protegiendo correctamente el entorno virtual

### Notas:
- Pylance muestra advertencias de tipo (type hints) más estrictas en Python 3.12.8, pero **el código funciona correctamente**
- Las advertencias son de análisis estático y no afectan la ejecución
- El motor y la lógica del programa **no fueron modificados**

---

## Pase 1 (diagnóstico sin cambiar lógica)  
Fecha: 2025-10-16  
Criterio: Solo observaciones del código visible. Nada de features nuevas.

## validaciones.py
Funciones reales (según archivo):
- validar_datos(df, columnas_esenciales) -> (pd.DataFrame, List[str])
- guardar_errores(errores, carpeta_salida, nombre_base) -> Optional[str]
- _to_object(df, cols)
- _is_excel_serial(x)
- _excel_serial_to_timestamp(x)
- _safe_to_datetime(series, dayfirst=True, errors="coerce")
- _normalize_fecha_col(df, col)
- _normalize_hora_col(df, col)
- _to_float_safe(series)
- _coerce_azimut(series)
- _ensure_lon_name(df)
- _ensure_lat_name(df)

Pendientes observables (higiene, sin tocar lógica):
- [ ] Agregar docstrings breves a `validar_datos` y `guardar_errores` (qué hace, params, retorno).
- [ ] Verificar que los mensajes se gestionen por `logging` desde `run.py` (aquí no configurar logging).
- [ ] Confirmar consistencia de `"_SIN_INF"` en todas las salidas de formateo (solo revisión).
- [ ] (Opcional) Añadir type hints solo en funciones **públicas** si son obvios (sin cambiar cuerpos).

Notas:
- No filtra filas ni aborta: la etapa HTML/KML decide; mantener ese contrato.

## run.py
Funciones / responsabilidades (según archivo):
- Punto de entrada del programa (menú / opciones).
- Orquestación: lectura de bitácora, validaciones, generación de salidas (HTML/KML/KMZ), rutas de salida.

Pendientes observables (higiene, sin cambiar lógica):
- [ ] Centralizar configuración de `logging` aquí (nivel y formato simples). No configurar en módulos.
- [ ] Docstring breve al inicio del archivo explicando flujo general (1–2 líneas).
- [ ] Mensajes de usuario: revisar que sean claros y consistentes (evitar prints ruidosos).
- [ ] Manejo de errores: envolver la ejecución principal en try/except con mensaje legible + `logging.error(...)`.
- [ ] Comprobación de carpetas de salida: asegurar `os.makedirs(..., exist_ok=True)` antes de escribir.

Notas:
- Mantener contratos actuales con módulos (`validaciones`, `kml_generador`, etc.).
- No cambiar nombres de opciones del menú en este pase.

## kml_generador.py
Funciones / responsabilidades (según archivo):
- Construcción de KML/KMZ a partir del DataFrame validado.
- Formateo de coordenadas y burbujas (placemarks), agrupaciones por criterio (fecha/rango, top antenas).

Pendientes observables (higiene, sin cambiar lógica):
- [ ] Docstrings breves en funciones públicas clave (qué hace, params, return).
- [ ] Revisar consistencia de formato en lat/lon (6 decimales, sin ‘.0’ en enteros cuando aplique).
- [ ] Confirmar que solo se muestren campos con dato (omitir “Sin Inf.” en la burbuja si así está definido).
- [ ] Validar que el nombre de archivos/carpetas no introduzca caracteres problemáticos (solo verificación).
- [ ] (Opcional) Extraer pequeñas utilidades repetidas (helpers) si existen bloques duplicados.

Notas:
- Respetar estructura de carpetas actual y nombres base (no modificar en este pase).
- Mantener compatibilidad con configuración desde `config.json`.

## Transversal
- [ ] Configurar `logging` en `run.py` (no en módulos) con formato simple visible en consola.
- [ ] Mantener `"_SIN_INF"` coherente en todas las salidas (HTML/KML/KMZ).
- [ ] Tests mínimos (pytest) para normalización de fecha/hora y formateo de lat/lon.
- [ ] Confirmar zonas horarias y `dayfirst=True` donde aplique.
- [ ] Documentar en `README.md` requisitos básicos y flujo general (breve).