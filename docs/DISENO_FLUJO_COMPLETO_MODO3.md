# DISEÑO COMPLETO — FLUJO DE USABILIDAD MODO 3

**Proyecto:** TZ Analyzer v1.0.0  
**Fecha:** 11 de abril de 2026  
**Diseñado por:** Tony (Omar Arias) + Claude Sonnet 4.5  
**Alcance:** Modo 3 únicamente (Ingresar antenas/puntos manualmente)  
**Estado:** DISEÑO COMPLETO — Pendiente implementación

---

## ⚠️ ALCANCE DE ESTE DOCUMENTO

Este documento contiene el diseño completo del flujo de usabilidad ÚNICAMENTE para el **Modo 3: Ingresar antenas/puntos manualmente** del menú principal de TZ Analyzer.

**DOCUMENTOS RELACIONADOS:**
- Modo 1 (Procesar bitácora completa): `DISENO_FLUJO_COMPLETO_MODO1.md`
- Modo 2 (Procesar bitácora filtrada por tiempo): `DISENO_FLUJO_COMPLETO_MODO2.md`
- Diagnóstico general de usabilidad: `DIAGNOSTICO_USABILIDAD_FASE_A.md`

---

## RESUMEN EJECUTIVO

| Métrica | Valor |
|---------|-------|
| Pantallas totales | 8 |
| Pantallas compartidas con Modo 1 | 1 (#1) |
| Pantallas específicas de Modo 3 | 7 (#3-#8 + validación) |
| Navegación tipo CRUD | Sí (A/L/E/G/V/S) |
| Salida del programa | Opción [S] agregada |
| Validaciones en tiempo real | Coordenadas, confirmaciones |
| Genera HTML | No (solo KML/KMZ) |

---

## PRINCIPIOS DE DISEÑO APLICADOS

### 1. Reutilización de Modo 1
Pantalla #1 (menú inicial) es idéntica a Modo 1. Se referencia, no se rediseña.

### 2. Sin selector de colores
Modo 3 usa color predeterminado. Usuario puede editar en Google Earth después.

### 3. Flujo CRUD intuitivo
Menú con opciones claras: Agregar, Listar, Eliminar, Generar, Volver, Salir.

### 4. Validaciones preventivas
Coordenadas validadas en tiempo real con mensajes de error útiles.

### 5. Eliminación de tecla Enter como atajo
Todo se maneja con letras (S/N/C/A) o números. Campos vacíos = omitir automáticamente.

### 6. Lenguaje técnico-profesional
Tono forense, contexto operativo, explicación clara de cada campo.

### 7. Equivalencia consola ↔ GUI
Cada opción (S/A/C/N) = 1 botón futuro en interfaz gráfica.

### 8. Branding
Crédito visible: "Desarrollado por Omar Arias (Tony Zero)"

---

## MAPA DEL FLUJO COMPLETO

```
[#1] Menú inicial (compartido con Modo 1)
  ↓
[#3] Selector de tipo de registro (Antenas vs Puntos)
  ↓
[#4] Menú CRUD (A/L/E/G/V/S)
  ↓
┌─────────────────────────────────────┐
│ BUCLE PRINCIPAL                     │
│                                     │
│ [A] → #5a o #5b (input de datos)   │
│        ↓                            │
│     Validación de coordenadas       │
│        ↓                            │
│     Confirmación S/N/C              │
│        ↓                            │
│     ¿Agregar otro? S/N              │
│        ↓                            │
│     Vuelve a #4                     │
│                                     │
│ [L] → #6 (lista de registros)       │
│        ↓                            │
│     Vuelve a #4                     │
│                                     │
│ [E] → #6 → Solicita # → Elimina     │
│        ↓                            │
│     Vuelve a #4                     │
│                                     │
│ [G] → #7 (confirmación)             │
│        ↓                            │
│     #8 (nombre de archivo)          │
│        ↓                            │
│     Generación KML/KMZ              │
│        ↓                            │
│     Vuelve a #4 (registros intactos)│
│                                     │
│ [V] → Confirmación → Menú principal │
│                                     │
│ [S] → Confirmación → Salir programa │
└─────────────────────────────────────┘
```

---

## PANTALLAS DETALLADAS

---

### PANTALLA #1: Menú inicial

**Estado:** Compartida con Modo 1  
**Referencia:** `DISENO_FLUJO_COMPLETO_MODO1.md` - Pantalla #1  
**Acción:** No requiere diseño (ya existe)

**Ver diseño completo en:** `docs/DISENO_FLUJO_COMPLETO_MODO1.md`

---

### PANTALLA #3: Selector de tipo de registro

```
═══════════════════════════════════════════════════════════════
  MODO MANUAL — TIPO DE REGISTRO
═══════════════════════════════════════════════════════════════

Seleccione el tipo de puntos que desea mapear:

[1] Antenas/Celdas telefónicas
    → Incluye: nombre, coordenadas GPS, azimut, dirección
    → Útil para representar orientación de antenas en el mapa
    → Ideal para: mapeo de infraestructura telefónica

[2] Puntos de interés (lugares, domicilios, escenas)
    → Incluye: nombre, coordenadas GPS, dirección, comentarios
    → Sin azimut (marcador simple en Google Earth)
    → Ideal para: ubicaciones de investigación, domicilios, escenas del hecho

Tipo (1/2, A=Atrás, C=Cancelar):
```

**Navegación:** 1/2/A/C  
**Botones GUI:** [Antenas/Celdas] [Puntos de interés] [← Atrás] [✕ Cancelar]

**Nota técnica:** Esta selección determina qué variante de Pantalla #5 se mostrará (5a o 5b).

---

### PANTALLA #4: Menú CRUD

**VARIANTE A — Cuando hay registros (ejemplo: 3):**

```
═══════════════════════════════════════════════════════════════
  GESTIÓN DE REGISTROS
═══════════════════════════════════════════════════════════════

Modo activo: Antenas/Celdas
Registros ingresados: 3

Opciones disponibles:

[A] Agregar nuevo registro
    → Ingresar coordenadas y datos de un punto

[L] Listar registros ingresados
    → Ver tabla con todos los puntos agregados

[E] Eliminar registro
    → Verá la lista de registros y seleccionará cuál borrar

[G] Generar archivos KML/KMZ
    → Crear archivos para visualización en Google Earth

[V] Volver al menú principal (perderá los 3 registros ingresados)

[S] Salir del programa

Opción (A/L/E/G/V/S):
```

---

**VARIANTE B — Cuando NO hay registros (0):**

```
═══════════════════════════════════════════════════════════════
  GESTIÓN DE REGISTROS
═══════════════════════════════════════════════════════════════

Modo activo: Antenas/Celdas
Registros ingresados: 0

Opciones disponibles:

[A] Agregar nuevo registro
    → Ingresar coordenadas y datos de un punto

[V] Volver al menú principal

[S] Salir del programa

Opción (A/V/S):
```

**Navegación:** A/L/E/G/V/S (dinámica según contador)  
**Botones GUI:** [➕ Agregar] [📋 Listar] [🗑️ Eliminar] [🗺️ Generar] [← Volver] [Salir]

**Lógica de deshabilitación:**
- L/E/G deshabilitados cuando `Registros = 0`
- V muestra advertencia dinámica: "perderá los N registros"
- S siempre disponible

---

### PANTALLA #5a: Input de datos — Antenas/Celdas

```
═══════════════════════════════════════════════════════════════
  NUEVO REGISTRO — ANTENA/CELDA
═══════════════════════════════════════════════════════════════

📡 DATOS DE LA ANTENA (obligatorios)

Nombre de la antena: 
Latitud (ejemplo: 13.68945): 
Longitud (ejemplo: -89.23456): 

─────────────────────────────────────────────────────────────────
📡 DATOS ADICIONALES DE LA ANTENA (opcionales)

Dirección: 
Azimut 0-359° (orientación de la antena):
  0°=Norte | 90°=Este | 180°=Sur | 270°=Oeste
  
Azimut: 

─────────────────────────────────────────────────────────────────
📱 INFORMACIÓN COMPLEMENTARIA (opcional)

Teléfono investigado: 
IMEI: 
Alias: 
Usuario: 
Abonado: 
Celda: 
LAC - Código de área de ubicación: 
Tipo de interacción (ejemplos: VOZ, SMS, DATOS): 
Contacto: 
Duración (segundos): 

─────────────────────────────────────────────────────────────────

¿Guardar este registro? (S=Sí, N=Descartar, C=Cancelar):
```

**Navegación:** Input secuencial / S/N/C  
**Botones GUI:** Formulario completo + [✓ Guardar] [Descartar] [✕ Cancelar]

**Post-confirmación (si S):**

```
✓ Registro agregado.

¿Desea agregar otro registro? (S=Sí, N=Volver al menú):
```

**Validación de coordenadas (si fuera de rango):**

```
⚠️ COORDENADAS FUERA DE RANGO

Valores ingresados:
  Latitud: 13
  Longitud: 89

Rangos válidos para El Salvador:
  Latitud: 13.0 a 14.5
  Longitud: -90.1 a -87.7 (debe ser negativa)

¿Reintentar ingreso de coordenadas? (S=Sí, C=Cancelar registro):
```

---

### PANTALLA #5b: Input de datos — Puntos de interés

```
═══════════════════════════════════════════════════════════════
  NUEVO REGISTRO — PUNTO DE INTERÉS
═══════════════════════════════════════════════════════════════

📍 DATOS DEL PUNTO (obligatorios)

Nombre/identificador del lugar: 
Latitud (ejemplo: 13.68945): 
Longitud (ejemplo: -89.23456): 

─────────────────────────────────────────────────────────────────
📍 INFORMACIÓN ADICIONAL (opcional)

Dirección: 
Comentarios: 

─────────────────────────────────────────────────────────────────

¿Guardar este registro? (S=Sí, N=Descartar, C=Cancelar):
```

**Navegación:** Input secuencial / S/N/C  
**Botones GUI:** Formulario completo + [✓ Guardar] [Descartar] [✕ Cancelar]

**Post-confirmación (si S):**

```
✓ Punto agregado.

¿Desea agregar otro punto? (S=Sí, N=Volver al menú):
```

**Diferencias con #5a:**
- Sin azimut (no aplica para puntos libres)
- Sin sección de información complementaria del caso
- Más simple: solo nombre, coords, dirección, comentarios

---

### PANTALLA #6: Lista de registros

**VARIANTE A — Antenas/Celdas:**

```
═══════════════════════════════════════════════════════════════
  REGISTROS INGRESADOS
═══════════════════════════════════════════════════════════════

Modo: Antenas/Celdas
Total de registros: 3

# | Nombre                      | Latitud    | Longitud   | Azimut
──┼─────────────────────────────┼────────────┼────────────┼────────
1 | Cafetal La Florida N 1      | 13.65644   | -89.27278  | 230°
2 | Antena Centro               | 13.69294   | -89.21821  | 180°
3 | Torre El Carmen             | 13.70123   | -89.19456  | 45°

─────────────────────────────────────────────────────────────────

Presione cualquier tecla para volver al menú...
```

---

**VARIANTE B — Puntos de interés:**

```
═══════════════════════════════════════════════════════════════
  REGISTROS INGRESADOS
═══════════════════════════════════════════════════════════════

Modo: Puntos de interés
Total de registros: 2

# | Nombre                      | Latitud    | Longitud
──┼─────────────────────────────┼────────────┼────────────
1 | Casa de alias Chepe         | 13.66714   | -89.27851
2 | Escena del hecho            | 13.68901   | -89.23456

─────────────────────────────────────────────────────────────────

Presione cualquier tecla para volver al menú...
```

**Navegación:** Cualquier tecla vuelve a Pantalla #4  
**Botones GUI:** [← Volver al menú]

**Uso adicional:** Esta pantalla también se muestra antes de solicitar número de registro a eliminar (opción E del menú CRUD).

---

### PANTALLA #7: Confirmación pre-generación

```
═══════════════════════════════════════════════════════════════
  CONFIRMACIÓN DE GENERACIÓN
═══════════════════════════════════════════════════════════════

Está a punto de generar los archivos KML/KMZ con los siguientes datos:

Modo: Antenas/Celdas
Total de registros: 3

💡 NOTA: Todos los puntos se mostrarán con color predeterminado en el mapa.
   Puede cambiar colores individuales editando el archivo en Google Earth.

Archivos a generar:
  🗺️ [nombre_base]_mapeo.kml
  🗺️ [nombre_base]_mapeo.kmz

Carpeta de destino: C:/Users/Omar Arias/Downloads

─────────────────────────────────────────────────────────────────

¿Confirma la generación? (S=Sí generar, N=Volver al menú):
```

**Navegación:** S/N  
**Botones GUI:** [✓ Generar] [← Volver]

**Si S:** Continúa a Pantalla #8  
**Si N:** Vuelve a Pantalla #4 (sin generar archivos)

---

### PANTALLA #8: Nombre base de archivo

```
═══════════════════════════════════════════════════════════════
  NOMBRE DE ARCHIVOS DE SALIDA
═══════════════════════════════════════════════════════════════

📁 CONFIGURACIÓN FINAL

El sistema generará los siguientes archivos en la carpeta de salida:

Carpeta de destino: C:\Users\Omar Arias\Downloads

Archivos a generar:
  🗺️ [nombre_base]_mapeo.kml
  🗺️ [nombre_base]_mapeo.kmz

─────────────────────────────────────────────────────────────────

💡 Nombre sugerido: 61090192_chepe

Puede aceptarlo dejando el campo como está o modificarlo.

Nombre base: [61090192_chepe]
```

**Comportamiento:**

**Si deja el campo sin modificar (teclea Enter):**

```
✓ Usando nombre sugerido: 61090192_chepe

Generando archivos...
```

**Si borra y escribe "mi_caso":**

```
✓ Nombre personalizado: mi_caso

Generando archivos...
```

**Navegación:** Campo pre-llenado editable  
**Botones GUI:** Campo de texto pre-llenado + [Generar]

**Post-generación:**

```
KML generado en: C:/Users/Omar Arias/Downloads\61090192_chepe\61090192_chepe_mapeo.kml
KMZ generado en: C:/Users/Omar Arias/Downloads\61090192_chepe\61090192_chepe_mapeo.kmz
Filas descartadas por coordenadas inválidas: 0

Presione cualquier tecla para volver al menú...
```

**Después de presionar tecla:** Vuelve a Pantalla #4 (los registros permanecen intactos para seguir agregando o generar con otro nombre).

---

## DIFERENCIAS CLAVE CON MODO 1 Y MODO 2

| Característica | Modo 1 | Modo 2 | Modo 3 |
|---------------|--------|--------|--------|
| Fuente de datos | Archivo Excel | Archivo Excel | Input manual |
| QC Wizard | Sí (10 campos esenciales) | Sí (igual que Modo 1) | No (no hay archivo) |
| Selector de colores | Sí | Sí | No (color automático) |
| Genera HTML | Sí | Sí | No (solo KML/KMZ) |
| Genera KML/KMZ | Sí | Sí | Sí |
| Tipo de flujo | Lineal (una pasada) | Lineal + filtro temporal | CRUD (agregar múltiples) |
| Navegación bidireccional | Hasta confirmación final | Hasta confirmación final | En todo el bucle CRUD |
| Punto de no retorno | Pantalla #24 | Pantalla #24 | No existe (siempre puede volver) |
| Salida del programa | No (bucle infinito) | No (bucle infinito) | Sí (opción S) |

---

## ISSUES CONOCIDOS EN IMPLEMENTACIÓN ACTUAL

### 🐛 ISSUE #1: No hay opción para salir del programa

**Severidad:** ALTA  
**Estado:** DISEÑADO — Pendiente implementación

**Descripción:**
- Usuario queda atrapado en bucle infinito del menú principal
- Única forma de salir es cerrar terminal manualmente
- No existe opción "Salir" en ningún menú

**Solución diseñada:**
- Agregar opción **[S] Salir del programa** en Pantalla #4
- Confirmación antes de salir (si hay registros sin generar)

---

### 🔴 ISSUE #2: Opción "Volver" es destructiva sin confirmación

**Severidad:** MEDIA  
**Estado:** DISEÑADO — Pendiente implementación

**Descripción:**
- Opción V en menú CRUD elimina todos los registros sin confirmación
- Usuario puede perder trabajo accidental

**Solución diseñada:**
- Pantalla #4 muestra advertencia dinámica: "perderá los N registros"
- Solicitar confirmación adicional antes de destruir datos

---

### ⚠️ ISSUE #3: Campos opcionales solicitan input innecesariamente

**Severidad:** BAJA  
**Estado:** DISEÑADO — Pendiente implementación

**Descripción:**
- Todos los campos opcionales solicitan input incluso si usuario los deja vacíos
- Genera fricción (ej: presionar Enter 10 veces para omitir sección completa)

**Solución diseñada:**
- En sección "Información complementaria", permitir omitir toda la sección con una sola opción
- Campo vacío = omitido automáticamente

---

### 💡 ISSUE #4: No hay validación de coordenadas en tiempo real

**Severidad:** MEDIA  
**Estado:** DISEÑADO — Pendiente implementación

**Descripción:**
- Usuario puede ingresar coordenadas fuera de rango sin advertencia
- Error se detecta solo al generar archivos

**Solución diseñada:**
- Validación inmediata después de ingresar lat/long
- Mensaje con rangos válidos y opción de reintentar

---

## MEJORAS DE USABILIDAD IMPLEMENTADAS

### ✅ Separación obligatorio/opcional explícita
Cada sección indica claramente qué campos son obligatorios vs opcionales.

### ✅ Ejemplos contextuales
Campos de coordenadas y otros datos técnicos incluyen ejemplos de formato válido.

### ✅ Explicaciones inline
Azimut, LAC, Tipo de interacción incluyen explicaciones breves o ejemplos.

### ✅ Navegación adaptativa
Menú CRUD deshabilita opciones no válidas (ej: Listar cuando no hay registros).

### ✅ Advertencias de pérdida de datos
Opción "Volver" muestra cuántos registros se perderán.

### ✅ Confirmaciones en puntos críticos
S/N antes de guardar, generar, o acciones destructivas.

### ✅ Sin tecla Enter como atajo
Eliminado `Enter=default` para evitar errores involuntarios.

### ✅ Campo vacío = omitir
Campos opcionales no requieren tecla especial para omitir.

### ✅ Contador visible
Usuario siempre sabe cuántos registros tiene ingresados.

### ✅ Flujo no destructivo de generación
Generar archivos NO elimina los registros (usuario puede generar múltiples veces con diferentes nombres).

---

## NOTAS DE IMPLEMENTACIÓN

### 1. Estado persistente del CRUD

**Estructura de datos requerida:**

```python
registros = [
    {
        'nombre': 'Cafetal La Florida N 1',
        'latitud': 13.65644,
        'longitud': -89.27278,
        'azimut': 230,
        'direccion': 'km 12 1/2...',
        'tel': '61090192',
        'alias': 'chepe',
        # ... resto de campos
    },
    # ... más registros
]

modo_activo = 'antenas'  # o 'puntos'
```

### 2. Validación de coordenadas

**Rangos válidos para El Salvador:**
- Latitud: 13.0 a 14.5
- Longitud: -90.1 a -87.7 (siempre negativa)

**Validación de azimut:**
- Rango: 0 a 359
- Solo aplica para modo "antenas"

### 3. Generación de nombre sugerido

**Prioridad de elementos:**
1. Si existe `tel` + `alias`: `{tel}_{alias}`
2. Si existe solo `tel`: `{tel}_manual`
3. Si existe solo `alias`: `antenas_{alias}`
4. Si no existe ninguno: `antenas_manual` o `puntos_manual`

### 4. Confirmación de salida

**Cuando opción S (Salir del programa):**

```python
if len(registros) > 0:
    print(f"⚠️ Tiene {len(registros)} registros sin generar.")
    print("¿Confirma que desea salir? (S=Sí salir, N=Volver al menú):")
    # ... lógica de confirmación
```

### 5. Eliminación de registros

**Flujo opción E (Eliminar):**
1. Mostrar Pantalla #6 (lista completa)
2. Solicitar número de registro a eliminar
3. Confirmar eliminación
4. Volver a Pantalla #4

---

## CRITERIOS DE ÉXITO

### Usabilidad
- [ ] Usuario sin capacitación puede agregar puntos siguiendo solo las instrucciones en pantalla
- [ ] Usuario puede corregir datos antes de guardar (S/N/C)
- [ ] Usuario puede generar archivos múltiples veces sin perder registros
- [ ] Usuario puede salir del programa sin cerrar terminal

### Técnico
- [ ] Validaciones de coordenadas funcionan correctamente
- [ ] Archivos KML/KMZ se generan con coordenadas válidas
- [ ] Estado CRUD persiste durante toda la sesión
- [ ] Contador de registros se actualiza dinámicamente

### Funcional
- [ ] Modo "Antenas" solicita azimut, modo "Puntos" no
- [ ] Campos vacíos se omiten automáticamente
- [ ] Nombre sugerido se genera según datos disponibles
- [ ] Lista de registros muestra columnas relevantes según modo
- [ ] Generación de archivos NO destruye registros ingresados

---

## BLOQUE DE RELEVO — PRÓXIMO CHAT

```
=== RELEVO — DISEÑO DE USABILIDAD MODO 3 ===

FASE ACTUAL: Diseño COMPLETO de los 3 modos

ESTADO:
✅ Modo 1: 27 pantallas diseñadas (DISENO_FLUJO_COMPLETO_MODO1.md)
✅ Modo 2: 3 pantallas específicas + reutilización (DISENO_FLUJO_COMPLETO_MODO2.md)
✅ Modo 3: 8 pantallas diseñadas (DISENO_FLUJO_COMPLETO_MODO3.md)
✅ Diagnóstico general: DIAGNOSTICO_USABILIDAD_FASE_A.md

TOTAL PANTALLAS ÚNICAS DISEÑADAS: 38

PENDIENTE:
⏳ Ejecutar prueba guiada completa Tony+Claude para validar diseños
⏳ Priorizar P0/P1/P2 para implementación
⏳ Corregir Issues conocidos (filtros Modo 2, salida Modo 3)
⏳ Implementar mejoras de usabilidad en QC Wizard (Modo 1 y 2)
⏳ Implementar capa interpretativa en HTML (P4 del diagnóstico)

DOCUMENTOS GENERADOS:
📄 DIAGNOSTICO_USABILIDAD_FASE_A.md (diagnóstico preliminar)
📄 DISENO_FLUJO_COMPLETO_MODO1.md (27 pantallas)
📄 DISENO_FLUJO_COMPLETO_MODO2.md (3 específicas + referencias)
📄 DISENO_FLUJO_COMPLETO_MODO3.md (8 pantallas + validaciones)

PRÓXIMA ACCIÓN:
Opción A: Prueba guiada completa de un modo (validar diseño con flujo real)
Opción B: Priorización P0/P1/P2 de pantallas a implementar
Opción C: Implementar correcciones de Issues conocidos
Opción D: Comenzar implementación de mejoras (QC Wizard o HTML)

PROTOCOLO DE RETOMA:
Tony, pega:
1. Este documento (DISENO_FLUJO_COMPLETO_MODO3.md) + otros 3 docs de diseño
2. git status + git log --oneline -5
3. Di: "Vamos a [prueba guiada / priorización / implementación / etc.]"

ISSUES CRÍTICOS PENDIENTES:
🐛 Modo 2 Issue #1: Filtros de rango de horas no funcionan
🔴 Modo 2 Issue #2: Sistema aborta sin recuperación cuando filtro falla
🐛 Modo 3 Issue #1: No hay opción para salir del programa
🔴 Modo 3 Issue #2: Opción Volver es destructiva sin confirmación
⚠️ Modo 3 Issue #3: Campos opcionales solicitan input innecesariamente
💡 Modo 3 Issue #4: No hay validación de coordenadas en tiempo real

PRINCIPIOS APLICADOS EN TODOS LOS DISEÑOS:
✅ Encabezados visuales consistentes (═══)
✅ Separación obligatorio/opcional explícita
✅ Ejemplos contextuales en campos técnicos
✅ Sin tecla Enter como atajo (evita errores involuntarios)
✅ Campo vacío = omitir (sin teclas especiales)
✅ Confirmaciones S/N en puntos críticos
✅ Navegación A/C clara en todas las pantallas
✅ Branding: "Desarrollado por Omar Arias (Tony Zero)"

==========================================
```

---

*Documento generado por consenso entre Tony (Omar Arias) y Claude Sonnet 4.5. Abril 2026.*
