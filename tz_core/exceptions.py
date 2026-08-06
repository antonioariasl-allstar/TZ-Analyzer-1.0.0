"""Excepciones de dominio para la ruta de ingesta reutilizable.

Reemplazan los ``sys.exit()``/``SystemExit`` que antes vivían dentro de
``tz_core.ingestion_pipeline`` para que orquestadores no interactivos
(servicios, tests, futuras integraciones) puedan capturar la condición de
error sin terminar el proceso completo. El CLI histórico (``main()`` en
``script_principal_bitacoras_refactory.py``) captura estas excepciones y
traduce el comportamiento a la salida limpia que ya existía.
"""


class ArchivoNoProcesableError(Exception):
    """El archivo de entrada no tiene datos analíticamente procesables.

    Se lanza en vez de terminar el proceso para que rutas reutilizables
    puedan decidir cómo responder, en lugar de heredar la salida abrupta
    del CLI original.
    """
