# Comparaciones Tarea 05: 3FN vs modelo dimensional

**Fecha de medición:** 2026-08-16T11:27:13-06:00
**Motor:** PostgreSQL 16 (Docker)
**Volumen:** 3,000,000 filas en `pedido` / `hechos_pedidos`

## Protocolo de tiempo

1. Se descarta la primera corrida (cold cache).
2. Se reporta la **mediana** de 5 corridas calientes.
3. Equivalencia verificada con fingerprint MD5 del result set.
4. Tiempo = `EXPLAIN (ANALYZE, FORMAT JSON)` → `Execution Time`.

## Espacio en disco

| Tabla / objeto | Tamaño |
|----------------|--------|
| `mart_pedido_geo` | 497 MB |
| `hechos_pedidos` | 342 MB |
| `pedido` | 331 MB |
| `dim_cliente` | 7960 kB |
| `cliente` | 7112 kB |
| `hechos_ventas_zona_mes` | 2040 kB |
| `agg_ventas_zona_mes` | 1928 kB |
| `mv_ventas_zona_mes` | 1312 kB |
| `dim_restaurante` | 408 kB |
| `restaurante` | 296 kB |
| `dim_fecha` | 136 kB |
| `zona` | 96 kB |
| `municipio` | 40 kB |
| `departamento` | 24 kB |
| `dim_estado` | 24 kB |

- **Suma 3FN** (departamento+municipio+zona+restaurante+cliente+pedido): **339 MB**
- **Suma dimensional transaccional** (dims + `hechos_pedidos`): **350 MB**
- **`hechos_ventas_zona_mes` (agregada, otro grano):** **2040 kB**

## Q1_ventas_zona_mes: Ventas totales por zona y mes (dashboard gerencial)

**Nota de grano:** Mismo patrón de la clase 04. El dimensional NO cambia el grano: agrega en query time. La tabla agregada SÍ cambia el grano (otra tabla).

**Equivalencia:** OK — mismo fingerprint

| Variante | Mediana (ms) | Min | Max | Cold |
|----------|-------------:|----:|----:|-----:|
| normalizado | 685.608 | 682.906 | 693.724 | 684.395 |
| dimensional | 365.082 | 354.052 | 376.934 | 356.958 |
| agregada | 2.150 | 2.132 | 2.291 | 3.085 |

### Ganancia vs 3FN

- **dimensional:** 1.88x más rápida (46.8% menos tiempo)
- **agregada:** 318.89x más rápida (99.7% menos tiempo)

## Q2_ventas_departamento_mes: Ventas por departamento y mes (rollup geográfico)

**Nota de grano:** El pre-join vive en dim_restaurante (2 500 filas), no repetido en 3M hechos.

**Equivalencia:** OK — mismo fingerprint

| Variante | Mediana (ms) | Min | Max | Cold |
|----------|-------------:|----:|----:|-----:|
| normalizado | 480.243 | 478.635 | 489.554 | 475.633 |
| dimensional | 277.719 | 271.999 | 282.824 | 274.899 |
| agregada | 3.301 | 3.205 | 3.351 | 3.312 |

### Ganancia vs 3FN

- **dimensional:** 1.73x más rápida (42.2% menos tiempo)
- **agregada:** 145.48x más rápida (99.3% menos tiempo)

## Q3_top_zonas_2025q1: Top 20 zonas por ventas en 2025-Q1

**Nota de grano:** Filtro temporal selectivo. La agregada gana porque el grain zona×mes ya está materializado.

**Equivalencia:** OK — mismo fingerprint

| Variante | Mediana (ms) | Min | Max | Cold |
|----------|-------------:|----:|----:|-----:|
| normalizado | 78.814 | 76.325 | 79.498 | 82.334 |
| dimensional | 108.447 | 106.012 | 112.844 | 107.510 |
| agregada | 1.722 | 1.672 | 1.733 | 2.111 |

### Ganancia vs 3FN

- **dimensional:** 1.38x más lenta (37.6% más tiempo)
- **agregada:** 45.77x más rápida (97.8% menos tiempo)

## Q4_segmento_dia_semana: Ventas por segmento de cliente y día de la semana

**Nota de grano:** Pregunta que el grano zona×mes NO puede responder. Solo 3FN y el hecho transaccional. Demuestra que el grano es irreversible.

**Equivalencia:** OK — mismo fingerprint

| Variante | Mediana (ms) | Min | Max | Cold |
|----------|-------------:|----:|----:|-----:|
| normalizado | 340.980 | 338.429 | 378.753 | 335.457 |
| dimensional | 334.715 | 324.539 | 343.973 | 321.028 |

### Ganancia vs 3FN

- **dimensional:** 1.02x más rápida (1.8% menos tiempo)

## Lectura de los tiempos (lo que pide la guía)

La clase 05 no pide un motor concreto, pero sí que el grano y las desnormalizaciones se justifiquen. Los tiempos muestran que:

1. **Desnormalizar la dimensión** (`dim_restaurante`) no replica geo en 3M filas; el hecho sigue delgado. El costo de espacio extra está en las dims, no en un mart ancho.
2. **La tabla agregada** es otra tabla de hechos, otro grano. Gana órdenes de magnitud en Q1–Q3 porque ya no recorre 3M pedidos. No se usa para Q4: esa pregunta exige el grano fino.
3. **Q4 no tiene variante agregada** a propósito: si el grano fuera zona×mes, «ventas por segmento y día de la semana» ya no tendría respuesta. Eso es lo que la guía llama grano irreversible.

_Raw JSON: `docs/05/procedimiento/raw_mediciones.json`_
