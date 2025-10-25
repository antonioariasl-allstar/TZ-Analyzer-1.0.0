Golden files para pruebas E2E

Este directorio almacena representaciones normalizadas de los outputs
(KML dentro del KMZ y HTML del informe) para detectar regresiones.

Cómo inicializar/actualizar:

1. Asegura dependencias instaladas y que el script principal corre.
2. Ejecuta:

   powershell
   ---
   python -m tests.update_golden

Esto generará:
- kml_normalized.txt
- html_normalized.txt

No edites estos archivos a mano; se regeneran cuando cambie el comportamiento esperado.
