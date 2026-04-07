"""
tz_core.manual_mode
===================
Modo manual de entrada de antenas/puntos libres.

EXTRAÍDO EN EPIC 16B (27/12/2025):
- Función _modo_manual() migrada desde monolito (498 líneas)
- Wizard CLI interactivo con validación robusta
- Generación de KML/KMZ desde datos manuales (sin DataFrame Excel)
- Helpers internos: input validators, listing, DF construction

ARQUITECTURA:
- Entrada interactiva con menú [A]gregar/[L]istar/[E]liminar/[G]raficar/[V]olver
- Dos modos: Antenas/Celdas (con azimut) vs Puntos libres (sin azimut)
- Validación de tipos: str/float/int con límites
- Generación KML usando tz_core.kml_generator

DEPENDENCIAS:
- pandas (construcción DataFrame desde lista de dicts)
- tz_core.utils (sanear_nombre_archivo, log)
- tz_core.kml_generator (generar_kml, generar_kml_puntos_libres)
- utilidades (seleccionar_carpeta)
- collections.Counter (estadísticas)

USO:
    from tz_core.manual_mode import modo_manual
    modo_manual(config=CONFIG)

AUTOR: TZ Analyzer Team
MIGRACIÓN: Epic 16B - Modularización Fase 2
"""

import os
import pandas as pd
from collections import Counter

from tz_core.logging_utils import log
from tz_core.utils import sanear_nombre_archivo


def modo_manual(config: dict):
    """
    Entrada manual de puntos/antenas con validación básica.
    Genera un KML/KMZ usando los mismos estilos reusables.
    
    Args:
        config: Diccionario de configuración del sistema (CONFIG)
        
    Returns:
        None - Ejecuta flujo interactivo y genera archivos KML/KMZ
    """
    # Imports dinámicos (para evitar ciclos y mantener compatibilidad)
    from tz_core.kml_generator import generar_kml_puntos_libres
    from utilidades import seleccionar_carpeta
    
    # Import de color_utils para _solicitar_color_tema
    try:
        from tz_core.color_utils import solicitar_color_tema
    except ImportError:
        # Fallback si no existe el módulo (mantener compatibilidad)
        def solicitar_color_tema(cfg):
            return cfg
    
    from tz_core.kml_generator import generar_kml as _generar_kml_core

    log("=== INICIANDO MODO MANUAL ===")
    log("Configurando funciones auxiliares para entrada de datos...")

    # ==================== HELPERS LOCALES ====================
    def _input_str(msg, obligatorio=False, maxlen=None):
        while True:
            s = input(msg).strip()
            if s == "" and not obligatorio:
                return None
            if s == "" and obligatorio:
                print("Este campo es obligatorio.")
                continue
            if maxlen and len(s) > maxlen:
                print(f"Máximo {maxlen} caracteres.")
                continue
            return s

    def _input_float(msg, obligatorio=False):
        while True:
            s = input(msg).strip()
            if s == "" and not obligatorio:
                return None
            try:
                return float(s.replace(",", "."))
            except Exception:
                print("Valor numérico inválido. Ej: 13.71234")

    def _input_int(msg, obligatorio=False, minv=None, maxv=None):
        while True:
            s = input(msg).strip()
            if s == "" and not obligatorio:
                return None
            try:
                val = int(s)
                if minv is not None and val < minv:
                    print(f"Debe ser ≥ {minv}."); continue
                if maxv is not None and val > maxv:
                    print(f"Debe ser ≤ {maxv}."); continue
                return val
            except Exception:
                print("Ingrese un entero válido.")

    def _listar(items):
        if not items:
            print("No hay registros cargados.")
            return
        print("\n# | Antena (corta) | Lat, Long | Azimut")
        for i, it in enumerate(items, 1):
            a = it.get("antena") or "(sin nombre)"
            a = (a[:38] + "…") if len(a) > 40 else a
            lat = it.get("lat")
            lon = it.get("long")
            az  = it.get("azimut")
            print(f"{i:>2} | {a:<40} | {lat},{lon} | {az if az is not None else '-'}")
        print()

    def _armar_df(items):
        # Convertimos a DF con los nombres que ya espera tu pipeline
        df = pd.DataFrame(items)
        # Tipos
        for c in ("lat", "long"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "azimut" in df.columns:
            df["azimut"] = pd.to_numeric(df["azimut"], errors="coerce")
        # Fecha/Hora si faltan
        if "fecha" not in df.columns: df["fecha"] = None
        if "hora"  not in df.columns: df["hora"]  = None
        return df
        
    def _sanear_nombre_archivo_local(s):
        """
        Wrapper para compatibilidad - usar sanear_nombre_archivo de tz_core.utils
        
        CRÍTICO: Preserva fallback original "antenas_manual" para mantener
        comportamiento idéntico en casos límite (None, "", "...", "___")
        
        Función original extraída con cero breaking changes garantizado.
        """
        return sanear_nombre_archivo(s, "antenas_manual")

    def _nombre_auto_desde_items(items):
        # toma el primer tel y el primer alias no vacios
        tel = next((it.get("tel") for it in items if it.get("tel")), None)
        alias = next((it.get("alias") for it in items if it.get("alias")), None)
        partes = []
        if tel:   partes.append(str(tel))
        if alias: partes.append(str(alias))
        base = "_".join(partes) if partes else "antenas_manual"
        return _sanear_nombre_archivo_local(base)

    # ==================== FLUJO INTERACTIVO ====================
    items = []
    log("Iniciando flujo interactivo de entrada manual")
    print("\nModo MANUAL. Ingresará uno o más puntos/antenas.")
    
    # Preguntar tipo de registro UNA SOLA VEZ al inicio
    log("Solicitando tipo de registro al usuario...")
    print("\n¿Qué tipo de registros desea agregar?")
    print("[1] Antenas/Celdas")
    print("[2] Puntos libres (lugares, domicilios, escenas, etc.)")
    tipo_modo = (input("Tipo (1/2, Enter=1): ").strip() or "1")
    es_punto_libre = (tipo_modo == "2")
    log(f"Usuario seleccionó tipo: {'Puntos libres' if es_punto_libre else 'Antenas/Celdas'}")
    
    if es_punto_libre:
        print("\n→ Modo: Puntos libres (sin azimut, campos simplificados)")
    else:
        print("\n→ Modo: Antenas/Celdas (con azimut y campos completos)")

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
            return

        if op == "L":
            log(f"Listando {len(items)} registros existentes")
            _listar(items)
            continue

        if op == "E":
            if not items:
                log("Intento de eliminar registro sin datos existentes")
                print("No hay registros para eliminar.")
                continue
            _listar(items)
            s = input("Número de registro a eliminar: ").strip()
            log(f"Usuario ingresó índice para eliminar: '{s}'")
            if s.isdigit():
                idx = int(s) - 1
                if 0 <= idx < len(items):
                    borr = items.pop(idx)
                    nombre_borrado = borr.get('antena','(sin nombre)')
                    log(f"Registro eliminado exitosamente: {nombre_borrado}")
                    print(f"Eliminado: {nombre_borrado}")
                else:
                    log(f"Índice fuera de rango: {idx}, total items: {len(items)}")
                    print("Índice fuera de rango.")
            else:
                log(f"Entrada inválida para eliminar: '{s}' (no es número)")
                print("Ingrese un número válido.")
            continue

        if op == "A":
            log("Iniciando entrada de nuevo registro...")
            print("\n— Nuevo registro —")

            if es_punto_libre:
                # Punto libre (sin azimut ni campos de antena)
                nombre = _input_str("Nombre/identificador del lugar: ", True, 160)
                direccion = _input_str("Dirección del lugar (opcional): ", False, 500)
                lat  = _input_float("Latitud (obligatoria): ", True)
                lon  = _input_float("Longitud (obligatoria): ", True)
                comentarios = _input_str("Comentarios (opcional): ", False, 800)

                # Mapear a las columnas soportadas por el generador KML
                # Usamos 'antena' como nombre del punto; 'direccion' se muestra en su bloque
                # y 'detalle' lo reutilizamos para comentarios.
                items.append({
                    "tipo": "punto",
                    "antena": nombre,
                    "detalle": comentarios,
                    "direccion": direccion,
                    "lat": lat,
                    "long": lon,
                    "azimut": None,  # sin orientación
                })
                print("✓ Punto agregado.")
            else:
                # Antena/Celda
                antena = _input_str("Nombre de la antena (recomendado corto): ", True, 120)
                detalle = _input_str("Detalle/dirección (opcional): ", False, 500)
                lat  = _input_float("Latitud (obligatoria): ", True)
                lon  = _input_float("Longitud (obligatoria): ", True)
                az   = _input_int("Azimut 0–359 (opcional): ", False, 0, 359)

                # Identidad (opcionales)
                tel     = _input_str("Tel (opcional): ", False, 50)
                imei    = _input_str("IMEI (opcional): ", False, 50)
                alias   = _input_str("Alias (opcional): ", False, 120)
                usuario = _input_str("Nombre del Usuario (opcional): ", False, 200)
                abonado = _input_str("Abonado (opcional): ", False, 200)

                # Técnica (opcionales)
                celda = _input_str("Celda (opcional): ", False, 50)
                lac   = _input_str("LAC (opcional): ", False, 50)

                # Interacción (opcionales)
                interaccion  = _input_str("Interacción (opcional): ", False, 80)
                tel_contacto = _input_str("Tel contacto (opcional): ", False, 50)
                duracion     = _input_int("Duración en segundos (opcional): ", False, 0)

                items.append({
                    "tipo": "antena",
                    "antena": antena, "detalle": detalle,
                    "lat": lat, "long": lon, "azimut": az,
                    "tel": tel, "imei": imei, "alias": alias,
                    "usuario": usuario, "abonado": abonado,
                    "celda": celda, "lac": lac,
                    "interaccion": interaccion,
                    "tel_contacto": tel_contacto,
                    "duracion": duracion
                })
                print("✓ Registro agregado.")
            continue

        if op == "G":
            if not items:
                print("No hay registros para graficar.")
                continue

            # Carpeta y nombre de salida
            base_auto = _nombre_auto_desde_items(items)
            nombre_sugerido = _input_str(
                f"Nombre base del archivo (Enter = {base_auto}): ", False, 120
            ) or base_auto

            # Normalizar nombre base y preparar carpeta de salida (manual)
            nombre_salida = (nombre_sugerido or base_auto)
            
            # Color tema (modo manual, antes de seleccionar carpeta)
            config = solicitar_color_tema(config)

            try:
                carpeta_base = seleccionar_carpeta()
            except Exception:
                carpeta_base = None

            if not carpeta_base:
                print("[QC] Selección de carpeta cancelada. Operación abortada.")
                return

            print(f"[QC] Carpeta destino: {carpeta_base}")

            carpeta_salida = os.path.join(carpeta_base, nombre_salida)
            os.makedirs(carpeta_salida, exist_ok=True)

            # DF y KML
            df = _armar_df(items)
            
            # RUTAS FINALES KML/KMZ (modo manual)
            if es_punto_libre:
                archivo_kml = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kml")
                archivo_kml, desc_coords = generar_kml_puntos_libres(df, archivo_kml, config)
                print(f"KML generado en: {archivo_kml}")
                kmz_path = os.path.splitext(archivo_kml)[0] + ".kmz"
                if os.path.exists(kmz_path):
                    print(f"KMZ generado en: {kmz_path}")
                print(f"Filas descartadas por coordenadas inválidas: {desc_coords}")
                # Nota: archivo_errores no está definido en scope original (posible bug)
                # print(f"Reporte de errores generado en: {archivo_errores}")
                return
                
            # Modo antenas/celdas
            if config.get("salida", {}).get("separar_kml_kmz", False):
                carpeta_kml = os.path.join(carpeta_salida, "kml")
                os.makedirs(carpeta_kml, exist_ok=True)
                archivo_kml = os.path.join(carpeta_kml, f"{nombre_salida}_mapeo.kml")
                archivo_kmz = os.path.join(carpeta_kml, f"{nombre_salida}_mapeo.kmz")
            else:
                archivo_kml = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kml")
                archivo_kmz = os.path.join(carpeta_salida, f"{nombre_salida}_mapeo.kmz")

            # Generar el KML/KMZ en modo plano (sin subcarpetas del KML)
            archivo_kml, desc_coords = _generar_kml_core(df, archivo_kml, config=config, flat=True)
            print(f"KML generado en: {archivo_kml}")

            # KMZ (si se pudo generar)
            if bool(config.get("salida", {}).get("separar_kml_kmz", False)):
                kml_dir = os.path.dirname(archivo_kml)
                base_dir = os.path.dirname(kml_dir) if os.path.basename(kml_dir).lower() == "kml" else kml_dir
                kmz_dir = os.path.join(base_dir, "kmz")
                kmz_path = os.path.join(kmz_dir, os.path.splitext(os.path.basename(archivo_kml))[0] + ".kmz")
            else:
                kmz_path = os.path.splitext(archivo_kml)[0] + ".kmz"

            if os.path.exists(kmz_path):
                print(f"KMZ generado en: {kmz_path}")

            print(f"Filas descartadas por coordenadas inválidas: {desc_coords}")
            # Nota: archivo_errores no está definido en scope original (posible bug)
            # print(f"Reporte de errores generado en: {archivo_errores}")
            return

        print("Opción no reconocida.")
