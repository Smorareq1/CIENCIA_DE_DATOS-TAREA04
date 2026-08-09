# Procedimiento del laboratorio — Desnormalización Ruta Verde

## Objetivo

Partir del modelo **normalizado (3FN)** de la guía, aplicar técnicas de
desnormalización de forma controlada, **medir** tiempo y espacio, y documentar
por cada decisión: qué consulta mejora, qué redundancia introduce y qué riesgo
asume.

## Entorno

| Elemento | Valor |
|----------|-------|
| Motor | PostgreSQL 16 (Docker Compose) |
| Base / usuario / pass | `ruta_verde` / `ruta_verde` / `ruta_verde` |
| Volumen de prueba | **3,000,000** filas en `pedido` |
| Helper | `scripts/db.ps1` |
| Medición | `scripts/benchmark.py` |

## Pasos ejecutados

### 1. Generar datos normalizados

```powershell
.\scripts\db.ps1 generate -Pedidos 3000000
```

Produce CSVs en `datos/` (`departamento`, `municipio`, `zona`, `restaurante`,
`cliente`, `pedido`).

### 2. Levantar Postgres y cargar el modelo 3FN

```powershell
.\scripts\db.ps1 up
.\scripts\db.ps1 load
```

- Schema: `sql/01_schema_normalizado.sql`
- Carga: `sql/02_load_normalizado.sql` (`TRUNCATE` + `COPY`)

### 3. Construir modelos desnormalizados

```powershell
docker compose exec -T postgres psql -U ruta_verde -d ruta_verde -f /sql/03_schema_desnormalizado.sql
```

| Objeto | Técnica | Descripción |
|--------|---------|-------------|
| `mart_pedido_geo` | Pre-join + columnas derivadas | Pedido aplanado con zona/municipio/depto + `anio_mes` + `dia_semana` |
| `agg_ventas_zona_mes` | Tabla agregada | Grain zona × mes, solo `estado = 'entregado'` |
| `mv_ventas_zona_mes` | Vista materializada | Misma agregación que el dashboard, refresco explícito |

El core (`pedido`, dimensiones) **no se toca**: la desnormalización vive en la
capa de consumo (marts).

### 4. Consultas de negocio medidas

| ID | Consulta | Por qué |
|----|----------|---------|
| Q1 | Ventas totales por zona y mes | Dashboard gerencial (reto de clase #1) |
| Q2 | Ventas por departamento y mes | Rollup geográfico con cadena de joins |
| Q3 | Top 20 zonas en 2025-Q1 | Ranking con filtro temporal |

### 5. Protocolo de medición (guía)

1. Descartar la 1ª corrida (cold).
2. 5 corridas calientes → **mediana**.
3. Verificar que todas las variantes devuelven el **mismo resultado** (fingerprint MD5).
4. Tiempo = `EXPLAIN (ANALYZE)` → `Execution Time`.

```powershell
python scripts/benchmark.py
```

### 6. Empezar de cero (si hace falta)

```powershell
.\scripts\db.ps1 reset          # borra volumen Docker + recarga CSVs
# luego reconstruir desnormalizado:
docker compose exec -T postgres psql -U ruta_verde -d ruta_verde -f /sql/03_schema_desnormalizado.sql
python scripts/benchmark.py
```

## Artefactos

| Archivo | Contenido |
|---------|-----------|
| [comparaciones.md](./comparaciones.md) | Tablas de tiempo, espacio, trade-offs y decisiones |
| [raw_mediciones.json](./raw_mediciones.json) | Mediciones crudas reproducibles |
| `sql/03_schema_desnormalizado.sql` | DDL/DML de los marts |
| `scripts/benchmark.py` | Runner del protocolo |

## Conclusión operativa (antes del detalle numérico)

1. **Tabla agregada / MV** ganan por órdenes de magnitud en el dashboard (Q1) con
   costo de espacio irrisorio (~2 MB vs 339 MB del modelo normalizado).
2. **Pre-join** ayuda cuando la consulta recorre muchos joins sobre todo el
   historial (Q1, Q2), pero **puede empeorar** si el mart es más ancho y la
   consulta ya filtra bien sobre el modelo estrecho (Q3).
3. Desnormalizar sin medir habría sido una suposición: en Q3 el pre-join
   **no** se justifica.
