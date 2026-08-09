-- Modelos desnormalizados sobre Ruta Verde (técnicas de la clase)
-- 1) Pre-join  2) Columnas derivadas  3) Tabla agregada  5) Vista materializada

-- ---------------------------------------------------------------------------
-- Decisión A: Pre-join + columnas derivadas
-- Aplana pedido → restaurante → zona → municipio → departamento
-- y materializa mes (YYYY-MM) y dia_semana para el dashboard.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS mart_pedido_geo CASCADE;

CREATE TABLE mart_pedido_geo AS
SELECT
    p.pedido_id,
    p.cliente_id,
    p.restaurante_id,
    p.fecha,
    p.total,
    p.estado,
    -- columnas derivadas
    to_char(p.fecha, 'YYYY-MM') AS anio_mes,
    EXTRACT(ISODOW FROM p.fecha)::INT AS dia_semana,
    -- pre-join geográfico
    r.nombre AS restaurante_nombre,
    z.zona_id,
    z.nombre AS zona_nombre,
    m.municipio_id,
    m.nombre AS municipio_nombre,
    d.departamento_id,
    d.nombre AS departamento_nombre
FROM pedido p
JOIN restaurante r ON r.restaurante_id = p.restaurante_id
JOIN zona z ON z.zona_id = r.zona_id
JOIN municipio m ON m.municipio_id = z.municipio_id
JOIN departamento d ON d.departamento_id = m.departamento_id;

CREATE INDEX idx_mart_pedido_geo_zona_mes ON mart_pedido_geo (zona_id, anio_mes);
CREATE INDEX idx_mart_pedido_geo_depto_mes ON mart_pedido_geo (departamento_id, anio_mes);
CREATE INDEX idx_mart_pedido_geo_fecha ON mart_pedido_geo (fecha);
CREATE INDEX idx_mart_pedido_geo_estado ON mart_pedido_geo (estado);

ANALYZE mart_pedido_geo;

-- ---------------------------------------------------------------------------
-- Decisión B: Tabla agregada (granularidad zona × mes)
-- Optimiza el dashboard gerencial: ventas por zona y mes.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS agg_ventas_zona_mes CASCADE;

CREATE TABLE agg_ventas_zona_mes AS
SELECT
    z.zona_id,
    z.nombre AS zona_nombre,
    m.municipio_id,
    m.nombre AS municipio_nombre,
    d.departamento_id,
    d.nombre AS departamento_nombre,
    to_char(p.fecha, 'YYYY-MM') AS anio_mes,
    COUNT(*)::BIGINT AS n_pedidos,
    SUM(p.total) AS ventas_totales,
    AVG(p.total) AS ticket_promedio
FROM pedido p
JOIN restaurante r ON r.restaurante_id = p.restaurante_id
JOIN zona z ON z.zona_id = r.zona_id
JOIN municipio m ON m.municipio_id = z.municipio_id
JOIN departamento d ON d.departamento_id = m.departamento_id
WHERE p.estado = 'entregado'
GROUP BY
    z.zona_id, z.nombre,
    m.municipio_id, m.nombre,
    d.departamento_id, d.nombre,
    to_char(p.fecha, 'YYYY-MM');

CREATE INDEX idx_agg_ventas_zona_mes ON agg_ventas_zona_mes (zona_id, anio_mes);
CREATE INDEX idx_agg_ventas_depto_mes ON agg_ventas_zona_mes (departamento_id, anio_mes);

ANALYZE agg_ventas_zona_mes;

-- ---------------------------------------------------------------------------
-- Decisión C: Vista materializada (misma consulta del dashboard)
-- Desnormalización declarativa / refresco explícito.
-- ---------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_ventas_zona_mes;

CREATE MATERIALIZED VIEW mv_ventas_zona_mes AS
SELECT
    z.zona_id,
    z.nombre AS zona_nombre,
    to_char(p.fecha, 'YYYY-MM') AS anio_mes,
    COUNT(*)::BIGINT AS n_pedidos,
    SUM(p.total) AS ventas_totales
FROM pedido p
JOIN restaurante r ON r.restaurante_id = p.restaurante_id
JOIN zona z ON z.zona_id = r.zona_id
WHERE p.estado = 'entregado'
GROUP BY z.zona_id, z.nombre, to_char(p.fecha, 'YYYY-MM');

CREATE UNIQUE INDEX idx_mv_ventas_zona_mes ON mv_ventas_zona_mes (zona_id, anio_mes);

ANALYZE mv_ventas_zona_mes;
