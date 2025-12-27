"""
mapping_wizard.py — Wizard interactivo para mapeo de columnas Excel → canónicas
=================================================================================

MIGRADO DE: script_principal_bitacoras_refactory.py L183-565 (Epic 15)
FECHA: 27/12/2025
RAZÓN: Modularización arquitectura híbrida (Epic 15 - Wizard QC completo)

⚡ ADVERTENCIA: Código crítico de 382 líneas extraído con máxima precaución.
Este módulo implementa el wizard interactivo QC manual marcado previamente
como "PELIGRO EXTREMO". La extracción se realizó con protocolo paranoico.

ARQUITECTURA:
- MappingWizard: Clase principal con separación de responsabilidades
- UI Layer: Interacción con usuario (input/print)
- Logic Layer: Procesamiento de mapeos y validaciones
- Data Layer: Aplicación de transformaciones a DataFrame

DEPENDENCIAS:
- pandas: Manipulación DataFrame
- input(): Interacción consola (17+ llamadas)

USO:
    from tz_core.mapping_wizard import MappingWizard
    
    wizard = MappingWizard(df, esenciales=["fecha", "tel", "lat", "long"], 
                           no_esenciales=["alias", "duracion"])
    df_mapeado, asignaciones = wizard.run()

COMPATIBILIDAD:
Mantiene firma exacta de _wizard_qc_mapeo() original para garantizar cero regresiones.
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple, Set, Any


class MappingWizard:
    """
    Wizard interactivo profesional para mapeo de columnas Excel → canónicas.
    
    ⚡ CÓDIGO CRÍTICO: Extraído de monolito con protocolo paranoico.
    Esta clase reemplaza _wizard_qc_mapeo() sin modificar comportamiento.
    
    Attributes:
        original_df: DataFrame original (inmutable)
        cols_menu: Lista de columnas disponibles para mapeo
        esenciales: Lista de campos canónicos esenciales
        no_esenciales: Lista de campos canónicos no esenciales
        asignadas: Dict de mapeos {canónico: (tipo, valor)}
        usadas: Set de columnas ya asignadas (evita duplicados)
        pendientes: Lista de esenciales omitidos
    """
    
    def __init__(self, df: pd.DataFrame, esenciales: Optional[List[str]] = None, 
                 no_esenciales: Optional[List[str]] = None):
        """
        Inicializa wizard con DataFrame y configuración de campos.
        
        Args:
            df: DataFrame con columnas a mapear
            esenciales: Lista de campos canónicos esenciales (default: fecha/hora/tel/lat/long/etc)
            no_esenciales: Lista de campos canónicos no esenciales (default: alias/duracion/etc)
        """
        # Estado inmutable
        self.original_df = df
        self.cols_menu = list(map(str, getattr(df, "_orig_cols", list(df.columns))))
        
        # Configuración de campos
        self.esenciales = esenciales if esenciales is not None else self._default_esenciales()
        self.no_esenciales = no_esenciales if no_esenciales is not None else self._default_no_esenciales()
        self.etiquetas_mapeo = self._build_labels()
        self.tipar_numericos = {"lat", "long", "azimut", "duracion"}
        
        # Estado mutable (tracking de mapeos)
        self.asignadas: Dict[str, Tuple[str, Any]] = {}  # canónico -> (tipo, valor)
        self.usadas: Set[str] = set()  # columnas ya tomadas
        self.pendientes: List[str] = []  # esenciales omitidos
    
    # =========================================================================
    # === CONFIGURACIÓN Y DEFAULTS ===
    # =========================================================================
    
    @staticmethod
    def _default_esenciales() -> List[str]:
        """Retorna lista default de campos esenciales."""
        return ["fecha", "hora", "tel", "imei", "interaccion", "contacto", 
                "lat", "long", "azimut", "antena"]
    
    @staticmethod
    def _default_no_esenciales() -> List[str]:
        """Retorna lista default de campos no esenciales."""
        return ["alias", "nombre_usuario", "abonado", "celda", "direccion", 
                "imei", "imsi", "duracion", "contacto", "interaccion"]
    
    @staticmethod
    def _build_labels() -> Dict[str, str]:
        """Construye diccionario de etiquetas amigables para mapeo."""
        return {
            "tel": "Tel u Origen",
            "contacto": "Contacto o Destino",
            "interaccion": "Interacción o Tipo"
        }
    
    # =========================================================================
    # === PUBLIC API - PUNTO DE ENTRADA ===
    # =========================================================================
    
    def run(self) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
        """
        Ejecuta wizard completo de mapeo interactivo.
        
        Flujo:
        1. Mapear campos esenciales (input usuario)
        2. Mapear campos no esenciales (input usuario)
        3. Mostrar resumen
        4. Preguntar identidad (alias/nombre_usuario/abonado)
        5. Mostrar vista previa
        6. Remapeo rápido opcional
        7. Aplicar mapeo al DataFrame
        8. Confirmación (S/N/R loop)
        
        Returns:
            Tuple[DataFrame mapeado, Dict asignaciones]
        """
        # Fase 1: Mapeo inicial
        self._map_essentials()
        self._map_non_essentials()
        self._show_summary()
        
        # Fase 2: Metadatos y preview
        df_temp = self._apply_mapping()
        df_temp = self._handle_identity_fields(df_temp)
        self._show_preview(df_temp)
        df_temp = self._quick_remap(df_temp)
        
        # Fase 3: Confirmación con loop S/N/R
        return self._confirm_loop(df_temp)
    
    # =========================================================================
    # === UI LAYER - INTERACCIÓN CON USUARIO ===
    # =========================================================================
    
    def _menu_horizontal(self, cols: List[str], per_line: int = 6) -> str:
        """
        Genera menú horizontal formateado de columnas numeradas.
        
        Args:
            cols: Lista de nombres de columnas
            per_line: Número de columnas por línea
        
        Returns:
            String con menú formateado multi-línea
        """
        filas, fila = [], []
        for i, c in enumerate(cols, 1):
            s = f"[{i}] {c}"
            fila.append(s)
            if len(fila) == per_line:
                filas.append("  " + "  |  ".join(fila))
                fila = []
        if fila:
            filas.append("  " + "  |  ".join(fila))
        return "\n".join(filas)
    
    def _ask_column_for_essential(self, canonical: str) -> Optional[str]:
        """
        Pregunta al usuario qué columna asignar a un campo esencial.
        
        Valida duplicados: si la columna ya fue asignada a otro esencial,
        pide otra columna. Permite Enter=omitir o '?'=ver menú.
        
        Args:
            canonical: Nombre del campo canónico
        
        Returns:
            Nombre de columna seleccionada o None si se omitió
        """
        etiqueta_visible = self.etiquetas_mapeo.get(canonical, canonical)
        
        while True:
            sel = input(f"→ Elegí columna para {etiqueta_visible} (número — '?' para ver menú / Enter=omitir): ").strip()
            if sel == "?":
                print(self._menu_horizontal(self.cols_menu, per_line=6))
                continue
            break
        
        if not sel:
            self.pendientes.append(canonical)
            self.asignadas[canonical] = ("omitido", None)
            return None
        
        # Validar número y duplicados
        ok = False
        while not ok:
            try:
                k = int(sel)
                if 1 <= k <= len(self.cols_menu):
                    col = self.cols_menu[k-1]
                    if col in self.usadas:
                        print(f"  [QC] Advertencia: la columna '{col}' ya fue asignada a otro esencial. Elegí otra.")
                        sel = input(f"→ Elegí columna para **{canonical}**: ").strip()
                        continue
                    self.asignadas[canonical] = ("col", col)
                    self.usadas.add(col)
                    return col
            except Exception:
                pass
            sel = input("  [QC] Entrada inválida. Debe ser un número de la lista (o Enter=omitir): ").strip()
            if not sel:
                self.pendientes.append(canonical)
                self.asignadas[canonical] = ("omitido", None)
                return None
    
    def _ask_column_for_non_essential(self, canonical: str) -> None:
        """
        Pregunta al usuario cómo mapear un campo no esencial.
        
        Opciones:
        - Número: asignar columna
        - "F <valor>": valor fijo para todo el DataFrame
        - Enter: omitir campo
        - "?": ver menú de columnas
        
        Args:
            canonical: Nombre del campo canónico
        """
        etiqueta_visible = self.etiquetas_mapeo.get(canonical, canonical)
        
        while True:
            sel = input(f"→ Elegí columna para {etiqueta_visible} (n / 'F valor' / Enter=omitir — '?' para ver menú): ").strip()
            if sel == "?":
                print(self._menu_horizontal(self.cols_menu, per_line=6))
                continue
            break
        
        if not sel:
            self.asignadas[canonical] = ("omitido", None)
        elif sel.upper().startswith("F "):
            val = sel[2:].strip()
            self.asignadas[canonical] = ("fijo", val)
        else:
            # número de columna
            try:
                k = int(sel)
                if 1 <= k <= len(self.cols_menu):
                    col = self.cols_menu[k-1]
                    self.asignadas[canonical] = ("col", col)
                else:
                    self.asignadas[canonical] = ("omitido", None)
            except:
                self.asignadas[canonical] = ("omitido", None)
    
    def _show_summary(self) -> None:
        """Muestra resumen visual de todos los mapeos realizados."""
        print("\n[QC] === Resumen de mapeo ===")
        for k, (t, v) in self.asignadas.items():
            if t == "col":
                print(f"  {k:12s} <- columna '{v}'")
            elif t == "fijo":
                print(f"  {k:12s} <- fijo '{v}'")
            else:
                print(f"  {k:12s} <- omitido")
        
        if self.pendientes:
            print("\n[QC] Aviso: omitiste canónicos ESENCIALES:", ", ".join(self.pendientes))
            print("Podés volver a ejecutar para completar esos campos, o continuar bajo tu responsabilidad.")
    
    def _show_preview(self, df: pd.DataFrame) -> None:
        """Muestra vista previa de las primeras 3 filas del DataFrame mapeado."""
        try:
            print("\n[QC] Vista previa (3 filas):")
            cols_preview = [c for c in self.esenciales + self.no_esenciales if c in df.columns]
            print(df.head(3)[cols_preview])
        except Exception:
            pass
    
    # =========================================================================
    # === LOGIC LAYER - PROCESAMIENTO DE MAPEOS ===
    # =========================================================================
    
    def _map_essentials(self) -> None:
        """
        Mapea todos los campos esenciales mediante interacción con usuario.
        
        Muestra menú de columnas una sola vez, luego pregunta por cada
        campo esencial en orden. Valida duplicados.
        """
        print("\n[QC] Columnas disponibles (una sola vez):")
        print(self._menu_horizontal(self.cols_menu, per_line=6))
        print("\n[QC] === Mapeo ESENCIALES ===")
        
        for canonical in self.esenciales:
            self._ask_column_for_essential(canonical)
    
    def _map_non_essentials(self) -> None:
        """
        Mapea todos los campos no esenciales mediante interacción con usuario.
        
        Muestra menú de columnas y permite asignación de columna, valor fijo
        o omitir. No valida duplicados (permitido para no esenciales).
        """
        print("\n[QC] === Mapeo NO ESENCIALES ===")
        print(self._menu_horizontal(self.cols_menu, per_line=6))
        print("  Podés: elegir número, escribir 'F <valor fijo>' o Enter=omitir.")
        
        for canonical in self.no_esenciales:
            self._ask_column_for_non_essential(canonical)
    
    def _apply_mapping(self) -> pd.DataFrame:
        """
        Aplica todos los mapeos al DataFrame y retorna copia modificada.
        
        Operaciones:
        1. Rename columnas según asignaciones "col"
        2. Asignar valores fijos según asignaciones "fijo"
        3. Eliminar columnas duplicadas
        4. Tipar campos numéricos (lat/long/azimut/duracion)
        5. Fallback antena/siteid
        
        Returns:
            DataFrame con mapeo aplicado
        """
        df = self.original_df.copy()
        
        # Aplicar mapeos
        for canonical, (tipo, val) in self.asignadas.items():
            if tipo == "col":
                src = val
                if src != canonical:
                    if src in df.columns:
                        df = df.rename(columns={src: canonical})
                    else:
                        # fallback por si difiere solo en espacios/caso
                        for c in list(df.columns):
                            if str(c).strip().lower() == str(src).strip().lower():
                                df = df.rename(columns={c: canonical})
                                break
            elif tipo == "fijo":
                df[canonical] = val
            # tipo "omitido" -> no hacer nada
        
        # Eliminar duplicados (por si renombramos a la misma canónica dos veces)
        df = df.loc[:, ~df.columns.duplicated(keep="first")]
        
        # Tipado numérico robusto
        for c in self.tipar_numericos:
            if c in df.columns:
                try:
                    serie = df[c]
                    # Si por alguna razón viene 2D, exprimimos a 1D
                    if hasattr(serie, "squeeze"):
                        serie = serie.squeeze()
                    df[c] = pd.to_numeric(serie, errors="coerce")
                except Exception as e:
                    print(f"[QC] Aviso: no se pudo convertir '{c}' a numérico ({e}); se deja como está.")
        
        # Fallback antena/siteid
        if "antena" not in df.columns and "siteid" in df.columns:
            df = df.rename(columns={"siteid": "antena"})
        df = df.loc[:, ~df.columns.duplicated(keep="first")]
        
        return df
    
    def _handle_identity_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pregunta por campos de identidad (alias/nombre_usuario/abonado) si faltan o están vacíos.
        
        Args:
            df: DataFrame con mapeo aplicado
        
        Returns:
            DataFrame con campos de identidad agregados si usuario los proveyó
        """
        for etiqueta in ("alias", "nombre_usuario", "abonado"):
            falta_col = etiqueta not in df.columns
            vacio = False
            if not falta_col:
                try:
                    vacio = bool(df[etiqueta].isna().all() or (df[etiqueta].astype(str).str.strip() == '').all())
                except Exception:
                    vacio = True
            if falta_col or vacio:
                try:
                    entrada = input(f"→ {etiqueta.capitalize()} para toda la ejecución (Enter=omitir): ").strip()
                except Exception:
                    entrada = ""
                if entrada:
                    df[etiqueta] = entrada
        return df
    
    def _quick_remap(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ofrece remapeo rápido de campos recomendados omitidos (ej. duracion).
        
        Args:
            df: DataFrame con mapeo aplicado
        
        Returns:
            DataFrame potencialmente con campos adicionales mapeados
        """
        recomendadas = ["duracion"]
        falt = [c for c in recomendadas if c not in df.columns]
        if falt:
            print("\n[QC] Aviso: omitiste asignar -> " + ", ".join(falt))
            resp = input("¿Querés mapearlas ahora? (s/N): ").strip().lower()
            if resp == "s":
                for can in list(falt):
                    sel = input(f"→ Elegí columna para {can} (n / 'F valor' / Enter=omitir): ").strip()
                    if not sel:
                        continue
                    if sel.upper().startswith("F "):
                        df[can] = sel[2:].strip()
                        continue
                    try:
                        k = int(sel)
                        if 1 <= k <= len(self.cols_menu):
                            col = self.cols_menu[k-1]
                            if col != can and col in df.columns:
                                df = df.rename(columns={col: can})
                    except:
                        pass
                # limpia duplicados
                df = df.loc[:, ~df.columns.duplicated(keep="first")]
        return df
    
    # =========================================================================
    # === CONFIRMATION LAYER - LOOP S/N/R ===
    # =========================================================================
    
    def _confirm_loop(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
        """
        Loop de confirmación: S=confirmar, N=reiniciar, R=remapear uno.
        
        Este es el punto crítico con recursividad (opción N).
        
        Args:
            df: DataFrame con mapeo aplicado
        
        Returns:
            Tuple[DataFrame final, Dict asignaciones]
        """
        while True:
            print("\n[QC] Confirmar mapeo — S=Confirmar y continuar; N=Volver a mapear; R=Remapear uno:")
            op = input("→ Opción (S/N/R): ").strip().upper()
            
            if op in ("S", ""):
                return df, self.asignadas
            
            elif op == "N":
                print("[QC] Reiniciando mapeo completo...")
                # RECURSIÓN: crear nuevo wizard y ejecutar
                new_wizard = MappingWizard(self.original_df, self.esenciales, self.no_esenciales)
                return new_wizard.run()
            
            elif op == "R":
                self._remap_single_field()
                # Re-aplicar mapeo y volver a mostrar resumen
                df = self._apply_mapping()
                df = self._handle_identity_fields(df)
                self._show_summary()
            
            else:
                print("[QC] Opción inválida. Escribí S, N o R.")
    
    def _remap_single_field(self) -> None:
        """
        Remapea un solo campo canónico (opción R del loop de confirmación).
        
        Flujo:
        1. Mostrar menú de canónicos disponibles
        2. Usuario elige por número o nombre
        3. Confirmar selección
        4. Reasignar columna/fijo/omitir
        5. Actualizar self.asignadas
        """
        # Orden fijo para menú consistente
        orden_fijo = ["tel", "lat", "lon", "fecha", "hora", "azimut", "imei", "antena",
                      "interaccion", "contacto", "alias", "nombre_usuario", "abonado",
                      "celda", "direccion", "imsi", "duracion"]
        todos_base = list(dict.fromkeys((self.esenciales + self.no_esenciales)))
        todos = [c for c in orden_fijo if c in todos_base] + [c for c in todos_base if c not in orden_fijo]
        
        print("\n[QC] ¿Qué canónico querés remapear?")
        print("  " + "  |  ".join(f"[{i+1}] {c}" for i, c in enumerate(todos)))
        
        target = input("→ Escribí **número o nombre** (ej. 4 o fecha): ").strip()
        
        # Resolver selección a nombre de canónico
        can = None
        if target.isdigit():
            idx = int(target)
            if 1 <= idx <= len(todos):
                can = todos[idx-1]
            else:
                print("[QC] Número fuera de rango.")
                return
        else:
            # aceptar nombre exacto (case-insensitive)
            t = target.lower()
            for c in todos:
                if c.lower() == t:
                    can = c
                    break
            if not can:
                print("[QC] Canónico inválido. Usá número o nombre de la lista.")
                return
        
        # Confirmación explícita
        print(f"[QC] Remapearás: [{todos.index(can)+1}] {can}. ¿Confirmás? (s/N): ", end="")
        if input().strip().lower() != "s":
            return
        
        # Mostrar menú de columnas
        print(self._menu_horizontal(self.cols_menu, per_line=6))
        
        if can in self.esenciales:
            # Remapeo ESENCIAL (solo número / no 'F')
            sel = input(f"→ Elegí columna para **{can}** (número — '?' menú / Enter=omitir): ").strip()
            if sel == "?":
                print(self._menu_horizontal(self.cols_menu, per_line=6))
                return
            if not sel:
                self.asignadas[can] = ("omitido", None)
            else:
                try:
                    k = int(sel)
                    if 1 <= k <= len(self.cols_menu):
                        col = self.cols_menu[k-1]
                        # Liberar anterior si era 'col'
                        prev = self.asignadas.get(can)
                        if prev and prev[0] == "col":
                            try:
                                self.usadas.discard(prev[1])
                            except Exception:
                                pass
                        if col in self.usadas:
                            print(f"  [QC] '{col}' ya está usada por otro esencial.")
                            return
                        self.asignadas[can] = ("col", col)
                        self.usadas.add(col)
                    else:
                        self.asignadas[can] = ("omitido", None)
                except:
                    self.asignadas[can] = ("omitido", None)
        else:
            # Remapeo NO ESENCIAL (n / 'F valor' / Enter)
            sel = input(f"→ Elegí columna para {can} (n / 'F valor' / Enter=omitir — '?' menú): ").strip()
            if sel == "?":
                print(self._menu_horizontal(self.cols_menu, per_line=6))
                return
            if not sel:
                self.asignadas[can] = ("omitido", None)
            elif sel.upper().startswith("F "):
                val = sel[2:].strip()
                self.asignadas[can] = ("fijo", val)
            else:
                try:
                    k = int(sel)
                    if 1 <= k <= len(self.cols_menu):
                        col = self.cols_menu[k-1]
                        self.asignadas[can] = ("col", col)
                    else:
                        self.asignadas[can] = ("omitido", None)
                except:
                    self.asignadas[can] = ("omitido", None)


# =========================================================================
# === WRAPPER FUNCIÓN PARA COMPATIBILIDAD COMPLETA ===
# =========================================================================

def wizard_qc_mapeo(df: pd.DataFrame, esenciales: Optional[List[str]] = None,
                    no_esenciales: Optional[List[str]] = None) -> Tuple[pd.DataFrame, Dict[str, Tuple[str, Any]]]:
    """
    Wrapper función para compatibilidad 100% con _wizard_qc_mapeo() original.
    
    Mantiene firma exacta y comportamiento idéntico. Este wrapper permite
    reemplazar llamadas directas sin modificar código cliente.
    
    Args:
        df: DataFrame con columnas a mapear
        esenciales: Lista de campos canónicos esenciales (opcional)
        no_esenciales: Lista de campos canónicos no esenciales (opcional)
    
    Returns:
        Tuple[DataFrame mapeado, Dict asignaciones]
    
    Ejemplo:
        >>> df, asignaciones = wizard_qc_mapeo(df, esenciales=["fecha", "tel"])
    """
    wizard = MappingWizard(df, esenciales, no_esenciales)
    return wizard.run()
