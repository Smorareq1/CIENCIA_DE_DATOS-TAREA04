# Guía técnica --- Tarea 4

## Cargar los datos y medir el rendimiento

Los CSV que genera `generar_datos.py` traen el modelo ya normalizado. Su
trabajo es diseñar la versión desnormalizada, construirla y comparar.

Use el motor que prefiera. Abajo están los comandos para los más
comunes.

## 1. Crear las tablas

El esquema es el mismo en todos los motores. Ajuste los tipos si su
motor los nombra distinto.

### Jerarquía geográfica

``` sql
CREATE TABLE departamento (
    departamento_id INT PRIMARY KEY,
    nombre VARCHAR(60)
);

CREATE TABLE municipio (
    municipio_id INT PRIMARY KEY,
    nombre VARCHAR(60),
    departamento_id INT REFERENCES departamento(departamento_id)
);

CREATE TABLE zona (
    zona_id INT PRIMARY KEY,
    nombre VARCHAR(60),
    municipio_id INT REFERENCES municipio(municipio_id)
);
```

### Operación

``` sql
CREATE TABLE restaurante (
    restaurante_id INT PRIMARY KEY,
    nombre VARCHAR(80),
    zona_id INT REFERENCES zona(zona_id)
);

CREATE TABLE cliente (
    cliente_id INT PRIMARY KEY,
    nombre VARCHAR(80),
    segmento VARCHAR(20),
    telefono VARCHAR(20)
);

CREATE TABLE pedido (
    pedido_id INT PRIMARY KEY,
    cliente_id INT REFERENCES cliente(cliente_id),
    restaurante_id INT REFERENCES restaurante(restaurante_id),
    fecha DATE,
    total DECIMAL(10,2),
    estado VARCHAR(20)
);
```

### Orden de carga

Cargue primero las tablas sin dependencias (`departamento`, `cliente`),
luego las que apuntan a ellas, y `pedido` al final. Si no, las llaves
foráneas rechazan la carga.

## 2. Cargar los CSV

### PostgreSQL

``` sql
\copy departamento FROM 'datos/departamento.csv' CSV HEADER
\copy municipio FROM 'datos/municipio.csv' CSV HEADER
\copy zona FROM 'datos/zona.csv' CSV HEADER
\copy restaurante FROM 'datos/restaurante.csv' CSV HEADER
\copy cliente FROM 'datos/cliente.csv' CSV HEADER
\copy pedido FROM 'datos/pedido.csv' CSV HEADER
```

### MySQL / MariaDB

``` sql
LOAD DATA LOCAL INFILE 'datos/pedido.csv'
INTO TABLE pedido
FIELDS TERMINATED BY ','
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;
```

Si da error de permisos: arranque el cliente con
`mysql --local-infile=1`.

### SQL Server

``` sql
BULK INSERT pedido
FROM 'C:\ruta\datos\pedido.csv'
WITH (FORMAT='CSV', FIRSTROW=2);
```

### DuckDB

``` sql
CREATE TABLE pedido AS SELECT * FROM read_csv_auto('datos/pedido.csv');
```

Detecta los tipos solo. No hace falta el `CREATE TABLE` previo.

### SQLite

``` text
.mode csv
.import datos/pedido.csv pedido
```

## 3. Medir el tiempo de una consulta

  Motor        Cómo activarlo
  ------------ --------------------------------------------------------
  PostgreSQL   `\timing on` --- o `EXPLAIN ANALYZE <consulta>;`
  MySQL        el cliente muestra el tiempo al final de cada consulta
  SQL Server   `SET STATISTICS TIME ON;`
  DuckDB       `.timer on`
  SQLite       `.timer on`

### Tres reglas para que la medición sirva

1.  Descarte la primera corrida. La primera vez el motor lee de disco;
    las siguientes ya tiene los datos en memoria. Mida a partir de la
    segunda.
2.  Corra cada consulta 5 veces y use la mediana, no el promedio. Un
    pico aislado no debe decidir su conclusión.
3.  Verifique que ambos modelos devuelven exactamente el mismo
    resultado. Si los números no coinciden, no está midiendo lo mismo y
    la comparación no vale.

## 4. Medir el espacio en disco

  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Motor                               Consulta
  ----------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------
  PostgreSQL                          `SELECT pg_size_pretty(pg_total_relation_size('pedido'));`

  MySQL                               `SELECT table_name, ROUND((data_length+index_length)/1024/1024,1) AS mb FROM information_schema.tables WHERE table_schema = DATABASE();`

  SQL Server                          `EXEC sp_spaceused 'pedido';`

  DuckDB                              `SELECT table_name, estimated_size FROM duckdb_tables();`

  SQLite                              tamaño del archivo `.db` antes y después
  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Para comparar de forma justa: sume el tamaño de todas las tablas del
modelo normalizado y compárelo contra la tabla desnormalizada.

## 5. Lo que debe entregar

Por cada decisión de desnormalización que tomó:

-   Qué consulta mejora y en cuánto, con sus números medidos.
-   Qué redundancia introduce y cuánto espacio costó.
-   Qué riesgo asume, y por qué lo acepta.

**Una comparación sin números medidos no cuenta: es una suposición, no
una justificación.**

### Nota sobre volumen

Con menos de un millón de filas en `pedido`, las diferencias de tiempo
no se van a notar y su comparación no dirá nada. El generador viene
configurado en 3 millones; si su equipo lo soporta, súbalo.
