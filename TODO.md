# TODO – TZ Analysis
Rama: copilot/pase-1  
Pase: 1 (diagnóstico sin cambiar lógica)  
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
