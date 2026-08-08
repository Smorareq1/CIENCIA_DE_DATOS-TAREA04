-- Modelo normalizado (3FN) — Ruta Verde
-- Fuente: docs/GUIA.md

CREATE TABLE IF NOT EXISTS departamento (
    departamento_id INT PRIMARY KEY,
    nombre VARCHAR(60)
);

CREATE TABLE IF NOT EXISTS municipio (
    municipio_id INT PRIMARY KEY,
    nombre VARCHAR(60),
    departamento_id INT REFERENCES departamento(departamento_id)
);

CREATE TABLE IF NOT EXISTS zona (
    zona_id INT PRIMARY KEY,
    nombre VARCHAR(60),
    municipio_id INT REFERENCES municipio(municipio_id)
);

CREATE TABLE IF NOT EXISTS restaurante (
    restaurante_id INT PRIMARY KEY,
    nombre VARCHAR(80),
    zona_id INT REFERENCES zona(zona_id)
);

CREATE TABLE IF NOT EXISTS cliente (
    cliente_id INT PRIMARY KEY,
    nombre VARCHAR(80),
    segmento VARCHAR(20),
    telefono VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS pedido (
    pedido_id INT PRIMARY KEY,
    cliente_id INT REFERENCES cliente(cliente_id),
    restaurante_id INT REFERENCES restaurante(restaurante_id),
    fecha DATE,
    total DECIMAL(10, 2),
    estado VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_municipio_departamento ON municipio (departamento_id);
CREATE INDEX IF NOT EXISTS idx_zona_municipio ON zona (municipio_id);
CREATE INDEX IF NOT EXISTS idx_restaurante_zona ON restaurante (zona_id);
CREATE INDEX IF NOT EXISTS idx_pedido_cliente ON pedido (cliente_id);
CREATE INDEX IF NOT EXISTS idx_pedido_restaurante ON pedido (restaurante_id);
CREATE INDEX IF NOT EXISTS idx_pedido_fecha ON pedido (fecha);
