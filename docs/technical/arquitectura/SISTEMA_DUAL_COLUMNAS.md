# Sistema Dual de Columnas - Documentación Crítica

## 🚨 ADVERTENCIA PARA DESARROLLADORES

**NUNCA elimine o "optimice" el sistema dual de columnas. Ambas versiones son arquitectónicamente necesarias.**

## Resumen Ejecutivo

Durante la refactorización Fase 5.3a del TZ Analyzer se descubrió que el sistema mantiene **intencionalmente** dos versiones de los nombres de columnas:

1. **`df.attrs["orig_cols"]`** - Columnas originales del archivo
2. **`df.columns`** - Columnas normalizadas para procesamiento

Esta dualidad **NO ES UN BUG** sino una decisión arquitectónica crítica.

## Historia del Descubrimiento

### Contexto Inicial
Durante el análisis de la Fase 5.3 (carga de Excel), se identificó lo que inicialmente parecía ser una operación simple en la línea 6543. Sin embargo, el análisis detallado reveló un sistema dual complejo.

### Análisis de Timeline
Mediante análisis forense del código original se estableció el timing crítico:

```
Línea 6543: pd.read_excel()           # Carga inicial
Línea 6545: df.attrs["orig_cols"]     # Backup ANTES de normalización  
Líneas 6549-6557: Normalización       # Procesamiento de headers
Línea 7551: df._orig_cols             # Snapshot post-normalización
Línea 355: Wizard interactivo         # Sistema de UI
```

### Revelación Arquitectónica
El análisis reveló que **ambos sistemas de columnas tienen propósitos específicos**:

- **UI/Presentación**: Necesita mostrar nombres exactos del archivo al usuario
- **Algoritmo/Procesamiento**: Necesita nombres limpiados sin espacios ni caracteres especiales

## Arquitectura del Sistema

### Componente 1: Columnas Originales
```python
df.attrs["orig_cols"] = list(df.columns)  # Línea 6545 original
```

**Propósito**: Preservar nombres exactos del archivo Excel para la interfaz de usuario

**Características**:
- Mantiene espacios en blanco
- Preserva caracteres especiales  
- Formato exacto como aparece en Excel
- **NUNCA debe ser modificado después de la carga**

**Ejemplo**:
```python
# Archivo Excel tiene: "  Timestamp  ", "Latitud ", " Longitud"
df.attrs["orig_cols"] = ["  Timestamp  ", "Latitud ", " Longitud"]
```

### Componente 2: Columnas Normalizadas
```python
df.columns = [str(col).strip() for col in df.columns]  # Líneas 6549-6557
```

**Propósito**: Estandarizar nombres para el procesamiento interno

**Características**:
- Remueve espacios en blanco
- Convierte a string normalizado
- Facilita acceso programático
- Usado por toda la lógica interna

**Ejemplo**:
```python
# Después de normalización
df.columns = ["Timestamp", "Latitud", "Longitud"]
```

## Casos de Uso Críticos

### 1. Interfaz de Usuario
Cuando el sistema muestra las columnas disponibles al usuario para mapeo manual, **debe** usar `df.attrs["orig_cols"]` para que el usuario reconozca los nombres exactos de su archivo.

### 2. Procesamiento de Datos
Todo el algoritmo interno usa `df.columns` normalizado para evitar problemas con espacios y caracteres especiales en el código.

### 3. Sistema de Sinónimos
El mapeo de sinónimos funciona con nombres normalizados, pero debe preservar la referencia a originales para la UI.

## Implementación en tz_core.data_loader

### Función Principal
```python
def cargar_excel_con_normalizacion(ruta_excel: str, hoja_elegida: Optional[str] = None):
    # PASO 1: Carga inicial
    df = pd.read_excel(ruta_excel, sheet_name=hoja_elegida)
    
    # PASO 2: Backup inmediato de originales 
    df.attrs["orig_cols"] = list(df.columns)
    
    # PASO 3: Normalización para algoritmo
    df.columns = [str(col).strip() for col in df.columns]
    
    # PASO 4: Validación del sistema dual
    assert "orig_cols" in df.attrs
    assert len(df.attrs["orig_cols"]) == len(df.columns)
    
    return df, hoja_usada
```

### Validaciones Críticas
La función incluye validaciones para asegurar que el sistema dual esté funcional:
- Verifica existencia de `orig_cols`
- Confirma consistencia de conteos
- Asegura timing correcto (backup antes de normalización)

## Testing y Validación

### Tests Unitarios
Los tests en `test_data_loader.py` verifican:

1. **Preservación de originales**: `df.attrs["orig_cols"]` mantiene nombres exactos
2. **Normalización correcta**: `df.columns` tiene nombres limpiados  
3. **Consistencia**: Ambos sistemas tienen el mismo número de elementos
4. **Integridad de datos**: Los datos no se corrompen durante el proceso

### Ejemplo de Test Crítico
```python
def test_carga_exitosa_con_sistema_dual(self):
    # Archivo con espacios problemáticos
    df_test = pd.DataFrame({
        'Columna 1  ': [1, 2, 3],      # Espacios al final
        '  Columna 2': [4, 5, 6],      # Espacios al inicio  
        'Columna 3': [7, 8, 9]         # Sin espacios
    })
    
    df_resultado, _ = cargar_excel_con_normalizacion(tmp_path)
    
    # Verificar sistema dual
    assert df_resultado.attrs["orig_cols"] == ['Columna 1  ', '  Columna 2', 'Columna 3']
    assert list(df_resultado.columns) == ['Columna 1', 'Columna 2', 'Columna 3']
```

## Migración y Compatibilidad

### Wrapper de Compatibilidad
En el script principal se mantiene un wrapper que:
- Preserva la firma original de la función
- Mantiene compatibilidad completa
- Documenta el cambio arquitectónico

```python
def _cargar_excel_con_normalizacion(ruta_excel, hoja_elegida=None):
    """
    Wrapper de compatibilidad que preserva el sistema dual de columnas
    extraído en Fase 5.3a
    """
    from tz_core.data_loader import cargar_excel_con_normalizacion
    return cargar_excel_con_normalizacion(ruta_excel, hoja_elegida)
```

## Advertencias para el Futuro

### ❌ NO Hacer
- Eliminar `df.attrs["orig_cols"]` como "duplicación innecesaria"
- "Optimizar" usando solo una versión de columnas
- Modificar `orig_cols` después de la carga inicial
- Cambiar el timing de backup vs normalización

### ✅ SÍ Hacer  
- Mantener ambos sistemas funcionando
- Usar `orig_cols` para UI y `columns` para algoritmo
- Validar consistencia entre ambos sistemas
- Documentar cualquier cambio en esta arquitectura

## Contacto y Mantenimiento

Este documento debe actualizarse si se realizan cambios al sistema dual de columnas. 

**Responsabilidad**: Equipo de refactorización TZ Analyzer
**Fecha de creación**: Fase 5.3a
**Última actualización**: Octubre 2025

---

**Recuerda**: Este sistema existe por una razón arquitectónica válida. La aparente "duplicación" es funcionalidad, no bug.