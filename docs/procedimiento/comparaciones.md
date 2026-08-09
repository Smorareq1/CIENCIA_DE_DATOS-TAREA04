# Comparaciones: modelo normalizado vs desnormalizado

**Fecha de medición:** 2026-08-09T11:31:19-06:00
**Motor:** PostgreSQL 16 (Docker)
**Volumen:** 3,000,000 filas en `pedido`

## Criterio: no desnormalizar “porque sí”

Las cinco técnicas de clase son un **menú, no una receta**. El flujo que
seguimos es el de la diapositiva de método:

1. **Empezar normalizado** (3FN cargado desde los CSV).
2. **Medir** qué consulta duele (frecuencia × costo), no intuición.
3. **Elegir por síntoma** la técnica adecuada.
4. **Documentar el trade-off** (qué gano, qué pierdo, por qué lo acepto).
5. **Volver a medir** — si no mejoró, **revertir / no adoptar**.

Desnormalizamos solo en la **capa de consumo** (`mart_*`, `agg_*`, `mv_*`).
El core (`pedido`, dimensiones geográficas, `cliente`) permanece en 3FN.

### Selección por síntoma (qué sí / qué no)

| Síntoma observado | Técnica candidata | ¿La adoptamos? | Justificación |
|-------------------|-------------------|----------------|---------------|
| Q1/Q2 encadenan 2–4 joins geográficos sobre 3M filas | 1. Pre-join | **Sí, con matices** | Mejora Q1 (~2.2×) y Q2 (~2.6×). En Q3 **empeora** → no se usa para ese patrón. |
| Se recalcula `to_char(fecha,'YYYY-MM')` / dow en cada query | 2. Columna derivada | **Sí (dentro del mart)** | `anio_mes` y `dia_semana` en `mart_pedido_geo`; baratas y alineadas al dashboard. |
| Dashboard recurrente barre millones para devolver ~12k filas zona×mes | 3. Tabla agregada | **Sí — preferida** | Q1 pasa de ~702 ms a ~1.2 ms; cuesta ~2 MB. Mejor relación ganancia/costo. |
| Pedido con muchos hijos que explotaría filas al aplanar | 4. Estructuras anidadas | **No** | El esquema de la guía no tiene `detalle_pedido`/`producto`. No hay síntoma de fan-out que resolver. Aplicarla sería inventar un problema. |
| Misma transformación del dashboard, versionable y refrescable | 5. Vista materializada | **Sí (alternativa a la agregada)** | Misma ganancia que `agg_*` (~0.9 ms) con SQL declarativo; obliga a definir política de `REFRESH`. |

### Qué rechazamos a propósito

- **No** convertimos el core en una sola tabla ancha de 300 columnas (trampa
  “la tabla que nadie entiende”).
- **No** usamos pre-join como solución universal: en Q3 midió **peor** que el
  3FN (106.6 ms vs 79.1 ms) → se descarta para rankings con filtro temporal
  selectivo.
- **No** aplicamos estructuras anidadas ni desnormalizamos para consultas
  exploratorias sin patrón fijo (reto de clase #3: “productos juntos”): sin
  modelo de detalle y sin recurrencia, desnormalizar sería optimizar a ciegas.
- **No** tocamos la capa de integración: ahí manda corrección e historia, no
  velocidad de lectura del dashboard.

Regla usada: *primero normalizado y correcto → medido → desnormalizado solo
donde la medición lo justifique.*

## Protocolo

Según `docs/GUIA/GUIA.md`:

1. Se descarta la primera corrida (cold cache).
2. Se reporta la **mediana** de 5 corridas calientes.
3. Se verifica equivalencia de resultados con fingerprint MD5 del result set.
4. Tiempo medido con `EXPLAIN (ANALYZE, FORMAT JSON)` → `Execution Time`.

## Espacio en disco

| Tabla / objeto | Tamaño |
|----------------|--------|
| `mart_pedido_geo` | 497 MB |
| `pedido` | 331 MB |
| `cliente` | 7112 kB |
| `agg_ventas_zona_mes` | 2040 kB |
| `mv_ventas_zona_mes` | 1416 kB |
| `restaurante` | 296 kB |
| `zona` | 96 kB |
| `municipio` | 40 kB |
| `departamento` | 24 kB |

- **Suma modelo normalizado** (`departamento`+`municipio`+`zona`+`restaurante`+`cliente`+`pedido`): **339 MB**
- **`mart_pedido_geo` (pre-join):** **497 MB**
- **`agg_ventas_zona_mes` (agregada):** **2040 kB**
- **`mv_ventas_zona_mes` (MV):** **1416 kB**

## Q1_ventas_zona_mes: Ventas totales por zona y mes (dashboard gerencial)

**Técnica(s):** Pre-join + columna derivada `anio_mes` / Tabla agregada / MV

**Equivalencia de resultados:** OK — mismo fingerprint

| Variante | Mediana (ms) | Min | Max | Cold |
|----------|-------------:|----:|----:|-----:|
| normalizado | 701.957 | 686.512 | 728.087 | 726.061 |
| prejoin | 312.761 | 298.702 | 321.103 | 311.005 |
| agregada | 1.248 | 1.200 | 1.345 | 1.709 |
| mv | 0.924 | 0.907 | 0.938 | 1.279 |

### Ganancia vs normalizado

- **prejoin:** 2.24x más rápida (55.4% menos tiempo)
- **agregada:** 562.47x más rápida (99.8% menos tiempo)
- **mv:** 759.69x más rápida (99.9% menos tiempo)

### Trade-off documentado

- **Qué gana:** el dashboard deja de recorrer millones de pedidos con 2–4 joins.
- **Redundancia:** nombres de zona/restaurante/depto repetidos (pre-join) o métricas materializadas (agg/MV).
- **Riesgo:** si cambia el nombre de una zona o se corrige un `total`, hay que refrescar mart/agg/MV; datos stale hasta el refresh.
- **Decisión para Q1:** se adopta **tabla agregada o MV** como solución principal
  (ganancia ~500–700×, ~2 MB). El pre-join ayuda (~2×) pero cuesta +158 MB y
  sigue agregando en query time; es opcional, no obligatorio. No se “tiran”
  las cinco técnicas: se elige la del síntoma (recorrer millones → pocas filas).

## Q2_ventas_departamento_mes: Ventas por departamento y mes (rollup geográfico)

**Técnica(s):** Pre-join (elimina 4 joins) vs joins normalizados

**Equivalencia de resultados:** OK — mismo fingerprint

| Variante | Mediana (ms) | Min | Max | Cold |
|----------|-------------:|----:|----:|-----:|
| normalizado | 488.551 | 482.503 | 492.510 | 484.389 |
| prejoin | 188.172 | 185.785 | 198.812 | 187.678 |
| agregada | 3.193 | 3.184 | 3.303 | 3.263 |

### Ganancia vs normalizado

- **prejoin:** 2.60x más rápida (61.5% menos tiempo)
- **agregada:** 153.01x más rápida (99.3% menos tiempo)

### Trade-off documentado

- **Qué gana:** elimina la cadena de joins geográficos en cada ejecución.
- **Redundancia:** `departamento_nombre` (y resto de jerarquía) denormalizado en el mart; o rollup desde la agregada.
- **Riesgo:** inconsistencia si la jerarquía geográfica se reclasifica (un municipio cambia de departamento) y no se regenera el mart.
- **Se acepta** en la capa de consumo (mart); el core sigue normalizado.

## Q3_top_zonas_ultimo_trimestre: Top 20 zonas por ventas en un trimestre fijo

**Técnica(s):** Pre-join + filtro sobre columna derivada / agregada filtrada

**Equivalencia de resultados:** OK — mismo fingerprint

| Variante | Mediana (ms) | Min | Max | Cold |
|----------|-------------:|----:|----:|-----:|
| normalizado | 79.082 | 78.446 | 81.779 | 78.235 |
| prejoin | 106.577 | 103.616 | 108.278 | 111.193 |
| agregada | 1.705 | 1.653 | 1.716 | 2.256 |

### Ganancia vs normalizado

- **prejoin:** 1.35x más lenta (34.8% más tiempo) — **no justifica esta técnica aquí**
- **agregada:** 46.38x más rápida (97.8% menos tiempo)

### Hallazgo

El pre-join **empeora** Q3: `mart_pedido_geo` es más ancho (497 MB vs 331 MB de
`pedido`) y, con un filtro de fechas selectivo, Postgres termina leyendo más
bytes que al hacer joins sobre tablas estrechas. La técnica correcta para este
patrón es la **tabla agregada** (lee ~12k filas zona×mes, no 3M).

### Trade-off documentado

- **Qué gana (agregada):** ranking trimestral sin escanear millones de pedidos.
- **Qué no gana (pre-join):** en este patrón el mart ancho cuesta más I/O que el 3FN.
- **Redundancia:** métricas por zona×mes materializadas (~2 MB).
- **Riesgo:** frescura del agregado hasta el refresh; grain fijo zona×mes.
- **Se acepta la agregada** para reportes periódicos; **se rechaza el pre-join para Q3**.

## Decisiones y riesgos (resumen)

| Decisión | Consulta que mejora | Costo de espacio | Riesgo asumido | ¿Por qué se acepta? |
|----------|---------------------|------------------|----------------|---------------------|
| A — Pre-join + columnas derivadas (`mart_pedido_geo`) | Q1 y Q2 (no Q3) — Q1: 312.8 ms vs 702.0 ms | 497 MB (+158 MB vs suma 3FN) | Redundancia de nombres; regenerar si cambia la dimensión o un pedido | Se acepta solo donde la medición mejora (historial completo con muchos joins); en Q3 se descarta |
| B — Tabla agregada (`agg_ventas_zona_mes`) | Q1 — mediana 1.248 ms vs 701.957 ms | 2040 kB | Granularidad fija zona×mes: no responde preguntas a nivel pedido sin volver al detalle | El dashboard solo necesita ese grain; el costo de espacio es mínimo vs escanear 3M filas |
| C — Vista materializada (`mv_ventas_zona_mes`) | Q1 — mediana 0.924 ms vs 701.957 ms | 1416 kB | Hay que definir política de `REFRESH MATERIALIZED VIEW` (datos stale) | Misma ganancia que la agregada, pero declarativa y versionable en SQL |

## Nota sobre consultas del reto de clase

El esquema entregado en la guía (`pedido`, `restaurante`, jerarquía geográfica, `cliente`) **no incluye** `repartidor`, tiempos de entrega ni `detalle_pedido`/`producto`. Por eso las consultas 2 y 3 del reto de diapositivas (tiempo por repartidor; products bought together) no se midieron aquí: requerirían ampliar el generador y el modelo. La consulta 1 del reto (ventas por zona y mes) sí se midió como **Q1**.

---

_Raw JSON: `docs/procedimiento/raw_mediciones.json`_
