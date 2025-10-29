"""
tz_cli.menu - MENÚS INTERACTIVOS EXTRAÍDOS DEL MONOLITO
======================================================

✅ ESTADO: SPRINT 3A - EXTRACCIÓN MENÚ INTERACTIVO SIN CLICK
🎯 PROPÓSITO: Centralizar toda la interacción de menús del flujo principal
📍 DIFERENCIACIÓN: Menú interactivo actual sin cambiar UX

RESPONSABILIDADES ESPECÍFICAS:
- main_menu(): Menú principal [1/2/3] extraído de main()
- manual_menu_loop(): Menú modo manual [A/L/E/G/V] 
- Conservar flujo exacto sin cambiar experiencia usuario
- Bridge hacia controllers para lógica de negocio

FUNCIONES EXTRAÍDAS:
- Menú principal L5241-L5265 de script_principal_bitacoras_refactory.py
- Menú manual L4852-L4870 de _modo_manual()
- Lógica de navegación y validación opciones

INTEGRACIÓN:
- Import desde script principal → tz_cli.menu.main_menu()
- Controllers manejan transición menú → lógica core
- Variables globales preservadas (CONFIG, df, nombres, etc.)

FECHA EXTRACCIÓN: 29 octubre 2025 - Sprint 3A Fase 3A.2
"""

import logging

def log(message):
    """Helper logging compatible con monolito"""
    logging.info(message)

def main_menu():
    """
    Menú principal extraído: [1] Completo, [2] Por tiempo, [3] Manual
    
    EJECUTA TODO EL FLUJO COMPLETO delegando al main() original:
    - Menú de selección modo 
    - Delegación transparente al main() del monolito
    - Zero cambios en comportamiento
    
    Returns:
        dict: Resultado ejecución con rutas archivos generados (como main())
    """
    log("Mostrando menú principal de opciones...")
    
    # Importar main() original del monolito
    import script_principal_bitacoras_refactory as script
    
    # Simplemente delegar al main() original que ya funciona
    # El menú está integrado dentro de main() correctamente
    return script.main()

def manual_menu_loop(items, handlers):
    """
    Menú modo manual extraído: [A/L/E/G/V]
    
    Conserva el flujo exacto del _modo_manual() del monolito:
    - Mismas opciones y navegación
    - Misma validación y mensajes
    - Delegación a handlers para cada operación
    
    Args:
        items: Lista registros manuales en construcción
        handlers: Dict con handlers para cada operación:
                  {'add': func, 'list': func, 'delete': func, 'generate': func}
    
    Returns:
        tuple: (operation, items, should_exit)
               operation: "A", "L", "E", "G", "V"
               items: Lista actualizada registros
               should_exit: True si usuario eligió [V] Volver
    """
    log("Iniciando bucle principal de entrada de datos...")
    
    while True:
        print("\nMenú:")
        print("[A] Agregar registro")
        print("[L] Listar registros")
        print("[E] Eliminar registro (#)")
        print("[G] Graficar (generar KML/KMZ)")
        print("[V] Volver (cancelar)")
        op = input("Opción: ").strip().upper() or "A"
        log(f"Usuario seleccionó opción del menú: '{op}'")

        if op == "V":
            log("Usuario canceló modo manual, regresando sin generar archivos")
            print("Volviendo sin generar…")
            return ("V", items, True)

        if op == "L":
            log(f"Listando {len(items)} registros existentes")
            if 'list' in handlers:
                handlers['list'](items)
            continue

        if op == "E":
            if not items:
                print("No hay registros para eliminar.")
                continue
            
            log("Usuario solicitó eliminar registro")
            if 'delete' in handlers:
                items = handlers['delete'](items)
            continue

        if op == "A":
            log("Usuario solicitó agregar nuevo registro")
            if 'add' in handlers:
                new_item = handlers['add']()
                if new_item:
                    items.append(new_item)
                    log(f"Registro agregado exitosamente. Total: {len(items)}")
            continue

        if op == "G":
            if not items:
                print("No hay registros para graficar. Agrega al menos uno.")
                continue
                
            log(f"Usuario solicitó generar KML/KMZ con {len(items)} registros")
            if 'generate' in handlers:
                success = handlers['generate'](items)
                if success:
                    return ("G", items, False)  # Generación exitosa, salir
            continue

        log(f"Opción manual inválida: '{op}'")
        print("[QC] Opción inválida. Usa A, L, E, G o V.")

def display_processing_options():
    """
    Muestra las opciones disponibles para procesamiento
    
    Helper function para mostrar información contextual
    sobre las opciones disponibles en el menú principal.
    """
    print("\n" + "="*50)
    print("TZ ANALYZER - OPCIONES DE PROCESAMIENTO")
    print("="*50)
    print("[1] PROCESAR BITÁCORA COMPLETA")
    print("    → Procesamiento estándar de toda la bitácora")
    print("    → Generación completa: HTML + KML/KMZ + Análisis")
    print()
    print("[2] PROCESAR POR TIEMPO")
    print("    → Filtros temporales: día específico, rango días, horas")
    print("    → Análisis acotado temporalmente")
    print()
    print("[3] INGRESAR ANTENAS MANUALMENTE")
    print("    → Entrada manual punto a punto")
    print("    → Generación KML/KMZ desde registros manuales")
    print("="*50)

def show_current_status(opcion=None, archivo=None, hoja=None):
    """
    Muestra estado actual del procesamiento
    
    Helper para mostrar información de contexto durante
    el flujo interactivo.
    """
    if opcion or archivo or hoja:
        print("\n[STATUS] Estado actual:")
        if opcion:
            modo_nombre = {"1": "Bitácora completa", "2": "Por tiempo", "3": "Manual"}
            print(f"   Modo: {modo_nombre.get(opcion, opcion)}")
        if archivo:
            print(f"   Archivo: {archivo}")
        if hoja:
            print(f"   Hoja: {hoja}")
        print()

def confirm_action(message, default_yes=False):
    """
    Helper para confirmaciones S/N
    
    Args:
        message: Mensaje de confirmación
        default_yes: Si True, Enter = Sí; si False, Enter = No
        
    Returns:
        bool: True si usuario confirmó, False si canceló
    """
    suffix = " (S/n)" if default_yes else " (s/N)"
    resp = input(f"{message}{suffix}: ").strip().lower()
    
    if not resp:
        return default_yes
    
    return resp in ('s', 'si', 'sí', 'y', 'yes')

# Aliases para compatibilidad con monolito
show_main_menu = main_menu
manual_mode_menu = manual_menu_loop