# Comparaciones Tarea 06: drill-across, medidas y estrella

**Fecha de medición:** 2026-08-18T23:54:32-06:00
**Motor:** PostgreSQL 16 (Docker)
**Volumen:** 3,000,000 pedidos · 2,287,575 cobros · 2,001,626 calificaciones

## Protocolo de tiempo

1. Se descarta la primera corrida (cold cache).
2. Se reporta la **mediana** de 5 corridas calientes.
3. Tiempo = `EXPLAIN (ANALYZE, FORMAT JSON)` → `Execution Time`.
4. El JOIN ilegal y el drill-across **no** deben coincidir: el error es de grano, no de SQL.

## El error que nunca hay que cometer (JOIN entre hechos)

Un subconjunto de pedidos entregados tiene **dos cobros**. El JOIN `hechos_pedidos ⋈ hechos_cobros` duplica esas filas de pedido. La consulta corre y el número se ve plausible.

| KPI | Valor |
|-----|------:|
| Pedidos | 3,000,000 |
| Pedidos entregados | 2,001,626 |
| Pedidos entregados con 2 cobros | 285,949 |
| Filas en `hechos_cobros` | 2,287,575 |
| `SUM(total)` entregados (correcto) | Q485,342,952.50 |
| `SUM(monto)` cobros (correcto) | Q485,342,952.50 |
| `SUM(pedido.total)` tras JOIN ilegal | Q554,686,695.39 |
| Inflación del JOIN ilegal | **+14.29%** (Q69,343,742.89 de más) |

Cobrado correcto = ventas entregadas (cada quetzal se cobra una vez). El JOIN ilegal **no avisa**: infla ventas.

| Variante | Mediana (ms) | Min | Max | Cold | Fingerprint |
|----------|-------------:|----:|----:|-----:|-------------|
| join_ilegal | 844.293 | 837.115 | 930.516 | 803.739 | `dd3b49fb3379…` |
| drill_across | 751.533 | 717.291 | 769.503 | 713.045 | `597f7d8a91b4…` |

Tiempo: drill-across es 1.12x más rápida (11.0% menos tiempo) respecto del JOIN ilegal, pero el punto no es la velocidad: **el JOIN ilegal está mal aunque fuera más rápido**.

Fingerprints distintos: `dd3b49fb3379c80dc84a53b6aef9a492` vs `597f7d8a91b47276f47d02036abdd55a` — no miden lo mismo.

## Medida no aditiva: % entregado

Nunca se guarda el porcentaje. Se guardan `n_entregados` y `n_pedidos` (aditivos) y se divide al consultar.

| Método | Resultado |
|--------|----------:|
| Correcto: Σ entregados / Σ pedidos | **66.7209%** |
| Incorrecto: promedio de % por zona | 66.7403% |
| Sesgo al promediar porcentajes | 0.0194 puntos |

## Optimización: dashboard zona × mes (mismo protocolo que 04/05)

**Equivalencia 3FN / estrella / agregada:** OK — mismo fingerprint

| Variante | Mediana (ms) | Min | Max | Cold |
|----------|-------------:|----:|----:|-----:|
| normalizado_3fn | 708.774 | 699.722 | 737.069 | 718.880 |
| estrella | 389.165 | 368.168 | 406.336 | 384.064 |
| agregada | 2.450 | 2.369 | 2.490 | 2.306 |

### Ganancia vs 3FN

- **estrella:** 1.82x más rápida (45.1% menos tiempo)
- **agregada:** 289.30x más rápida (99.7% menos tiempo)

## Espacio

| Tabla | Tamaño |
|-------|--------|
| `mart_pedido_geo` | 497 MB |
| `hechos_pedidos` | 341 MB |
| `pedido` | 331 MB |
| `hechos_cobros` | 294 MB |
| `hechos_calificaciones` | 200 MB |
| `hechos_cancelaciones` | 39 MB |
| `dim_cliente` | 9768 kB |
| `hechos_ventas_zona_mes` | 1928 kB |
| `dim_restaurante` | 512 kB |
| `dim_fecha` | 152 kB |
| `dim_estado` | 40 kB |

Hecho angosto (`hechos_pedidos`) vs mart ancho clase 04 (`mart_pedido_geo`): el texto geográfico no se copia 3 millones de veces.

_Raw: `docs/06/procedimiento/raw_mediciones.json`_
