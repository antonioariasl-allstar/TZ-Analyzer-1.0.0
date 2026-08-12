# Dependencias de terceros vendorizadas (uso offline)

Estos archivos se incorporan al repositorio para que los informes HTML
generados por TZ Analyzer funcionen sin conexión a Internet (AUD-08). Se
embeben (inline) dentro del HTML/KMZ generado en tiempo de ejecución; no se
minifican ni se modifican salvo lo indicado.

## Leaflet

- Versión: 1.9.4 (misma versión que ya se referenciaba vía CDN antes de este cambio)
- Licencia: BSD-2-Clause
- Origen oficial: https://unpkg.com/leaflet@1.9.4/dist/ (paquete npm `leaflet`, repo https://github.com/Leaflet/Leaflet)
- Archivos incluidos:
  - `leaflet.js`
  - `leaflet.css` (sin modificar; TZ Analyzer reescribe en memoria, al generar el HTML,
    las dos referencias `url(images/marker-icon...)` a data URIs para que el CSS
    embebido no dependa de archivos externos — ver `tz_core/html/header.py`)
  - `images/marker-icon.png`, `images/marker-icon-2x.png`, `images/marker-shadow.png`
    (íconos por defecto de Leaflet, usados como fuente para las data URIs anteriores)

## Leaflet.heat (plugin de mapa de calor)

- Versión: 0.2.0
- Licencia: BSD-2-Clause (paquete npm `leaflet.heat`, repo https://github.com/Leaflet/Leaflet.heat)
- Origen oficial: https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js
- Archivo incluido: `leaflet-heat.js`

## Nota de integridad

Los archivos se descargaron directamente de la fuente de distribución oficial
(unpkg, que sirve el contenido publicado en npm) en la fecha de este cambio y
no fueron reprocesados salvo la reescritura de rutas de imagen mencionada
arriba, aplicada en memoria al momento de generar cada informe (el archivo
`leaflet.css` vendorizado permanece intacto en disco).
