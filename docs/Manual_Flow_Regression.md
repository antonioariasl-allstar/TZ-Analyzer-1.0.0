# Manual Flow Regression (Opción 1)

Esta guía documenta cómo repetir de forma determinista la regresión de la Opción 1 (flujo manual) sin interacción humana.

## Enfoque recomendado: prueba de integración
- Ejecuta la prueba de integración que ya monta un `WizardIO` falso y un dataset sintético:

```bash
pytest tests/integration/test_manual_flow_option1.py -q
```

- La prueba crea un Excel temporal con dos filas válidas, ejecuta `run_tz_analysis` y valida que se generen los artefactos clave (HTML, KMZ y log) en un directorio temporal.
- No requiere variables de entorno ni datasets externos; todo vive dentro de la prueba.

## Qué valida
- El flujo manual completo puede correrse con `WizardIO` inyectado (sin prompts reales).
- Se generan `*_informe.html`, `*.kmz` y `ejecucion_log.txt`.
- El `WizardIO` dummy responde vacío a todos los prompts, lo que ejerce el camino por defecto y asegura estabilidad del pipeline manual.

## Reproducción CLI (opcional)
Si quieres correr el flujo manual fuera de pytest:

```bash
python run.py
```

1. Elige la opción 1 en el menú.
2. Selecciona un Excel con las columnas mínimas (`fecha`, `hora`, `lat`, `long`, `antena`, `direccion`, `tel`, `imei`, `contacto`, `interaccion`, `duracion`).
3. Acepta los defaults de Top N y carpeta de salida. Se generarán `*_informe.html`, `*.kml`/`*.kmz` y `ejecucion_log.txt` en la carpeta elegida.

## Notas sobre el harness previo
- El harness temporal que dependía de `TZ_MANUAL_FLOW_AUTOMATION` ya no es necesario; fue reemplazado por la prueba de integración descrita arriba.
- Los artefactos históricos (`mi_resultado/option1_auto_*`) quedan solo como referencia manual; la regresión oficial debe correrse vía pytest.
