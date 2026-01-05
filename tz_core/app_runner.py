"""Fachada mínima para ejecutar el flujo principal.

Expone `run()` para inicializar configuración y delegar en el monolito
sin alterar la lógica ni las salidas actuales.
"""


def run() -> None:
    """Ejecuta el flujo principal respetando el orden actual.

    1) Inicializa configuración global vía bootstrap_config().
    2) Ejecuta main() con el menú y generación de salidas.
    """

    # Import lazy para evitar efectos secundarios al importar la fachada en tests
    from script_principal_bitacoras_refactory import bootstrap_config, main

    bootstrap_config()
    main()
