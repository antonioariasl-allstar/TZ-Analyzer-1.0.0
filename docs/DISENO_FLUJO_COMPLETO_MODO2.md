# DISEÑO COMPLETO — FLUJO DE USABILIDAD MODO 2

**Proyecto:** TZ Analyzer v1.0.0  
**Fecha:** 10 de abril de 2026  
**Diseñado por:** Tony (Omar Arias) + Claude Sonnet 4.5  
**Alcance:** Modo 2 únicamente (Procesar bitácora filtrada por tiempo)  
**Estado:** DISEÑO COMPLETO — Pendiente implementación

---

## ⚠️ ALCANCE DE ESTE DOCUMENTO

Este documento contiene el diseño completo del flujo de usabilidad ÚNICAMENTE para el **Modo 2: Procesar bitácora filtrada por tiempo** del menú principal de TZ Analyzer.

**DOCUMENTOS RELACIONADOS:**
- Modo 1 (Procesar bitácora completa): `DISENO_FLUJO_COMPLETO_MODO1.md`
- Modo 3 (Ingresar antenas manualmente): Pendiente de diseñar

---

## RESUMEN EJECUTIVO

| Métrica | Valor |
|---------|-------|
| Pantallas totales | 30 |
| Pantallas compartidas con Modo 1 | 24 (#1-24) |
| Pantallas específicas de Modo 2 | 3 (#25-27) |
| Pantallas finales (reutilizan Modo 1) | 3 (#28-30) |
| Navegación bidireccional | Hasta confirmación final (Pantalla #24) |
| Navegación unidireccional | Post-confirmación (Pantallas #25-30) |
| Issues conocidos | 2 (bug filtro horas + aborto sin recuperación) |

---

## PRINCIPIOS DE DISEÑO APLICADOS

### 1. Reutilización de Modo 1
Pantallas #1-24 son idénticas a Modo 1. No se rediseñan, se referencian.

### 2. Diferenciación post-confirmación
Después de la confirmación final (#24), Modo 2 introduce filtrado temporal antes de continuar con el flujo estándar.

### 3. Manejo de errores
Se diseña pantalla de validación (#27) que NO existe actualmente, para evitar pérdida de mapeo cuando el filtro falla.

### 4. Lenguaje técnico-profesional
Tono forense, contexto operativo, explicación clara de cada opción de filtro.

### 5. Equivalencia consola ↔ GUI
Cada opción (S/A/C/N/R) = 1 botón futuro en interfaz gráfica.

### 6. Branding
Crédito visible: "Desarrollado por Omar Arias (Tony Zero)"

---

## MAPA DEL FLUJO COMPLETO

```
[#1-24] Pantallas compartidas con Modo 1 (ver DISENO_FLUJO_COMPLETO_MODO1.md)
  ↓
[#24] Confirmación final (S/N/R/A/C) ← ÚLTIMO PUNTO COMÚN CON MODO 1
  ↓
🔒 PUNTO DE NO RETORNO
  ↓
[#25] ⭐ SELECTOR DE FILTRO TEMPORAL (NUEVO - específico de Modo 2)
  ↓
[#26a-d] ⭐ INPUT DE PARÁMETROS TEMPORALES (4 variantes según filtro elegido)
  ↓
[#27] ⭐ VALIDACIÓN DE RESULTADOS (CRÍTICO - pantalla que falta implementar)
  ↓
[#28-30] Pantallas finales (reutilizan lógica de Modo 1 #25-27)
  ↓
[Generación de archivos...]
```

---

## PANTALLAS COMPARTIDAS CON MODO 1 (#1-24)

**⚠️ IMPORTANTE:** Estas pantallas son **idénticas** entre Modo 1 y Modo 2.

**Ver documento completo:** `DISENO_FLUJO_COMPLETO_MODO1.md`

### Lista de pantallas compartidas:

```
#1   Menú inicial
#2   Selector de colores (60 opciones)
#3   Pre-selector de archivo
     [Diálogo OS] Selección de archivo
#4   Selector de hoja Excel
#5   Vista previa de columnas
#6   Campo FECHA (esencial 1/10)
#7   Campo HORA (esencial 2/10)
#8   Campo TELÉFONO (esencial 3/10)
#9   Campo IMEI (esencial 4/10)
#10  Campo TIPO DE INTERACCIÓN (esencial 5/10)
#11  Campo CONTACTO (esencial 6/10)
#12  Campo LATITUD (esencial 7/10)
#13  Campo LONGITUD (esencial 8/10)
#14  Campo AZIMUT (esencial 9/10)
#15  Campo ANTENA (esencial 10/10)
#16  Campo CELDA (opcional 1/4)
#17  Campo DIRECCIÓN (opcional 2/4)
#18  Campo IMSI (opcional 3/4)
#19  Campo DURACIÓN (opcional 4/4)
#20  Alias (info complementaria 1/3)
#21  Usuario (info complementaria 2/3)
#22  Abonado (info complementaria 3/3)
#23  Resumen de mapeo + Vista previa
#24  Confirmación final (S/N/R/A/C) ← ÚLTIMO PUNTO COMÚN
```

**Para el diseño detallado de estas pantallas, consultar:**  
`docs/DISENO_FLUJO_COMPLETO_MODO1.md`

---

## PANTALLAS ESPECÍFICAS DE MODO 2 (#25-27)

---

### PANTALLA #25: Selector de filtro temporal

```
═══════════════════════════════════════════════════════════════
  CONFIGURACIÓN DE FILTRO TEMPORAL
═══════════════════════════════════════════════════════════════

Seleccione el tipo de filtro a aplicar sobre la bitácora:

[1] Día específico
    → Analiza todos los eventos de una fecha puntual
    → Útil para: día del incidente, día de vigilancia específica

[2] Rango de días
    → Analiza eventos entre dos fechas (inclusive)
    → Útil para: período de investigación, semana específica

[3] Rango de horas en un día específico
    → Analiza solo cierto horario dentro de un día
    → Útil para: momento del hecho, ventana temporal del incidente

[4] Rango de horas (aplicado a todos los días)
    → Analiza mismo horario en todos los días de la bitácora
    → Útil para: actividad nocturna recurrente, patrón horario

[5] Sin filtro (procesar bitácora completa)
    → Analiza todos los registros sin restricción temporal

─────────────────────────────────────────────────────────────────

Opción (1/2/3/4/5, A=Atrás, C=Cancelar):
```

**Navegación:** 1/2/3/4/5/A/C  
**Botones GUI:** [Día] [Rango días] [Horas en día] [Horas global] [Sin filtro] [← Atrás] [✕ Cancelar]

---

### PANTALLA #26a: Día específico

```
═══════════════════════════════════════════════════════════════
  FILTRO: DÍA ESPECÍFICO
═══════════════════════════════════════════════════════════════

📅 FECHA A ANALIZAR

Ingrese la fecha del día que desea analizar.

Se incluirán todos los eventos ocurridos desde las 00:00:00 hasta
las 23:59:59 de la fecha indicada.

Formato esperado: DD/MM/YYYY

Ejemplos: 15/03/2024, 01/01/2020

💡 DATOS DISPONIBLES EN LA BITÁCORA:
   Fecha más antigua: 01/01/2020
   Fecha más reciente: 01/03/2020

─────────────────────────────────────────────────────────────────

Día (DD/MM/YYYY): 01/01/2020
```

**Después de ingresar la fecha:**

```
✓ Fecha ingresada: 01/01/2020

¿Confirma esta fecha? (S=Sí, N=Reingresar, A=Atrás, C=Cancelar):
```

**Navegación:** Input / S/N/A/C  
**Botones GUI:** Campo calendario + [✓ Confirmar] [↻ Reingresar] [← Atrás] [✕ Cancelar]

---

### PANTALLA #26b: Rango de días

```
═══════════════════════════════════════════════════════════════
  FILTRO: RANGO DE DÍAS
═══════════════════════════════════════════════════════════════

📅 PERÍODO A ANALIZAR

Ingrese las fechas de inicio y fin del período que desea analizar.

Se incluirán todos los eventos desde las 00:00:00 del día inicial
hasta las 23:59:59 del día final (ambas fechas inclusive).

Formato esperado: DD/MM/YYYY

💡 DATOS DISPONIBLES EN LA BITÁCORA:
   Fecha más antigua: 01/01/2020
   Fecha más reciente: 01/03/2020

─────────────────────────────────────────────────────────────────

Desde (DD/MM/YYYY): 01/01/2020
Hasta (DD/MM/YYYY): 15/01/2020
```

**Después de ingresar ambas fechas:**

```
✓ Rango ingresado: 01/01/2020 → 15/01/2020
  Duración: 15 días

¿Confirma este rango? (S=Sí, N=Reingresar, A=Atrás, C=Cancelar):
```

**Navegación:** Input / S/N/A/C  
**Botones GUI:** Campos calendario + [✓ Confirmar] [↻ Reingresar] [← Atrás] [✕ Cancelar]

---

### PANTALLA #26c: Rango de horas en un día específico

```
═══════════════════════════════════════════════════════════════
  FILTRO: RANGO DE HORAS EN UN DÍA ESPECÍFICO
═══════════════════════════════════════════════════════════════

🕐 VENTANA TEMPORAL A ANALIZAR

Ingrese el día y el rango horario que desea analizar.

Se incluirán solo los eventos ocurridos dentro del horario
especificado en la fecha indicada.

Formato esperado:
  Día: DD/MM/YYYY
  Hora: HH:MM (formato 24 horas)

💡 DATOS DISPONIBLES EN LA BITÁCORA:
   Fecha más antigua: 01/01/2020
   Fecha más reciente: 01/03/2020

─────────────────────────────────────────────────────────────────

Día (DD/MM/YYYY): 01/01/2020
Hora inicio (HH:MM): 08:00
Hora fin (HH:MM): 18:00
```

**Después de ingresar los datos:**

```
✓ Filtro ingresado: 01/01/2020 de 08:00 a 18:00
  Ventana: 10 horas

¿Confirma este filtro? (S=Sí, N=Reingresar, A=Atrás, C=Cancelar):
```

**Navegación:** Input / S/N/A/C  
**Botones GUI:** Campos fecha+hora + [✓ Confirmar] [↻ Reingresar] [← Atrás] [✕ Cancelar]

---

### PANTALLA #26d: Rango de horas (aplicado a todos los días)

```
═══════════════════════════════════════════════════════════════
  FILTRO: RANGO DE HORAS (APLICADO A TODOS LOS DÍAS)
═══════════════════════════════════════════════════════════════

🕐 HORARIO RECURRENTE A ANALIZAR

Ingrese el rango horario que desea analizar.

Este filtro se aplicará a TODOS los días presentes en la bitácora,
incluyendo solo los eventos ocurridos dentro del horario especificado
sin importar la fecha.

Formato esperado: HH:MM (formato 24 horas)

Ejemplos de uso:
  • Actividad nocturna: 22:00 a 06:00
  • Horario laboral: 08:00 a 17:00
  • Madrugada: 00:00 a 05:00

─────────────────────────────────────────────────────────────────

Hora inicio (HH:MM): 22:00
Hora fin (HH:MM): 06:00
```

**Después de ingresar las horas:**

```
✓ Filtro ingresado: 22:00 → 06:00 (todos los días)
  Nota: Este horario cruza medianoche

¿Confirma este filtro? (S=Sí, N=Reingresar, A=Atrás, C=Cancelar):
```

**Navegación:** Input / S/N/A/C  
**Botones GUI:** Campos hora + [✓ Confirmar] [↻ Reingresar] [← Atrás] [✕ Cancelar]

---

### PANTALLA #27: Validación de resultados

**ESTA ES LA PANTALLA CRÍTICA QUE ACTUALMENTE NO EXISTE.**

---

#### VARIANTE A: Cuando SÍ hay registros (exitosa)

```
═══════════════════════════════════════════════════════════════
  ✓ FILTRO APLICADO EXITOSAMENTE
═══════════════════════════════════════════════════════════════

Filtro aplicado: Día específico → 01/01/2020

Registros originales: 50
Registros tras filtro: 12 (24%)
Coordenadas válidas: 12 (100%)

─────────────────────────────────────────────────────────────────

✓ El filtro produjo datos suficientes para generar el informe.

Presione Enter para continuar...
```

**Navegación:** Solo Enter  
**Botones GUI:** [▶ Continuar]

---

#### VARIANTE B: Cuando NO hay registros (fallida)

```
═══════════════════════════════════════════════════════════════
  ⚠️  FILTRO NO PRODUJO RESULTADOS
═══════════════════════════════════════════════════════════════

Filtro aplicado: Rango de horas en día 01/01/2020: 06:00 → 13:00

Registros originales: 50
Registros tras filtro: 0 (0%)

─────────────────────────────────────────────────────────────────

El filtro seleccionado no coincide con ningún registro de la bitácora.

DATOS DISPONIBLES EN LA BITÁCORA:

  Rango completo de fechas:
    • Fecha más antigua: 01/01/2020
    • Fecha más reciente: 01/03/2020

  Actividad del día 01/01/2020:
    • Primera actividad: 02:02
    • Última actividad: 20:14
    • Total de eventos: 12

─────────────────────────────────────────────────────────────────

Opciones:
  R = Cambiar filtro temporal (mantener mapeo)
  C = Cancelar y volver al menú principal

Opción (R/C):
```

**Navegación:** R / C  
**Botones GUI:** [🔄 Cambiar filtro] [✕ Cancelar]

---

## PANTALLAS FINALES (#28-30)

Estas pantallas reutilizan la lógica de las pantallas finales de Modo 1 (#25-27).

---

### PANTALLA #28: Tipo de bitácora

**Equivalente a:** Modo 1 Pantalla #25

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
  • IMEI → IMEI_860766049463800_alias_2026-04-10_18-45
  • Teléfono → TEL_61090192_alias_2026-04-10_18-45

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

**Navegación:** I/T/Enter/C  
**Botones GUI:** [IMEI] [Teléfono] [Automático] [✕ Cancelar]

**Ver diseño completo:** `DISENO_FLUJO_COMPLETO_MODO1.md` - Pantalla #25

---

### PANTALLA #29: Top de antenas y contactos

**Equivalente a:** Modo 1 Pantalla #26

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

**Navegación:** Input numérico / 'mismo' / Enter / C  
**Botones GUI:** Campos numéricos + [Continuar] [✕ Cancelar]

**Ver diseño completo:** `DISENO_FLUJO_COMPLETO_MODO1.md` - Pantalla #26

---

### PANTALLA #30: Nombre base de archivos

**Equivalente a:** Modo 1 Pantalla #27

```
═══════════════════════════════════════════════════════════════
  NOMBRE DE ARCHIVOS DE SALIDA
═══════════════════════════════════════════════════════════════

📁 CONFIGURACIÓN FINAL

El sistema generará los siguientes archivos en la carpeta de salida:

Carpeta sugerida:
  📁 IMEI_860766049463800_alias_2026-04-10_18-45

Archivos a generar:
  📄 IMEI_860766049463800_alias_2026-04-10_18-45_informe.html
  🗺️ IMEI_860766049463800_alias_2026-04-10_18-45_mapeo.kmz
  🔐 IMEI_860766049463800_alias_2026-04-10_18-45_hashes.txt
  ⚠️ IMEI_860766049463800_alias_2026-04-10_18-45_errores.txt

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

**Navegación:** Input / Enter / C  
**Botones GUI:** Campo de texto + [Usar sugerido] [Generar] [✕ Cancelar]

**Ver diseño completo:** `DISENO_FLUJO_COMPLETO_MODO1.md` - Pantalla #27

---

## ISSUES CONOCIDOS

### 🐛 ISSUE #1: Bug en filtros de rango de horas (Opciones 3 y 4)

**Severidad:** ALTA  
**Estado:** CONFIRMADO — Pendiente corrección

**Descripción:**
- Las opciones 3 (Rango de horas en un día) y 4 (Rango de horas global) del filtro temporal NO funcionan correctamente
- Siempre retornan 0 registros, incluso con rangos completamente válidos (00:00-23:59)
- El problema es independiente del formato de hora ingresado (HH:MM o HH:MM:SS)

**Evidencia:**
```
Prueba 1 - Opción 3:
  Input: Día 01/01/2020, 00:00 → 23:59
  Esperado: 12 registros (día completo)
  Resultado: 0 registros

Prueba 2 - Opción 4:
  Input: 00:00 → 23:59 (todos los días)
  Esperado: 50 registros (bitácora completa)
  Resultado: 0 registros
```

**Impacto:**
- Opciones 3 y 4 son completamente inutilizables
- Usuarios solo pueden filtrar por día completo (opciones 1 y 2)
- Casos de uso como "horario del hecho" o "actividad nocturna" no son posibles

**Solución temporal para usuarios:**
- Usar opción 1 (Día específico) como alternativa
- Usar opción 2 (Rango de días) para períodos más amplios

**Causa probable (requiere debugging):**
- Error en lógica de comparación de horas
- Problema con timezone o formato de timestamp
- Columna 'hora' tiene formato incompatible con el filtro

**Prioridad:** ALTA (funcionalidad completa bloqueada)

---

### 🔴 ISSUE #2: Sistema aborta sin recuperación cuando filtro falla

**Severidad:** CRÍTICA  
**Estado:** CONFIRMADO — Solución diseñada (Pantalla #27 variante B)

**Descripción:**
- Cuando un filtro temporal produce 0 registros, el sistema muestra:
  ```
  No hay registros después de aplicar el filtro. Saliendo...
  ```
- Aborta TODO el proceso inmediatamente
- Usuario pierde TODO el mapeo realizado (14 campos + info complementaria)
- No hay opción de corregir el filtro y reintentar

**Impacto:**
Usuario debe reiniciar desde cero:
1. Volver al menú principal (Pantalla #1)
2. Re-seleccionar archivo
3. Re-seleccionar hoja Excel
4. Re-mapear 10 campos esenciales
5. Re-mapear 4 campos opcionales
6. Re-ingresar alias, usuario, abonado
7. Re-confirmar todo
8. Reintentar filtro temporal

**Flujo actual (problemático):**
```
Usuario → 25 minutos mapeando → Filtro falla → ABORTA TODO → Reiniciar desde #1
```

**Flujo deseado (con Pantalla #27 variante B):**
```
Usuario → 25 minutos mapeando → Filtro falla → R=Cambiar filtro → Reintentar (mantiene mapeo)
```

**Solución propuesta:**
Implementar **Pantalla #27 variante B** que:
- Detecta cuando el filtro produce 0 registros
- Muestra información útil (rango de fechas disponibles, actividad del día)
- Ofrece opción R = Cambiar filtro (vuelve a Pantalla #25, mantiene mapeo)
- Ofrece opción C = Cancelar (vuelve al menú principal)

**Prioridad:** CRÍTICA (UX bloqueante, causa frustración extrema)

---

## CRITERIOS DE ÉXITO

### Usabilidad
- [ ] Usuario sin capacitación completa el flujo Modo 2 siguiendo solo las instrucciones en pantalla
- [ ] Cero errores de selección de filtro por ambigüedad en opciones
- [ ] Usuario puede corregir filtro fallido sin perder mapeo (con Pantalla #27 variante B)
- [ ] Tiempo de ejecución ≤ 10% mayor que Modo 1 (por filtrado adicional)

### Técnico
- [ ] Golden output byte-identical para registros filtrados vs Modo 1 con mismo subset
- [ ] Tests completos pasando sin regresiones
- [ ] Código permite volver atrás hasta confirmación final (Pantalla #24)
- [ ] Implementada Pantalla #27 con ambas variantes (exitosa y fallida)

### Funcional
- [ ] Opciones 1 y 2 de filtro funcionan correctamente
- [ ] Issues #1 y #2 corregidos (filtros por hora + recuperación de errores)
- [ ] Usuario puede elegir "Sin filtro" (opción 5) y procesar como Modo 1
- [ ] Sistema muestra rangos de fechas disponibles antes de solicitar filtro

---

## BLOQUE DE RELEVO — PRÓXIMO CHAT

```
=== RELEVO — DISEÑO DE USABILIDAD ===

FASE ACTUAL: Diseño Modo 2 COMPLETADO

ESTADO:
✅ Pantallas #25-27 diseñadas y aprobadas
✅ Referencias a pantallas compartidas (#1-24) documentadas
✅ Referencias a pantallas finales (#28-30) documentadas
✅ 2 Issues conocidos documentados (bug filtros + aborto sin recuperación)
✅ Documento generado: DISENO_FLUJO_COMPLETO_MODO2.md

PENDIENTE:
⏳ Diseñar Modo 3 (Ingresar antenas manualmente)
⏳ Ejecutar prueba guiada completa Tony+Claude para mapear fricción real
⏳ Corregir Issue #1 (bug filtros de rango de horas)
⏳ Implementar Issue #2 (Pantalla #27 variante B - recuperación de errores)
⏳ Implementar mejoras de usabilidad en QC Wizard (P1 del diagnóstico)

DOCUMENTOS GENERADOS:
📄 DISENO_FLUJO_COMPLETO_MODO1.md (existe)
📄 DISENO_FLUJO_COMPLETO_MODO2.md (este archivo)

PRÓXIMA ACCIÓN:
Opción A: Diseñar Modo 3 (flujo manual de antenas)
Opción B: Prueba guiada completa Modo 1 o Modo 2
Opción C: Implementar correcciones de Issues conocidos

PROTOCOLO DE RETOMA:
Tony, pega:
1. Este documento (DISENO_FLUJO_COMPLETO_MODO2.md)
2. git status + log
3. Di: "Vamos a [diseñar Modo 3 / hacer prueba guiada / implementar correcciones]"

ISSUES CRÍTICOS DETECTADOS:
🐛 Issue #1: Opciones 3 y 4 de filtro no funcionan (bug en lógica de horas)
🔴 Issue #2: Sistema aborta sin recuperación cuando filtro falla (implementar Pantalla #27 variante B)

==========================================
```

---

*Documento generado por consenso entre Tony (Omar Arias) y Claude Sonnet 4.5. Abril 2026.*
