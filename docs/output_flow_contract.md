# Contrato: run_outputs_flow

## 1) Propósito

`run_outputs_flow` es un **wrapper defensivo** que orquesta la generación de salidas HTML/KML/KMZ/hashes para un caso procesado. Su responsabilidad principal es:

- Invocar la función de pipeline `produce_fn` (en práctica: `produce_case_outputs` de `tz_core.output_pipeline`)
- Capturar excepciones para evitar que el flujo principal falle por errores en generación de salidas
- Almacenar secciones HTML generadas en globals del monolito mediante callbacks
- Registrar información de diagnóstico mediante logger
- Retornar resultado exitoso o `None` en caso de error

Este módulo actúa como **boundary** entre el monolito y la lógica pura de generación de salidas, permitiendo pruebas unitarias aisladas mediante inyección de dependencias.

---

## 2) Firma y parámetros (reales)

**Módulo**: `tz_core/output_runner.py`

**Firma completa**:
```python
def run_outputs_flow(
    *,
    df,                                      # pd.DataFrame: dataset procesado con coordenadas
    config,                                  # Dict[str, Any]: CONFIG global con claves html/columnas/salida
    nombre_salida: str,                      # Nombre base del caso (ej: "TEL_123456_2026-01-05")
    archivo_kml: str,                        # Path absoluto del KML a generar
    carpeta_base: str,                       # Carpeta raíz destino (ej: cwd o seleccionada por usuario)
    carpeta_salida: str,                     # Carpeta del caso específico (carpeta_base/nombre_salida)
    archivo_entrada: str,                    # Path absoluto del Excel original
    hoja: Any,                               # Nombre de la hoja Excel usada (o None)
    archivo_errores: str,                    # Path del reporte de errores (ej: "nombre_salida_errores.txt")
    desc_coords: Any,                        # Contador de coordenadas descartadas (int)
    build_interactions_section: Callable[..., Any],  # Función que construye HTML de interacciones recientes
    build_contacts_section: Callable[..., Any],      # Función que construye HTML de todos los contactos
    generar_html_fn: Callable[..., Any],     # Función que genera el informe HTML final
    relocate_kmz_fn: Callable[..., Any],     # Función que mueve/renombra KMZ según configuración
    write_hashes_fn: Callable[..., Any],     # Función que escribe HASHES.txt con checksums
    produce_fn: Callable[..., Any],          # Pipeline principal (produce_case_outputs)
    summarize_fn: Callable[..., Any],        # Función que imprime resumen de salidas
    logger: Callable[[str], None],           # Función de logging (ej: función `log` del monolito)
    output_fn: Callable[[str], None],        # Función de output (ej: `print`)
    path_exists: Callable[[str], bool],      # Verificación de existencia de archivos (ej: os.path.exists)
    cwd_fn: Callable[[], str],               # Función que retorna cwd (ej: os.getcwd)
    log_file_path: Optional[str],            # Path del archivo de log generado (o None)
    set_interactions_section: Callable[[str], None],  # Callback para almacenar HTML interacciones en global
    set_contacts_section: Callable[[str], None],      # Callback para almacenar HTML contactos en global
):
```

**Notas sobre parámetros**:
- Todos los parámetros son **keyword-only** (asterisco inicial).
- `df`, `config`, `hoja`, `desc_coords` tienen tipos flexibles (`Any`) para evitar acoplamiento fuerte.
- Las funciones inyectadas (`build_*`, `generar_*`, etc.) permiten testear sin código del monolito.
- `produce_fn` es el punto de extensión principal: actualmente `produce_case_outputs` de `tz_core.output_pipeline`.

---

## 3) Precondiciones (qué debe existir antes)

### Obligatorias
1. **`df` debe ser un DataFrame válido** con columnas normalizadas y coordenadas procesadas.
2. **`config` debe contener**:
   - `config["html"]["interacciones_ultimos_dias"]` (int, fallback a 3)
   - `config["columnas"]` (dict con mapeo de columnas)
   - `config["salida"]` (dict con `solo_kmz`, `separar_kml_kmz`, etc.)
3. **`carpeta_salida` debe existir** o ser creada por funciones previas (normalmente ya creada en etapa de setup).
4. **`archivo_entrada` debe ser legible** (para calcular hash en HASHES.txt).
5. **Callbacks (`build_interactions_section`, `build_contacts_section`, `generar_html_fn`, etc.) deben ser callables válidos**.

### Opcionales
- `log_file_path` puede ser `None` si no se genera log de ejecución.
- `hoja` puede ser `None` si el dataset no proviene de Excel multi-hoja.
- `desc_coords` puede ser 0 si no hubo coordenadas descartadas.

### Invariantes del sistema
- **CONFIG global** debe haber sido inicializado por `bootstrap_config()` antes de llamar esta función.
- **Imports de tz_core** (analytics, file_utils, output_pipeline) deben estar disponibles sin ImportError.
- **No debe haber side-effects de imports** (lazy imports manejados en `app_runner.py`).

---

## 4) Secuencia interna (paso a paso, con nombres reales)

### 4.1) Preparación
1. **Logger inicial**: `logger("[salidas] Construyendo salidas HTML/KML…")`
2. **Bloque try-except principal** envuelve toda la ejecución.

### 4.2) Invocación del pipeline (dentro del try)
3. **Llamada a `produce_fn`** (alias de `produce_case_outputs` en `tz_core.output_pipeline`):
   ```python
   resultado_salidas = produce_fn(
       df=df,
       config=config,
       nombre_salida=nombre_salida,
       archivo_kml=archivo_kml,
       carpeta_base=carpeta_base,
       carpeta_salida=carpeta_salida,
       archivo_entrada=archivo_entrada,
       hoja=hoja,
       error_report_path=archivo_errores,
       discarded_coords=desc_coords,
       build_interactions_section=build_interactions_section,
       build_contacts_section=build_contacts_section,
       generar_html_fn=generar_html_fn,
       relocate_kmz_fn=relocate_kmz_fn,
       write_hashes_fn=write_hashes_fn,
       summarize_fn=summarize_fn,
       logger=logger,
       output_fn=output_fn,
       path_exists=path_exists,
       cwd_fn=cwd_fn,
       log_file_path=log_file_path,
       set_interactions_section=set_interactions_section,
       set_contacts_section=set_contacts_section,
   )
   ```

### 4.3) Logging defensivo
4. **Bloque try-except anidado** para extraer paths de resultado:
   ```python
   try:
       html_path = resultado_salidas.get("html") if isinstance(resultado_salidas, dict) else None
       kmz_path = resultado_salidas.get("kmz") if isinstance(resultado_salidas, dict) else None
       hashes_path = resultado_salidas.get("hashes") if isinstance(resultado_salidas, dict) else None
       logger(f"[salidas] HTML={html_path} KMZ={kmz_path} HASHES={hashes_path}")
   except Exception:
       pass  # Si el resultado no es dict o falla el logging, continuar silenciosamente
   ```

### 4.4) Retorno exitoso
5. **Return** `resultado_salidas` (tipo: `ProduceOutputsResult` o dict o None según implementación de `produce_fn`).

### 4.5) Captura de errores (except principal)
6. **Si cualquier excepción** ocurre en el bloque principal:
   ```python
   except Exception as e:
       output_fn(f"[ERROR] Bloque HTML/KML falló: {e}")
       return None
   ```

---

## 5) Side-effects (archivos/logs, carpetas, stdout, etc.)

### Side-effects directos de `run_outputs_flow`
- **Logging**: Llama a `logger(...)` con mensajes de diagnóstico (mínimo 2 llamadas: inicio y resultado).
- **Stdout/stderr**: Llama a `output_fn(...)` con mensajes de error si falla.
- **Retorno**: Modifica el call stack retornando `resultado_salidas` o `None`.

### Side-effects delegados a `produce_fn` (`produce_case_outputs`)
**⚠️ IMPORTANTE**: Los siguientes side-effects ocurren **dentro** de `produce_fn`, NO en `run_outputs_flow` directamente.

#### Archivos generados
1. **Informe HTML**: `carpeta_salida/nombre_salida_informe.html` (vía `generar_html_fn`).
2. **KML**: `archivo_kml` (path especificado como parámetro, generado por `generar_html_fn` o lógica interna).
3. **KMZ**: `carpeta_salida/nombre_salida_mapeo.kmz` o carpeta separada según `config["salida"]["separar_kml_kmz"]` (vía `relocate_kmz_fn`).
4. **HASHES.txt**: `carpeta_salida/nombre_salida_hashes.txt` con checksums SHA256 de archivos relevantes (vía `write_hashes_fn`).
5. **LOG.txt** (opcional): Si `log_file_path` está presente, se incluye en HASHES.txt.

#### Carpetas creadas
- `carpeta_salida` (si no existe, creada por `os.makedirs` en `produce_case_outputs`).
- `carpeta_salida/kmz/` (si `config["salida"]["separar_kml_kmz"]` es True).

#### Globals mutados
- **`HTML_SECCION_INTERACCIONES`** (global del monolito): actualizado vía callback `set_interactions_section`.
- **`HTML_SECCION_TODOS_CONTACTOS`** (global del monolito): actualizado vía callback `set_contacts_section`.

#### Stdout/stderr
- Múltiples llamadas a `output_fn` (generalmente `print`) con progreso y mensajes de éxito/error.
- Llamadas a `logger` (función `log` del monolito) para traza detallada.

#### Operaciones de I/O adicionales
- **Lectura de archivos** para calcular hashes (Excel original, HTML, KMZ, log).
- **Copia/relocation de KMZ**: Puede mover archivo entre carpetas según configuración.
- **Escritura de errores**: Si `error_report_path` está presente, se maneja en etapas previas (no en `run_outputs_flow` directamente).

---

## 6) Salidas (qué retorna si retorna algo; si no, aclarar)

### Retorno exitoso
**Tipo**: Depende de implementación de `produce_fn`, en práctica es `ProduceOutputsResult` (dataclass de `tz_core.output_pipeline`).

**Estructura esperada** (si `produce_fn` retorna `ProduceOutputsResult`):
```python
@dataclass
class ProduceOutputsResult:
    informe_html: Optional[str]      # Path del HTML generado o None
    kmz_path: Optional[str]          # Path del KMZ final o None
    hashes_path: Optional[str]       # Path del HASHES.txt o None
    interactions_html: str           # HTML de sección interacciones (puede ser "")
    contacts_html: str               # HTML de sección contactos (puede ser "")
```

**Compatibilidad**: La función intenta acceder a `resultado_salidas.get("html")` como dict, indicando que también puede retornar un dict con claves `"html"`, `"kmz"`, `"hashes"`.

### Retorno de error
**Tipo**: `None`

**Condición**: Si cualquier excepción ocurre durante la ejecución del pipeline.

### Comportamiento en caller
El monolito **ignora el retorno** de `run_outputs_flow` (no hay asignación en el script principal). Las salidas se almacenan en globals vía callbacks, y los archivos se generan como side-effects.

---

## 7) Manejo de errores (qué captura vs qué propaga)

### Errores capturados (swallowed)
- **Cualquier `Exception`** lanzada por `produce_fn` o sus dependencias.
- **Excepciones en logging defensivo** (bloque try-except anidado al extraer paths).

### Errores propagados
- **Ninguno**: La función está diseñada para NO propagar excepciones al caller.
- Garantiza que el flujo principal (orquestador del monolito) continúe incluso si falla la generación de salidas.

### Logging de errores
- Errores capturados se imprimen vía `output_fn(f"[ERROR] Bloque HTML/KML falló: {e}")`.
- **NO se usa `raise` ni `sys.exit()`**.

### Implicaciones
- **Silent failures posibles**: Si `produce_fn` falla, el usuario ve el mensaje de error pero el programa continúa.
- **No hay rollback automático**: Archivos parcialmente generados pueden quedar en disco.
- **Responsabilidad del caller**: Debe verificar existencia de archivos de salida o inspeccionar logs para confirmar éxito real.

---

## 8) Dependencias (módulos tz_core/tz_services y globals si aplica)

### Dependencias de módulos importados
- **`tz_core.output_pipeline`**: Proporciona `produce_case_outputs` (función principal del pipeline).
- **Transitividad**: `produce_case_outputs` depende de:
  - `tz_core.analytics.construir_seccion_todos_contactos`
  - `tz_core.file_utils.escribe_hashes_txt`, `relocate_kmz_file`
  - `tz_core.ui_utils.summarize_outputs`
  - `tz_core.html_generator` (para `generar_informe_html` si se inyecta desde el monolito)

### Dependencias inyectadas (en práctica, desde el monolito)
En el script principal (`script_principal_bitacoras_refactory.py`), las funciones inyectadas son:

1. **`build_interactions_section`** → `_construir_seccion_interacciones` (función local del monolito, línea 439).
2. **`build_contacts_section`** → `construir_seccion_todos_contactos` (de `tz_core.analytics`, línea 396).
3. **`generar_html_fn`** → `generar_informe_html` (función local del monolito, línea 1105).
4. **`relocate_kmz_fn`** → `relocate_kmz_file` (de `tz_core.file_utils`, línea 397).
5. **`write_hashes_fn`** → `escribe_hashes_txt` (de `tz_core.file_utils`, línea 397).
6. **`produce_fn`** → `produce_case_outputs` (de `tz_core.output_pipeline`, línea 404).
7. **`summarize_fn`** → `summarize_outputs` (de `tz_core.ui_utils`, línea 112).
8. **`logger`** → función `log` del monolito (definida localmente).
9. **`output_fn`** → `print` (built-in de Python).
10. **`path_exists`** → `os.path.exists` (stdlib).
11. **`cwd_fn`** → `os.getcwd` (stdlib).
12. **`set_interactions_section`** → `_store_interacciones` (closure local del monolito, línea 2981).
13. **`set_contacts_section`** → `_store_contactos` (closure local del monolito, línea 2985).

### Dependencias de globals (indirectas)
- **`CONFIG`**: Accedido dentro de `produce_case_outputs` y funciones inyectadas.
- **`HTML_SECCION_INTERACCIONES`**: Mutado vía `set_interactions_section`.
- **`HTML_SECCION_TODOS_CONTACTOS`**: Mutado vía `set_contacts_section`.
- **`LOG_FILE`**: Leído como `globals().get("LOG_FILE")` para `log_file_path` (línea 3011 del monolito).

### Dependencias de filesystem
- Carpeta `carpeta_salida` debe existir o ser creada por `produce_case_outputs`.
- Archivo `archivo_entrada` debe ser legible para hashing.
- Path `archivo_kml` debe estar en carpeta escribible.

---

## 9) Puntos frágiles / riesgos (solo observación)

### 🔴 Alto riesgo
1. **Mutación de globals**: Los callbacks `set_interactions_section` y `set_contacts_section` mutan globals del monolito (`HTML_SECCION_INTERACCIONES`, `HTML_SECCION_TODOS_CONTACTOS`). Si se refactoriza el monolito sin actualizar estos callbacks, pueden quedar referencias muertas o silenciosamente no actualizar el estado esperado.

2. **Falta de transaccionalidad**: Si `produce_fn` falla después de escribir HTML pero antes de generar KMZ, el sistema queda en estado inconsistente (archivo parcial en disco, sin rollback).

3. **Logging silenciado**: El bloque try-except anidado (líneas 67-70 del código) swallow excepciones al extraer paths del resultado. Si `produce_fn` retorna un tipo inesperado, no hay alerta clara.

4. **Dependencia de CONFIG global**: Aunque `config` se pasa como parámetro, funciones inyectadas como `generar_informe_html` pueden acceder a `CONFIG` directamente, creando dependencia oculta. Refactorizar requiere threading explícito del contexto.

### 🟡 Riesgo moderado
5. **Side-effects no documentados**: El contrato de `produce_fn` y funciones inyectadas NO está formalizado; solo se conoce por inspección del código. Cambios en firmas pueden romper silenciosamente.

6. **Error swallowing**: Cualquier excepción se convierte en retorno `None` sin stack trace completo (solo mensaje). Debugging de failures requiere inspección de logs externos.

7. **Rutas hardcodeadas en funciones inyectadas**: `generar_informe_html` y `relocate_kmz_file` pueden asumir estructura de carpetas específica. Cambios en configuración de rutas pueden fallar sin validación previa.

### 🟢 Bajo riesgo
8. **Tipos flexibles**: El uso de `Any` para `df`, `hoja`, etc., reduce seguridad de tipos pero facilita testing con mocks. Riesgo aceptable mientras existan tests de integración.

9. **Path normalization**: No hay validación explícita de que `carpeta_salida` sea path absoluto vs relativo. Dependencia implícita de funciones previas para sanitización.

10. **Callback exceptions**: Si `set_interactions_section` o `set_contacts_section` lanzan excepciones, se capturan silenciosamente en `produce_case_outputs` (bloques try-except internos). No afecta flujo principal pero puede ocultar bugs.

---

## 10) Recomendaciones para extracción/refactorización (futuro)

### Fase 1: Formalizar contrato
- [ ] Definir protocol/ABC para `produce_fn` y funciones inyectadas.
- [ ] Reemplazar `Any` por tipos explícitos donde sea seguro (ej: `df: pd.DataFrame`).
- [ ] Documentar precondiciones y postcondiciones como docstrings estructurados.

### Fase 2: Eliminar dependencias de globals
- [ ] Pasar contexto explícito (`AppContext`) en lugar de callbacks que mutan globals.
- [ ] Mover almacenamiento de secciones HTML a retorno de `run_outputs_flow`.

### Fase 3: Transaccionalidad
- [ ] Implementar patrón "staging folder" + atomic rename para salidas.
- [ ] Rollback automático si `produce_fn` falla después de escribir archivos.

### Fase 4: Observabilidad
- [ ] Añadir structured logging con niveles (DEBUG/INFO/ERROR).
- [ ] Retornar objeto `OutputFlowResult` con status code, paths generados y errores capturados.

### Fase 5: Testing
- [ ] Tests unitarios con mocks para cada función inyectada.
- [ ] Tests de integración con fixture de archivos reales.
- [ ] Golden files para validar outputs byte-a-byte.

---

**Fin del contrato**. Este documento debe actualizarse si la implementación de `run_outputs_flow` o `produce_case_outputs` cambia.
