-- Tarea 06: estrella con claves sustitutas, varios procesos, drill-across.
-- Parte de las dims/hechos de la 05 y las reconstruye (SK, segundo y tercer proceso).
--
-- Procesos:
--   hechos_pedidos         transaccional  grano: un pedido registrado
--   hechos_cobros          transaccional  grano: un pago recibido
--   hechos_calificaciones  transaccional  grano: una calificación enviada
--   hechos_cancelaciones   factless       grano: una cancelación ocurrida
--   hechos_ventas_zona_mes agregada       grano: ventas de una zona en un mes
--
-- Cobros se derivan de pedido entregado (laboratorio). ~1/7 de esos pedidos
-- tiene DOS pagos (grano distinto al de pedido) para que el JOIN directo mienta.

DROP TABLE IF EXISTS hechos_ventas_zona_mes CASCADE;
DROP TABLE IF EXISTS hechos_cancelaciones CASCADE;
DROP TABLE IF EXISTS hechos_calificaciones CASCADE;
DROP TABLE IF EXISTS hechos_cobros CASCADE;
DROP TABLE IF EXISTS hechos_pedidos CASCADE;
DROP TABLE IF EXISTS dim_restaurante CASCADE;
DROP TABLE IF EXISTS dim_cliente CASCADE;
DROP TABLE IF EXISTS dim_fecha CASCADE;
DROP TABLE IF EXISTS dim_estado CASCADE;

-- ---------------------------------------------------------------------------
-- Dimensiones con PK sustituta (no la llave del origen)
-- cliente_id / restaurante_id / fecha / estado quedan como llaves naturales
-- ---------------------------------------------------------------------------
CREATE TABLE dim_fecha AS
SELECT
    ROW_NUMBER() OVER (ORDER BY fecha)::INT AS fecha_key,
    fecha AS fecha_id,
    fecha,
    EXTRACT(YEAR FROM fecha)::INT AS anio,
    EXTRACT(MONTH FROM fecha)::INT AS mes,
    EXTRACT(DAY FROM fecha)::INT AS dia,
    EXTRACT(ISODOW FROM fecha)::INT AS dia_semana,
    to_char(fecha, 'YYYY-MM') AS anio_mes
FROM (SELECT DISTINCT fecha FROM pedido) d;

ALTER TABLE dim_fecha ADD PRIMARY KEY (fecha_key);
CREATE UNIQUE INDEX idx_dim_fecha_natural ON dim_fecha (fecha_id);
CREATE INDEX idx_dim_fecha_anio_mes ON dim_fecha (anio_mes);

ANALYZE dim_fecha;

CREATE TABLE dim_cliente AS
SELECT
    ROW_NUMBER() OVER (ORDER BY cliente_id)::INT AS cliente_key,
    cliente_id,
    nombre,
    segmento,
    telefono
FROM cliente;

ALTER TABLE dim_cliente ADD PRIMARY KEY (cliente_key);
CREATE UNIQUE INDEX idx_dim_cliente_natural ON dim_cliente (cliente_id);
CREATE INDEX idx_dim_cliente_segmento ON dim_cliente (segmento);

ANALYZE dim_cliente;

CREATE TABLE dim_restaurante AS
SELECT
    ROW_NUMBER() OVER (ORDER BY r.restaurante_id)::INT AS restaurante_key,
    r.restaurante_id,
    r.nombre AS restaurante_nombre,
    z.zona_id,
    z.nombre AS zona_nombre,
    m.municipio_id,
    m.nombre AS municipio_nombre,
    d.departamento_id,
    d.nombre AS departamento_nombre
FROM restaurante r
JOIN zona z ON z.zona_id = r.zona_id
JOIN municipio m ON m.municipio_id = z.municipio_id
JOIN departamento d ON d.departamento_id = m.departamento_id;

ALTER TABLE dim_restaurante ADD PRIMARY KEY (restaurante_key);
CREATE UNIQUE INDEX idx_dim_restaurante_natural ON dim_restaurante (restaurante_id);
CREATE INDEX idx_dim_restaurante_zona ON dim_restaurante (zona_id);
CREATE INDEX idx_dim_restaurante_depto ON dim_restaurante (departamento_id);

ANALYZE dim_restaurante;

CREATE TABLE dim_estado AS
SELECT
    ROW_NUMBER() OVER (ORDER BY estado)::INT AS estado_key,
    estado AS estado_id,
    estado AS nombre
FROM (SELECT DISTINCT estado FROM pedido) e;

ALTER TABLE dim_estado ADD PRIMARY KEY (estado_key);
CREATE UNIQUE INDEX idx_dim_estado_natural ON dim_estado (estado_id);

ANALYZE dim_estado;

-- Calendario extendido: cobros pueden caer 0–3 días después del pedido
INSERT INTO dim_fecha (fecha_key, fecha_id, fecha, anio, mes, dia, dia_semana, anio_mes)
SELECT
    (SELECT COALESCE(MAX(fecha_key), 0) FROM dim_fecha) + ROW_NUMBER() OVER (ORDER BY f.fecha),
    f.fecha, f.fecha,
    EXTRACT(YEAR FROM f.fecha)::INT,
    EXTRACT(MONTH FROM f.fecha)::INT,
    EXTRACT(DAY FROM f.fecha)::INT,
    EXTRACT(ISODOW FROM f.fecha)::INT,
    to_char(f.fecha, 'YYYY-MM')
FROM (
    SELECT DISTINCT (p.fecha + (p.pedido_id % 4))::DATE AS fecha
    FROM pedido p
) f
WHERE NOT EXISTS (SELECT 1 FROM dim_fecha d WHERE d.fecha_id = f.fecha);

ANALYZE dim_fecha;

-- ---------------------------------------------------------------------------
-- hechos_pedidos (transaccional)
-- Medidas ADITIVAS: total, n_pedidos, n_entregados, n_cancelados
-- % entregado = SUM(n_entregados)/SUM(n_pedidos)  → nunca guardar el %
-- pedido_id = dimensión degenerada
-- ---------------------------------------------------------------------------
CREATE TABLE hechos_pedidos AS
SELECT
    p.pedido_id,
    dc.cliente_key,
    dr.restaurante_key,
    df.fecha_key AS fecha_pedido_key,
    de.estado_key,
    p.total,
    1::INT AS n_pedidos,
    CASE WHEN p.estado = 'entregado' THEN 1 ELSE 0 END::INT AS n_entregados,
    CASE WHEN p.estado = 'cancelado' THEN 1 ELSE 0 END::INT AS n_cancelados
FROM pedido p
JOIN dim_cliente dc ON dc.cliente_id = p.cliente_id
JOIN dim_restaurante dr ON dr.restaurante_id = p.restaurante_id
JOIN dim_fecha df ON df.fecha_id = p.fecha
JOIN dim_estado de ON de.estado_id = p.estado;

ALTER TABLE hechos_pedidos ADD PRIMARY KEY (pedido_id);
CREATE INDEX idx_hp_fecha ON hechos_pedidos (fecha_pedido_key);
CREATE INDEX idx_hp_restaurante ON hechos_pedidos (restaurante_key);
CREATE INDEX idx_hp_cliente ON hechos_pedidos (cliente_key);
CREATE INDEX idx_hp_estado ON hechos_pedidos (estado_key);

ANALYZE hechos_pedidos;

-- ---------------------------------------------------------------------------
-- hechos_cobros (transaccional, grano: un pago)
-- Role-playing: fecha_cobro_key → la MISMA dim_fecha que fecha_pedido_key
-- ~1/7 de pedidos entregados se parte en 2 cobros (JOIN directo infla)
-- ---------------------------------------------------------------------------
CREATE TABLE hechos_cobros AS
WITH base AS (
    SELECT
        p.pedido_id,
        dc.cliente_key,
        dr.restaurante_key,
        p.fecha,
        p.pedido_id % 4 AS lag_dias,
        p.pedido_id % 7 AS split,
        p.total
    FROM pedido p
    JOIN dim_cliente dc ON dc.cliente_id = p.cliente_id
    JOIN dim_restaurante dr ON dr.restaurante_id = p.restaurante_id
    WHERE p.estado = 'entregado'
),
pagos AS (
    SELECT
        pedido_id, cliente_key, restaurante_key,
        (fecha + lag_dias)::DATE AS fecha_cobro,
        1 AS n_pago,
        CASE WHEN split = 0 THEN ROUND(total / 2, 2) ELSE total END AS monto
    FROM base
    UNION ALL
    SELECT
        pedido_id, cliente_key, restaurante_key,
        (fecha + lag_dias)::DATE,
        2,
        total - ROUND(total / 2, 2)
    FROM base
    WHERE split = 0
)
SELECT
    ROW_NUMBER() OVER (ORDER BY pedido_id, n_pago)::BIGINT AS cobro_id,
    p.pedido_id,
    p.cliente_key,
    p.restaurante_key,
    df.fecha_key AS fecha_cobro_key,
    p.n_pago,
    p.monto,
    1::INT AS n_cobros
FROM pagos p
JOIN dim_fecha df ON df.fecha_id = p.fecha_cobro;

ALTER TABLE hechos_cobros ADD PRIMARY KEY (cobro_id);
CREATE INDEX idx_hc_pedido ON hechos_cobros (pedido_id);
CREATE INDEX idx_hc_fecha ON hechos_cobros (fecha_cobro_key);
CREATE INDEX idx_hc_restaurante ON hechos_cobros (restaurante_key);
CREATE INDEX idx_hc_cliente ON hechos_cobros (cliente_key);

ANALYZE hechos_cobros;

-- ---------------------------------------------------------------------------
-- hechos_calificaciones (transaccional, grano: una calificación)
-- puntaje es ADITIVO como suma; el promedio es NO ADITIVO → se calcula al consultar
-- ---------------------------------------------------------------------------
CREATE TABLE hechos_calificaciones AS
SELECT
    p.pedido_id AS calificacion_id,
    p.pedido_id,
    dc.cliente_key,
    dr.restaurante_key,
    df.fecha_key AS fecha_calificacion_key,
    (1 + (p.pedido_id % 5))::INT AS puntaje,
    1::INT AS n_calificaciones
FROM pedido p
JOIN dim_cliente dc ON dc.cliente_id = p.cliente_id
JOIN dim_restaurante dr ON dr.restaurante_id = p.restaurante_id
JOIN dim_fecha df ON df.fecha_id = p.fecha
WHERE p.estado = 'entregado';

ALTER TABLE hechos_calificaciones ADD PRIMARY KEY (calificacion_id);
CREATE INDEX idx_hcal_fecha ON hechos_calificaciones (fecha_calificacion_key);
CREATE INDEX idx_hcal_restaurante ON hechos_calificaciones (restaurante_key);
CREATE INDEX idx_hcal_cliente ON hechos_calificaciones (cliente_key);

ANALYZE hechos_calificaciones;

-- ---------------------------------------------------------------------------
-- hechos_cancelaciones — FACTLESS (solo FKs; se consulta con COUNT(*))
-- ---------------------------------------------------------------------------
CREATE TABLE hechos_cancelaciones AS
SELECT
    p.pedido_id,
    dc.cliente_key,
    dr.restaurante_key,
    df.fecha_key AS fecha_cancelacion_key
FROM pedido p
JOIN dim_cliente dc ON dc.cliente_id = p.cliente_id
JOIN dim_restaurante dr ON dr.restaurante_id = p.restaurante_id
JOIN dim_fecha df ON df.fecha_id = p.fecha
WHERE p.estado = 'cancelado';

ALTER TABLE hechos_cancelaciones ADD PRIMARY KEY (pedido_id);
CREATE INDEX idx_hcan_fecha ON hechos_cancelaciones (fecha_cancelacion_key);
CREATE INDEX idx_hcan_restaurante ON hechos_cancelaciones (restaurante_key);

ANALYZE hechos_cancelaciones;

-- ---------------------------------------------------------------------------
-- hechos_ventas_zona_mes — agregado (otro grano, otra tabla)
-- numerador/denominador aditivos; NO se materializa ticket_promedio ni %
-- ---------------------------------------------------------------------------
CREATE TABLE hechos_ventas_zona_mes AS
SELECT
    dr.zona_id,
    dr.zona_nombre,
    dr.departamento_id,
    dr.departamento_nombre,
    df.anio_mes,
    SUM(f.n_pedidos)::BIGINT AS n_pedidos,
    SUM(f.n_entregados)::BIGINT AS n_entregados,
    SUM(f.total) FILTER (WHERE f.n_entregados = 1) AS ventas_entregadas
FROM hechos_pedidos f
JOIN dim_restaurante dr ON dr.restaurante_key = f.restaurante_key
JOIN dim_fecha df ON df.fecha_key = f.fecha_pedido_key
GROUP BY
    dr.zona_id, dr.zona_nombre,
    dr.departamento_id, dr.departamento_nombre,
    df.anio_mes;

CREATE UNIQUE INDEX idx_hvzm ON hechos_ventas_zona_mes (zona_id, anio_mes);
ANALYZE hechos_ventas_zona_mes;
