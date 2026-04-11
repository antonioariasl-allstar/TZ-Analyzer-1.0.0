# DISEÑO COMPLETO — FLUJO DE USABILIDAD MODO 1

**Proyecto:** TZ Analyzer v1.0.0  
**Fecha:** 10 de abril de 2026  
**Diseñado por:** Tony (Omar Arias) + Claude Sonnet 4.5  
**Alcance:** Modo 1 únicamente (Procesar bitácora completa)  
**Estado:** DISEÑO COMPLETO — Pendiente implementación

---

## ⚠️ ALCANCE DE ESTE DOCUMENTO

Este documento contiene el diseño completo del flujo de usabilidad ÚNICAMENTE para el **Modo 1: Procesar bitácora completa** del menú principal de TZ Analyzer.

**PENDIENTE DE DISEÑAR:**
- Modo 2: Procesar bitácora filtrada por tiempo
- Modo 3: Ingresar antenas manualmente (sin bitácora)

Estos modos se diseñarán en sesiones posteriores siguiendo los mismos principios establecidos aquí.

---

## RESUMEN EJECUTIVO

| Métrica | Valor |
|---------|-------|
| Pantallas diseñadas | 27 |
| Campos esenciales | 10 |
| Campos opcionales | 4 |
| Información complementaria | 3 (Alias, Usuario, Abonado) |
| Navegación bidireccional | Hasta confirmación final (Pantalla #24) |
| Navegación unidireccional | Post-confirmación (Pantallas #25-27) |

---

## PRINCIPIOS DE DISEÑO APLICADOS

### 1. Encabezado visual consistente
Todas las pantallas usan formato con separadores `═══` para claridad visual.

### 2. Navegación por zonas
- **Zona 1 (Pantallas #1-24):** Navegación completa S/A/C
- **Zona 2 (Pantallas #25-27):** Solo C (cancelar) — punto de no retorno

### 3. Confirmación por campo
Cada campo del QC Wizard muestra vista previa de datos + validación antes de avanzar.

### 4. Lenguaje técnico-profesional
Tono forense, contexto operativo, explicación clara de para qué sirve cada dato.

### 5. Equivalencia consola ↔ GUI
Cada opción (S/A/C/N/R) = 1 botón futuro en interfaz gráfica.

### 6. Branding
Crédito visible: "Desarrollado por Omar Arias (Tony Zero)"

---

## MAPA DEL FLUJO COMPLETO

```
[#1] Menú inicial
  ↓
[#2] Selector de colores
  ↓
[#3] Pre-selector de archivo (nuevo)
  ↓
[Diálogo OS - selección de archivo]
  ↓
[#4] Selector de hoja Excel
  ↓
[#5] Vista previa de columnas detectadas
  ↓
[#6-15] Mapeo de campos ESENCIALES (10 campos con confirmación individual)
  ↓
[#16-19] Mapeo de campos OPCIONALES (4 campos con confirmación individual)
  ↓
[#20-22] Información complementaria (Alias, Usuario, Abonado)
  ↓
[#23] Resumen de mapeo + Vista previa de datos
  ↓
[#24] Confirmación final (S/N/R/A/C) ← PUNTO DE NO RETORNO
  ↓
🔒 ZONA SIN RETORNO
  ↓
[#25] Tipo de bitácora (I/T/Enter/C)
  ↓
[#26] Top de antenas y contactos
  ↓
[#27] Nombre base de archivos
  ↓
[Generación de archivos...]
```

---

## PANTALLAS DETALLADAS

---

### PANTALLA #1: Menú inicial

```
═══════════════════════════════════════════════════════════════
              T Z   A N A L Y Z E R
       Bitácoras → KML/KMZ + Informe HTML
          Desarrollado por Omar Arias (Tony Zero)
═══════════════════════════════════════════════════════════════

Seleccione el modo de procesamiento:

[1] Procesar bitácora completa
    → Genera informe HTML + mapa KML/KMZ con todos los registros
    → Ideal para análisis forense completo de un caso

[2] Procesar bitácora filtrada por tiempo
    → Analiza período específico: día, rango de días o rango de horas
    → Útil para enfocar en ventanas temporales de interés

[3] Ingresar antenas manualmente (sin bitácora)
    → Crea archivo KML desde coordenadas GPS directas
    → Modo avanzado para ploteo rápido de ubicaciones

Opción (1/2/3, Enter=1):
```

**Navegación:** Solo avanza (sin A/C — es pantalla inicial)  
**Botones GUI:** [Opción 1] [Opción 2] [Opción 3] [Salir]

---

### PANTALLA #2: Selector de colores

```
═══════════════════════════════════════════════════════════════
  SELECCIÓN DE COLOR PARA VISUALIZACIÓN EN GOOGLE EARTH
═══════════════════════════════════════════════════════════════

💡 RECOMENDACIÓN: Si se procesan múltiples bitácoras para un mismo caso,
   debería usarse un color diferente para cada una. Esto facilitará que
   se distingan cuando se visualicen de forma simultánea en Google Earth.

Colores disponibles:

  [0] Verde neón (predeterminado)    [21] Azul dodger         [41] Cian A200
  [1] Magenta                        [22] Verde puro          [42] Verde azulado
  [2] Cian                           [23] Carmesí             [43] Verde A400
  [3] Amarillo                       [24] Púrpura neón        [44] Verde lima A700
  [4] Rojo intenso                   [25] Rojo puro           [45] Verde neón
  [5] Azul fuerte                    [26] Rojo cereza         [46] Lima A700
  [6] Verde intenso                  [27] Rojo coral          [47] Amarillo A400
  [7] Naranja                        [28] Fucsia vibrante     [48] Ámbar A700
  [8] Morado                         [29] Rosa A400           [49] Naranja fuerte
  [9] Rosa                           [30] Magenta oscuro      [50] Naranja oscuro
  [10] Lima                          [31] Índigo A700         [51] Naranja rojizo
  [11] Aqua                          [32] Índigo A400         [52] Mandarina
  [12] Ámbar                         [33] Azul A700           [53] Anaranjado suave
  [13] Azul eléctrico                [34] Azul medio          [54] Diente de león
  [14] Chartreuse                    [35] Azul cielo          [55] Ámbar 500
  [15] Verde primavera               [36] Azul claro          [56] Amarillo neón
  [16] Rosa fuerte                   [37] Azul A400           [57] Púrpura A400
  [17] Cielo profundo                [38] Azul A700 brillante [58] Púrpura profundo
  [18] Oro                           [39] Turquesa            [59] Morado A400
  [19] Rojo anaranjado               [40] Cian profundo       [60] Violeta claro
  [20] Violeta

Ingrese número (0-60) o código hexadecimal (A=Atrás, C=Cancelar, Enter=0):
```

**Navegación:** A=Atrás (vuelve a menú), C=Cancelar  
**Botones GUI:** Grilla de 60 colores + [Campo HEX] + [← Atrás] + [✕ Cancelar]

---

### PANTALLA #3: Pre-selector de archivo

```
═══════════════════════════════════════════════════════════════
  SELECCIÓN DE ARCHIVO DE BITÁCORA
═══════════════════════════════════════════════════════════════

A continuación se abrirá el explorador de archivos del sistema para
seleccionar el archivo Excel que contiene la bitácora telefónica.

Formatos soportados: .xlsx, .xls, .xlsm

El archivo debe contener columnas con datos de llamadas/mensajes,
coordenadas GPS, fechas, horas y números de contacto.

Opción (E=Examinar, A=Atrás, C=Cancelar):
```

**Navegación:** E=Abrir diálogo, A=Atrás (colores), C=Cancelar  
**Botones GUI:** [📁 Examinar...] [← Atrás] [✕ Cancelar]

---

### PANTALLA #4: Selector de hoja Excel

```
═══════════════════════════════════════════════════════════════
  SELECCIÓN DE HOJA DE TRABAJO
═══════════════════════════════════════════════════════════════

Archivo seleccionado: bitacora_test.tsv.xlsx

Hojas disponibles en el archivo:
  [1] CASO_860766049463800_PROCESADA
  [2] segunda

Seleccione la hoja que contiene la bitácora telefónica a procesar.

Hoja (1-2, A=Atrás, C=Cancelar, Enter=1):
```

**Confirmación post-selección:**
```
✓ Hoja seleccionada: CASO_860766049463800_PROCESADA

Cargando datos...
```

**Navegación:** A=Atrás (pre-selector), C=Cancelar  
**Botones GUI:** Dropdown/Lista + [Continuar] [← Atrás] [✕ Cancelar]

---

### PANTALLA #5: Vista previa de columnas detectadas

```
═══════════════════════════════════════════════════════════════
  COLUMNAS DETECTADAS EN LA BITÁCORA
═══════════════════════════════════════════════════════════════

Archivo: bitacora_test.tsv.xlsx
Hoja: CASO_860766049463800_PROCESADA
Registros cargados: 50

Columnas disponibles para mapeo:

  [1] tipo_llamada       [8] duracion_seg         [15] latitud_inicial
  [2] numero_origen      [9] cod_celda_inicial    [16] azimut_inicial
  [3] imei_origen       [10] ubicacion_inicio     [17] longitud_final
  [4] numero_destino    [11] cod_celda_final      [18] latitud_final
  [5] fecha_inicial     [12] ubicacion_final      [19] azimut_final
  [6] hora_inicial      [13] imsi                 [20] fecha
  [7] fecha_hora_final  [14] longitud_inicial     [21] hora

─────────────────────────────────────────────────────────────────

A continuación deberá mapear cada campo requerido seleccionando el
número de columna correspondiente. El sistema validará cada selección
antes de continuar al siguiente campo.

Opción (S=Comenzar mapeo, A=Atrás, C=Cancelar):
```

**Navegación:** S=Comenzar, A=Atrás (selector hoja), C=Cancelar  
**Botones GUI:** [▶ Comenzar mapeo] [← Atrás] [✕ Cancelar]

---

### PANTALLAS #6-15: Mapeo de campos ESENCIALES

**Estructura común para todos los campos esenciales:**

```
═══════════════════════════════════════════════════════════════
  ASISTENTE DE MAPEO DE CAMPOS (N/10)
═══════════════════════════════════════════════════════════════

[ICONO] NOMBRE DEL CAMPO

Descripción de qué contiene este campo y para qué sirve.

Formatos válidos/esperados: [ejemplos]

Columnas disponibles:
  [lista de columnas en 3 columnas]

Columna (?=Ver columnas nuevamente, A=Atrás, C=Cancelar):
```

**Después de ingresar número:**
```
Vista previa de datos en '[nombre_columna]':
  [ejemplo 1]
  [ejemplo 2]
  [ejemplo 3]

✓ Formato detectado: [descripción]
[Validaciones adicionales si aplican]

¿Es correcta esta columna? (S=Sí, N=Elegir otra, A=Atrás, C=Cancelar):
```

---

#### PANTALLA #6: Campo FECHA (1/10)
- **Icono:** 📅
- **Descripción:** Fecha en que ocurrió el evento telefónico
- **Formatos:** DD/MM/YYYY, YYYY-MM-DD, DD/MM/YY
- **Validación:** Formato de fecha válido

---

#### PANTALLA #7: Campo HORA (2/10)
- **Icono:** 🕐
- **Descripción:** Hora en que ocurrió el evento
- **Formatos:** HH:MM:SS, HH:MM, fecha/hora completo
- **Validación:** Advertencia si contiene fecha+hora

---

#### PANTALLA #8: Campo TELÉFONO/ORIGEN (3/10)
- **Icono:** 📞
- **Descripción:** Número telefónico investigado o de origen
- **Formatos:** 50370001234, +50370001234, 70001234
- **Validación:** Consistencia (mismo número en todos los registros)

---

#### PANTALLA #9: Campo IMEI (4/10)
- **Icono:** 📱
- **Descripción:** IMEI del dispositivo móvil investigado
- **Formatos:** 860766049463800 (15 dígitos)
- **Validación:** Luhn check, consistencia

---

#### PANTALLA #10: Campo TIPO DE INTERACCIÓN (5/10)
- **Icono:** 💬
- **Descripción:** Tipo de evento (VOZ, SMS, DATOS)
- **Formatos:** VOZ, SMS, DATOS, LLAMADA, MENSAJE
- **Validación:** Tipos encontrados en los datos

---

#### PANTALLA #11: Campo CONTACTO/DESTINO (6/10)
- **Icono:** 👤
- **Descripción:** Número con quien se comunicó el investigado
- **Formatos:** 50371112233, +50371112233, 71112233
- **Validación:** Conteo de contactos únicos

---

#### PANTALLA #12: Campo LATITUD (7/10)
- **Icono:** 🌍
- **Descripción:** Latitud geográfica (posición Norte-Sur)
- **Formatos:** -90.0 a +90.0, El Salvador: 13.0 a 14.5
- **Validación:** Rango válido, % de coordenadas válidas

---

#### PANTALLA #13: Campo LONGITUD (8/10)
- **Icono:** 🌍
- **Descripción:** Longitud geográfica (posición Este-Oeste)
- **Formatos:** -180.0 a +180.0, El Salvador: -90.1 a -87.7
- **Validación:** Rango válido, correspondencia con latitud

---

#### PANTALLA #14: Campo AZIMUT (9/10)
- **Icono:** 📡
- **Descripción:** Orientación direccional de la antena en grados
- **Formatos:** 0 a 360 grados (0°=Norte, 90°=Este, 180°=Sur, 270°=Oeste)
- **Validación:** Rango válido 0-360

---

#### PANTALLA #15: Campo ANTENA/CELDA (10/10)
- **Icono:** 📶
- **Descripción:** Código de antena o celda telefónica
- **Formatos:** 39512-0473-3, 503-01-1234, BTS_12345
- **Validación:** Conteo de antenas únicas, correspondencia con GPS

---

### PANTALLAS #16-19: Mapeo de campos OPCIONALES

**Estructura común:** Similar a esenciales, pero con `Enter=Omitir`

---

#### PANTALLA #16: Campo CELDA (Opcional 1/4)
- **Icono:** 📍
- **Descripción:** Nombre descriptivo de la celda telefónica
- **Ejemplos:** "San Salvador Centro", "Santa Tecla Norte"
- **Omisible:** Sí

---

#### PANTALLA #17: Campo DIRECCIÓN (Opcional 2/4)
- **Icono:** 🏠
- **Descripción:** Dirección física de la antena
- **Ejemplos:** "Final 12 calle oriente y 15 ave Sur", "Km 12 1/2..."
- **Omisible:** Sí
- **Nota:** Puede ser la misma columna que CELDA si datos están combinados

---

#### PANTALLA #18: Campo IMSI (Opcional 3/4)
- **Icono:** 🔢
- **Descripción:** IMSI de la tarjeta SIM
- **Formatos:** 15 dígitos (706040000000000)
- **Omisible:** Sí

---

#### PANTALLA #19: Campo DURACIÓN (Opcional 4/4)
- **Icono:** ⏱️
- **Descripción:** Duración de la llamada o evento
- **Formatos:** Segundos (305), minutos (5:05), HH:MM:SS
- **Omisible:** Sí
- **Validación:** Rango, duración promedio

---

### PANTALLAS #20-22: Información complementaria

---

#### PANTALLA #20: Alias (1/3)

```
═══════════════════════════════════════════════════════════════
  INFORMACIÓN COMPLEMENTARIA DEL CASO (1/3)
═══════════════════════════════════════════════════════════════

🏷️ ALIAS DEL INVESTIGADO

Ingrese un alias o apodo para identificar al sujeto investigado.

Este valor aparecerá en:
  • Informe HTML (sección de identificación)
  • Etiquetas de puntos en el mapa de Google Earth (burbujas emergentes)

Ejemplos: "El Chele", "Sospechoso A", "Investigado 001"

💡 NOTA: Facilita la lectura sin exponer datos sensibles.

Alias (A=Atrás, C=Cancelar, Enter=Omitir):
```

---

#### PANTALLA #21: Nombre de usuario (2/3)

```
═══════════════════════════════════════════════════════════════
  INFORMACIÓN COMPLEMENTARIA DEL CASO (2/3)
═══════════════════════════════════════════════════════════════

👤 NOMBRE DE USUARIO

Ingrese el nombre completo del sujeto investigado o usuario registrado
de la línea telefónica.

Este campo complementa la identificación en el informe HTML.

Ejemplos: "Antonio Ayala", "Juan Pérez García", "María López"

💡 NOTA: Dato opcional que aparece en la sección de metadatos del informe.

Nombre de usuario (A=Atrás, C=Cancelar, Enter=Omitir):
```

---

#### PANTALLA #22: Abonado (3/3)

```
═══════════════════════════════════════════════════════════════
  INFORMACIÓN COMPLEMENTARIA DEL CASO (3/3)
═══════════════════════════════════════════════════════════════

📋 NOMBRE DEL ABONADO

Ingrese el nombre de la persona registrada como titular de la línea
telefónica ante la operadora (abonado oficial).

Este campo puede diferir del usuario real si la línea está a nombre
de un tercero.

Ejemplos: "Juana Hernández de Ayala", "Empresa Telecomunicaciones SA"

💡 NOTA: Información relevante para identificar titularidad de la línea.

Nombre del abonado (A=Atrás, C=Cancelar, Enter=Omitir):
```

---

### PANTALLA #23: Resumen de mapeo y vista previa

```
═══════════════════════════════════════════════════════════════
  RESUMEN DEL MAPEO DE CAMPOS
═══════════════════════════════════════════════════════════════

Archivo: bitacora_test.tsv.xlsx
Hoja: CASO_860766049463800_PROCESADA
Registros: 50

─────────────────────────────────────────────────────────────────
  CAMPOS ESENCIALES MAPEADOS
─────────────────────────────────────────────────────────────────
  fecha        ← columna [5] fecha_inicial
  hora         ← columna [6] hora_inicial
  tel          ← columna [2] numero_origen
  imei         ← columna [3] imei_origen
  interaccion  ← columna [1] tipo_llamada
  contacto     ← columna [4] numero_destino
  lat          ← columna [15] latitud_inicial
  long         ← columna [14] longitud_inicial
  azimut       ← columna [16] azimut_inicial
  antena       ← columna [9] cod_celda_inicial

─────────────────────────────────────────────────────────────────
  CAMPOS OPCIONALES MAPEADOS
─────────────────────────────────────────────────────────────────
  celda        ← columna [10] ubicacion_inicio
  direccion    ← columna [10] ubicacion_inicio
  imsi         ← columna [13] imsi
  duracion     ← columna [8] duracion_seg

─────────────────────────────────────────────────────────────────
  INFORMACIÓN COMPLEMENTARIA
─────────────────────────────────────────────────────────────────
  Alias:        toño
  Usuario:      Antonio Ayala
  Abonado:      Juana Hernández de Ayala

─────────────────────────────────────────────────────────────────
  VISTA PREVIA (primeras 3 filas)
─────────────────────────────────────────────────────────────────

       fecha                hora       tel  interaccion  contacto   lat       long      antena
0  2020-01-01  2020-01-01 02:02:00  61090192  VOZ       77665544  13.6929  -89.1872  39512 0473 3
1  2020-01-01  2020-01-01 04:01:00  61090192  SMS       78889999  13.6929  -89.1872  39512 0473 9
2  2020-01-01  2020-01-01 05:08:00  61090192  VOZ       79990000  13.6768  -89.2795  39512 0404 7


Opciones (S=Confirmar y continuar, N=Remapear todo, R=Remapear campo específico, 
          A=Atrás, C=Cancelar):
```

**Navegación:** S/N/R/A/C todas disponibles  
**Botones GUI:** [✓ Confirmar] [↻ Remapear todo] [🔧 Remapear campo] [← Atrás] [✕ Cancelar]

---

### PANTALLA #24: Confirmación final (PUNTO DE NO RETORNO)

```
═══════════════════════════════════════════════════════════════
  CONFIRMACIÓN FINAL DEL MAPEO
═══════════════════════════════════════════════════════════════

⚠️  IMPORTANTE: Una vez confirmado, el sistema procesará los datos
    y no podrá retroceder para modificar el mapeo.

Resumen:
  • Archivo: bitacora_test.tsv.xlsx
  • Hoja: CASO_860766049463800_PROCESADA
  • Registros a procesar: 50
  • Campos esenciales: 10/10 mapeados
  • Campos opcionales: 4/4 mapeados
  • Coordenadas válidas: 50/50 (100%)

Alias configurado: toño
Usuario: Antonio Ayala
Abonado: Juana Hernández de Ayala

─────────────────────────────────────────────────────────────────

¿Confirma el mapeo y desea continuar con el procesamiento?

Opciones disponibles:
  S = Sí, confirmar y procesar datos
  N = No, volver a mapear todos los campos desde el inicio
  R = Remapear solo un campo específico
  A = Atrás (volver a vista previa)
  C = Cancelar (volver al menú principal)

Opción (S/N/R/A/C):
```

**Si elige S:**
```
✓ Mapeo confirmado. Procesando datos...

🔒 A partir de este punto no se puede retroceder.
```

**Navegación:** S/N/R/A/C — última pantalla con navegación completa  
**Botones GUI:** [✓ SÍ, PROCESAR] [↻ Remapear todo] [🔧 Campo específico] [← Atrás] [✕ Cancelar]

---

## 🔒 ZONA SIN RETORNO (POST-CONFIRMACIÓN)

A partir de aquí, el usuario solo puede **cancelar** (no retroceder).

---

### PANTALLA #25: Tipo de bitácora

```
═══════════════════════════════════════════════════════════════
  CONFIGURACIÓN DE SALIDA
═══════════════════════════════════════════════════════════════

🔒 Datos procesados correctamente. A partir de aquí solo puede cancelar
   la generación de archivos (no retroceder al mapeo).

─────────────────────────────────────────────────────────────────

📋 TIPO DE BITÁCORA PROCESADA

Indique si la bitácora que procesó corresponde a un seguimiento por
número telefónico o por IMEI del dispositivo.

Esto determina cómo se nombrarán los archivos de salida:
  • IMEI → IMEI_860766049463800_toño_2026-04-10_18-45
  • Teléfono → TEL_61090192_toño_2026-04-10_18-45

💡 Datos detectados en la bitácora:
   Teléfono: 61090192
   IMEI: 860766049463800

Opciones:
  I = Bitácora por IMEI
  T = Bitácora por número telefónico
  Enter = Dejar que TZ Analyzer decida automáticamente
  C = Cancelar generación de archivos

Opción (I/T/Enter/C):
```

**Confirmación:**
```
✓ Tipo de bitácora establecido: IMEI

Los archivos se nombrarán usando el IMEI detectado.
```

**Navegación:** Solo I/T/Enter/C (sin A=Atrás)  
**Botones GUI:** [IMEI] [Teléfono] [Automático] [✕ Cancelar]

---

### PANTALLA #26: Top de antenas y contactos

```
═══════════════════════════════════════════════════════════════
  CONFIGURACIÓN DE ANÁLISIS
═══════════════════════════════════════════════════════════════

📊 TOP DE ANTENAS Y CONTACTOS

Defina cuántas antenas y contactos más frecuentes desea incluir en el
informe HTML y en el análisis estadístico.

─────────────────────────────────────────────────────────────────

🗼 TOP DE ANTENAS MÁS ACTIVADAS

¿Cuántas antenas desea incluir en el análisis de ubicaciones frecuentes?

Valores comunes: 3-10 antenas (0 = incluir todas sin límite)

Top de antenas (Enter=10, C=Cancelar): 4
```

**Después de ingresar antenas:**
```
✓ Top de antenas configurado: 4

─────────────────────────────────────────────────────────────────

👥 TOP DE CONTACTOS MÁS FRECUENTES

¿Cuántos contactos desea incluir en el análisis de comunicaciones?

Puede ingresar un número, 0 para todos, o escribir 'mismo' para usar
el mismo valor que antenas (4).

Top de contactos (Enter=10, 'mismo'=copiar antenas, C=Cancelar): 8
```

**Confirmación:**
```
✓ Top de contactos configurado: 8

El informe incluirá las 4 antenas más activadas y los 8 contactos
más frecuentes.
```

**Navegación:** Solo C=Cancelar (sin A=Atrás)  
**Botones GUI:** Campos numéricos + [Continuar] [✕ Cancelar]

---

### PANTALLA #27: Nombre base de archivos de salida

```
═══════════════════════════════════════════════════════════════
  NOMBRE DE ARCHIVOS DE SALIDA
═══════════════════════════════════════════════════════════════

📁 CONFIGURACIÓN FINAL

El sistema generará los siguientes archivos en la carpeta de salida:

Carpeta sugerida:
  📁 IMEI_860766049463800_toño_2026-04-10_18-45

Archivos a generar:
  📄 IMEI_860766049463800_toño_2026-04-10_18-45_informe.html
  🗺️ IMEI_860766049463800_toño_2026-04-10_18-45_mapeo.kmz
  🔐 IMEI_860766049463800_toño_2026-04-10_18-45_hashes.txt
  ⚠️ IMEI_860766049463800_toño_2026-04-10_18-45_errores.txt

─────────────────────────────────────────────────────────────────

Si desea usar un nombre personalizado en lugar del sugerido por el
sistema, ingréselo ahora (solo el nombre base, sin extensión).

💡 NOTA: 
   • Nombre sugerido: incluye fecha y hora automáticamente
   • Nombre personalizado: NO incluye fecha ni hora

Nombre base (Enter=usar sugerido, C=Cancelar):
```

**Si presiona Enter:**
```
✓ Usando nombre sugerido con fecha y hora

Carpeta de destino: C:\Users\Omar Arias\Downloads

Generando archivos...
```

**Si ingresa nombre personalizado (ej: "caso_prueba"):**
```
✓ Nombre base personalizado: caso_prueba

Los archivos se nombrarán:
  - caso_prueba_informe.html
  - caso_prueba_mapeo.kmz
  - caso_prueba_hashes.txt
  - caso_prueba_errores.txt

Carpeta de destino: C:\Users\Omar Arias\Downloads

Generando archivos...
```

**Navegación:** Solo Enter/C (sin A=Atrás)  
**Botones GUI:** Campo de texto + [Usar sugerido] [Generar] [✕ Cancelar]

---

## NOTAS DE IMPLEMENTACIÓN

### Navegación bidireccional (Pantallas #1-24)

**Implementación técnica:**
- Requiere **estado persistente** del mapeo:
  ```python
  mapeo_state = {
      'fecha': 5,
      'hora': 6,
      'tel': 2,
      # ... todos los campos
  }
  ```
- Al presionar "A" → recupera valor anterior del campo
- Al presionar "S" → guarda valor y avanza
- Al presionar "N" en confirmación → limpia todo el estado y reinicia

### Validaciones por campo

Cada campo debe implementar:
1. **Validación de formato** (numérico, fecha, texto)
2. **Validación de rango** (lat/long, azimut)
3. **Validación de consistencia** (mismo tel/IMEI en todos los registros)
4. **Detección de advertencias** (columna con datos combinados)

### Vista previa de datos

- Mostrar **3 filas** de ejemplo de la columna seleccionada
- Formato: valores reales sin procesar
- Agregar validaciones contextuales (ej: "Todos los registros tienen el mismo valor")

### Punto de no retorno (Pantalla #24)

**Técnicamente:**
- Al confirmar "S" → sistema ejecuta:
  1. Aplicar mapeo al DataFrame
  2. Normalizar datos
  3. Calcular métricas
  4. Preparar estructuras para generación

- Una vez hecho esto, retroceder requeriría **deshacer todo el procesamiento**
- Por eso solo queda "C=Cancelar" (abortar generación)

---

## EQUIVALENCIAS CONSOLA ↔ GUI

| Consola | GUI | Función |
|---------|-----|---------|
| `S` | [✓ Sí] / [Confirmar] / [Continuar] | Afirmativo, avanzar |
| `N` | [Elegir otra] / [Remapear todo] | Negativo, corregir |
| `A` | [← Atrás] | Retroceder pantalla |
| `C` | [✕ Cancelar] | Cancelar/Salir |
| `R` | [🔧 Remapear campo] | Remapeo selectivo |
| `?` | [? Ver columnas] | Ayuda contextual |
| `Enter` | Click en campo predeterminado | Aceptar default |
| Número | Dropdown / Lista seleccionable | Elegir opción |
| Texto libre | Campo de texto | Entrada manual |

---

## PENDIENTES PARA PRÓXIMAS SESIONES

### 1. Revisión de campos "esenciales"

**Pregunta de Tony:** ¿Pueden algunos "esenciales" degradarse a "opcionales"?

**Candidatos a revisar:**
- **Azimut:** Si falta → no se genera diagrama direccional, pero el resto funciona
- **IMSI:** Identificación complementaria, no crítica para análisis de ubicación
- **Duración:** Solo afecta análisis de patrones de llamadas

**Acción:** Evaluar qué análisis se pueden generar sin cada campo.

---

### 2. Diseño de Modo 2 (Procesar por tiempo)

**Pantallas adicionales esperadas:**
- Selector de tipo de filtro (día / rango de días / rango de horas)
- Calendario o input de fechas
- Validación de rango temporal
- Confirmación de registros filtrados

**Reutilizable de Modo 1:**
- Todo el QC Wizard (pantallas #6-24)
- Configuración de salida (pantallas #25-27)

---

### 3. Diseño de Modo 3 (Ingresar antenas manualmente)

**Pantallas adicionales esperadas:**
- Input de coordenadas GPS manuales
- Tabla/grid para múltiples antenas
- Validación de coordenadas
- Opciones de exportación (solo KML, sin HTML)

**Reutilizable de Modo 1:**
- Selector de colores
- Configuración de nombres de archivo

---

### 4. Priorización P0/P1/P2

**Después de diseñar los 3 modos:**
- Evaluar qué pantallas implementar primero
- P0: Críticas (bloquean uso básico)
- P1: Altas (mejoran usabilidad significativamente)
- P2: Mejoras incrementales

---

## CRITERIOS DE ÉXITO

### Usabilidad
- [ ] Usuario sin capacitación completa el flujo solo leyendo pantallas
- [ ] Cero errores de mapeo por ambigüedad en prompts
- [ ] Tiempo de ejecución ≤ 10% mayor que flujo actual

### Técnico
- [ ] Golden output byte-identical después de implementación
- [ ] Tests completos pasando sin regresiones
- [ ] Código permite navegación bidireccional sin bugs

### Funcional
- [ ] Validaciones detectan errores ANTES de procesar
- [ ] Usuario puede corregir sin reiniciar todo el flujo
- [ ] Textos son consistentes en tono técnico-profesional

---

## BLOQUE DE RELEVO — PRÓXIMO CHAT

```
=== RELEVO — DISEÑO DE USABILIDAD ===

FASE ACTUAL: Diseño Modo 1 COMPLETADO

ESTADO:
✅ 27 pantallas diseñadas con formato consensuado
✅ Navegación bidireccional hasta punto de no retorno
✅ Validaciones por campo con vista previa
✅ Branding aplicado (Omar Arias - Tony Zero)

PENDIENTE:
⏳ Diseñar Modo 2 (Procesar por tiempo)
⏳ Diseñar Modo 3 (Ingresar antenas manualmente)
⏳ Revisar campos "esenciales" vs "opcionales"
⏳ Priorizar P0/P1/P2 para implementación

DOCUMENTOS GENERADOS:
📄 DISENO_FLUJO_COMPLETO_MODO1.md (este archivo)

PRÓXIMA ACCIÓN:
1. Ejecutar Modo 2 del menú principal
2. Capturar flujo completo (screenshots/output)
3. Diseñar pantallas con mismo formato
4. Repetir para Modo 3
5. Consolidar en documento maestro

PROTOCOLO DE RETOMA:
Tony, pega:
1. Este documento (DISENO_FLUJO_COMPLETO_MODO1.md)
2. git status + log
3. Di: "Vamos a diseñar Modo 2" o "Vamos a implementar"

==========================================
```

---

*Documento generado por consenso entre Tony (Omar Arias) y Claude Sonnet 4.5. Abril 2026.*
