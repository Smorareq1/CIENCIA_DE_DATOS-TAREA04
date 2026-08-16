-- Modelo dimensional (Tarea 05) sobre el 3FN de Ruta Verde.
-- NO se dibuja el estrella todavía (próxima clase): solo se materializa
-- la desnormalización correcta, con grano declarado y tablas separadas.
--
-- Proceso: registrar un pedido
-- Grano de hechos_pedidos: una fila = un pedido registrado
-- Tipo: transaccional (el evento se inserta; no hay hitos con timestamp)
--
-- Regla: grano distinto → tabla distinta.
-- hechos_ventas_zona_mes NO convive en hechos_pedidos.

-- ---------------------------------------------------------------------------
-- dim_fecha: atributos de calendario derivados de pedido.fecha
-- Dependencia que se rompe: ninguna de 3FN; se materializa fecha → (año, mes, dow)
-- para no recalcular to_char/extract en cada consulta.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS hechos_ventas_zona_mes CASCADE;
DROP TABLE IF EXISTS hechos_pedidos CASCADE;
DROP TABLE IF EXISTS dim_restaurante CASCADE;
DROP TABLE IF EXISTS dim_cliente CASCADE;
DROP TABLE IF EXISTS dim_fecha CASCADE;
DROP TABLE IF EXISTS dim_estado CASCADE;

CREATE TABLE dim_fecha AS
SELECT
    fecha AS fecha_id,
    fecha,
    EXTRACT(YEAR FROM fecha)::INT AS anio,
    EXTRACT(MONTH FROM fecha)::INT AS mes,
    EXTRACT(DAY FROM fecha)::INT AS dia,
    EXTRACT(ISODOW FROM fecha)::INT AS dia_semana,
    to_char(fecha, 'YYYY-MM') AS anio_mes
FROM (SELECT DISTINCT fecha FROM pedido) d;

ALTER TABLE dim_fecha ADD PRIMARY KEY (fecha_id);
CREATE INDEX idx_dim_fecha_anio_mes ON dim_fecha (anio_mes);
CREATE INDEX idx_dim_fecha_dia_semana ON dim_fecha (dia_semana);

ANALYZE dim_fecha;

-- ---------------------------------------------------------------------------
-- dim_cliente: el 3FN de cliente ya era una dimensión (quién).
-- Se copia a la capa de consumo; no se mezcla con el hecho.
-- ---------------------------------------------------------------------------
CREATE TABLE dim_cliente AS
SELECT
    cliente_id,
    nombre,
    segmento,
    telefono
FROM cliente;

ALTER TABLE dim_cliente ADD PRIMARY KEY (cliente_id);
CREATE INDEX idx_dim_cliente_segmento ON dim_cliente (segmento);

ANALYZE dim_cliente;

-- ---------------------------------------------------------------------------
-- dim_restaurante: AQUÍ va el pre-join geográfico (no en el hecho).
-- Dependencia 3FN que se rompe (transitiva):
--   restaurante_id → zona_id → municipio_id → departamento_id → departamento.nombre
-- En 3FN estaba repartida en restaurante, zona, municipio, departamento.
-- En el mart queda colapsada en dim_restaurante (una fila por restaurante).
-- ---------------------------------------------------------------------------
CREATE TABLE dim_restaurante AS
SELECT
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

ALTER TABLE dim_restaurante ADD PRIMARY KEY (restaurante_id);
CREATE INDEX idx_dim_restaurante_zona ON dim_restaurante (zona_id);
CREATE INDEX idx_dim_restaurante_depto ON dim_restaurante (departamento_id);

ANALYZE dim_restaurante;

-- ---------------------------------------------------------------------------
-- dim_estado: degenerada promovida a dimensión chica (filtra, no suma).
-- ---------------------------------------------------------------------------
CREATE TABLE dim_estado AS
SELECT DISTINCT
    estado AS estado_id,
    estado AS nombre
FROM pedido;

ALTER TABLE dim_estado ADD PRIMARY KEY (estado_id);

ANALYZE dim_estado;

-- ---------------------------------------------------------------------------
-- hechos_pedidos — TRANSACCIONAL
-- Grano: una fila = un pedido registrado
-- Medidas: total, n_pedidos (=1)
-- pedido_id es dimensión degenerada (vive en el hecho, sin dim_pedido).
-- ---------------------------------------------------------------------------
CREATE TABLE hechos_pedidos AS
SELECT
    p.pedido_id,
    p.cliente_id,
    p.restaurante_id,
    p.fecha AS fecha_id,
    p.estado AS estado_id,
    p.total,
    1::INT AS n_pedidos
FROM pedido p;

ALTER TABLE hechos_pedidos ADD PRIMARY KEY (pedido_id);
CREATE INDEX idx_hechos_pedidos_fecha ON hechos_pedidos (fecha_id);
CREATE INDEX idx_hechos_pedidos_restaurante ON hechos_pedidos (restaurante_id);
CREATE INDEX idx_hechos_pedidos_cliente ON hechos_pedidos (cliente_id);
CREATE INDEX idx_hechos_pedidos_estado ON hechos_pedidos (estado_id);

ANALYZE hechos_pedidos;

-- ---------------------------------------------------------------------------
-- hechos_ventas_zona_mes — TABLA AGREGADA (otro grano, otra tabla)
-- Grano: una fila = las ventas de una zona en un mes (solo entregados)
-- No convive con hechos_pedidos. No responde preguntas a nivel pedido.
-- ---------------------------------------------------------------------------
CREATE TABLE hechos_ventas_zona_mes AS
SELECT
    dr.zona_id,
    dr.zona_nombre,
    dr.municipio_id,
    dr.municipio_nombre,
    dr.departamento_id,
    dr.departamento_nombre,
    df.anio_mes,
    SUM(f.n_pedidos)::BIGINT AS n_pedidos,
    SUM(f.total) AS ventas_totales
FROM hechos_pedidos f
JOIN dim_restaurante dr ON dr.restaurante_id = f.restaurante_id
JOIN dim_fecha df ON df.fecha_id = f.fecha_id
WHERE f.estado_id = 'entregado'
GROUP BY
    dr.zona_id, dr.zona_nombre,
    dr.municipio_id, dr.municipio_nombre,
    dr.departamento_id, dr.departamento_nombre,
    df.anio_mes;

CREATE UNIQUE INDEX idx_hechos_zona_mes ON hechos_ventas_zona_mes (zona_id, anio_mes);
CREATE INDEX idx_hechos_zona_mes_depto ON hechos_ventas_zona_mes (departamento_id, anio_mes);

ANALYZE hechos_ventas_zona_mes;
