-- Carga CSV del modelo normalizado (rutas dentro del contenedor)
-- Orden: tablas sin dependencias → dependientes → pedido

TRUNCATE TABLE pedido, restaurante, zona, municipio, departamento, cliente
    RESTART IDENTITY CASCADE;

COPY departamento FROM '/datos/departamento.csv' CSV HEADER;
COPY municipio    FROM '/datos/municipio.csv'    CSV HEADER;
COPY zona         FROM '/datos/zona.csv'         CSV HEADER;
COPY restaurante  FROM '/datos/restaurante.csv'  CSV HEADER;
COPY cliente      FROM '/datos/cliente.csv'      CSV HEADER;
COPY pedido       FROM '/datos/pedido.csv'       CSV HEADER;

ANALYZE departamento;
ANALYZE municipio;
ANALYZE zona;
ANALYZE restaurante;
ANALYZE cliente;
ANALYZE pedido;
