#!/usr/bin/env python3
"""Tarea 05: mide 3FN vs modelo dimensional (grano correcto).

Protocolo (misma guía de medición de la clase 04):
  1) Descartar la 1ª corrida (cold)
  2) 5 corridas calientes → mediana
  3) Verificar mismos resultados (fingerprint MD5)

Salida: docs/05/procedimiento/comparaciones.md
        docs/05/procedimiento/raw_mediciones.json
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "05" / "procedimiento"
RAW_JSON = OUT_DIR / "raw_mediciones.json"
MD_OUT = OUT_DIR / "comparaciones.md"

PG = [
    "docker",
    "compose",
    "exec",
    "-T",
    "postgres",
    "psql",
    "-U",
    "ruta_verde",
    "-d",
    "ruta_verde",
    "-v",
    "ON_ERROR_STOP=1",
    "-q",
    "-t",
    "-A",
]


def psql(sql: str) -> str:
    r = subprocess.run(
        PG + ["-c", sql],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if r.returncode != 0:
        raise RuntimeError(f"psql error:\n{r.stderr}\nSQL:\n{sql}")
    return r.stdout.strip()


def explain_ms(sql: str) -> float:
    wrapped = f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}"
    out = psql(wrapped)
    data = json.loads(out)
    return float(data[0]["Execution Time"])


def median_ms(sql: str, runs: int = 6) -> dict:
    times = [explain_ms(sql) for _ in range(runs)]
    hot = times[1:]
    return {
        "all_ms": [round(t, 3) for t in times],
        "cold_ms": round(times[0], 3),
        "hot_ms": [round(t, 3) for t in hot],
        "median_ms": round(statistics.median(hot), 3),
        "min_ms": round(min(hot), 3),
        "max_ms": round(max(hot), 3),
    }


def fetch_fingerprint(sql: str) -> str:
    wrap = f"""
    SELECT md5(string_agg(row_hash, '' ORDER BY row_hash))
    FROM (
      SELECT md5(CAST(t AS text)) AS row_hash
      FROM ({sql}) AS t
    ) s;
    """
    return psql(wrap)


def table_sizes() -> list[dict]:
    sql = """
    SELECT relname,
           pg_total_relation_size(c.oid)::BIGINT,
           pg_size_pretty(pg_total_relation_size(c.oid))
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'm')
    ORDER BY pg_total_relation_size(c.oid) DESC;
    """
    rows = []
    for line in psql(sql).splitlines():
        if not line.strip():
            continue
        name, bytes_, pretty = line.split("|")
        rows.append({"tabla": name, "bytes": int(bytes_), "pretty": pretty})
    return rows


def pretty_bytes(n: int) -> str:
    return psql(f"SELECT pg_size_pretty({n}::BIGINT);")


def speedup(base: float, other: float) -> str:
    if other <= 0 or base <= 0:
        return "n/a"
    if other < base:
        factor = base / other
        pct = (1 - other / base) * 100
        return f"{factor:.2f}x más rápida ({pct:.1f}% menos tiempo)"
    if other > base:
        factor = other / base
        pct = (other / base - 1) * 100
        return f"{factor:.2f}x más lenta ({pct:.1f}% más tiempo)"
    return "empate"


QUERIES = {
    "Q1_ventas_zona_mes": {
        "titulo": "Ventas totales por zona y mes (dashboard gerencial)",
        "nota": "Mismo patrón de la clase 04. El dimensional NO cambia el grano: agrega en query time. La tabla agregada SÍ cambia el grano (otra tabla).",
        "normalizado": """
            SELECT z.zona_id, z.nombre AS zona_nombre,
                   to_char(p.fecha, 'YYYY-MM') AS anio_mes,
                   COUNT(*)::BIGINT AS n_pedidos,
                   SUM(p.total) AS ventas_totales
            FROM pedido p
            JOIN restaurante r ON r.restaurante_id = p.restaurante_id
            JOIN zona z ON z.zona_id = r.zona_id
            WHERE p.estado = 'entregado'
            GROUP BY z.zona_id, z.nombre, to_char(p.fecha, 'YYYY-MM')
            ORDER BY z.zona_id, anio_mes
        """,
        "dimensional": """
            SELECT dr.zona_id, dr.zona_nombre, df.anio_mes,
                   SUM(f.n_pedidos)::BIGINT AS n_pedidos,
                   SUM(f.total) AS ventas_totales
            FROM hechos_pedidos f
            JOIN dim_restaurante dr ON dr.restaurante_id = f.restaurante_id
            JOIN dim_fecha df ON df.fecha_id = f.fecha_id
            WHERE f.estado_id = 'entregado'
            GROUP BY dr.zona_id, dr.zona_nombre, df.anio_mes
            ORDER BY dr.zona_id, df.anio_mes
        """,
        "agregada": """
            SELECT zona_id, zona_nombre, anio_mes,
                   n_pedidos, ventas_totales
            FROM hechos_ventas_zona_mes
            ORDER BY zona_id, anio_mes
        """,
        "fingerprint_keys": ["normalizado", "dimensional", "agregada"],
    },
    "Q2_ventas_departamento_mes": {
        "titulo": "Ventas por departamento y mes (rollup geográfico)",
        "nota": "El pre-join vive en dim_restaurante (2 500 filas), no repetido en 3M hechos.",
        "normalizado": """
            SELECT d.departamento_id, d.nombre AS departamento_nombre,
                   to_char(p.fecha, 'YYYY-MM') AS anio_mes,
                   COUNT(*)::BIGINT AS n_pedidos,
                   SUM(p.total) AS ventas_totales
            FROM pedido p
            JOIN restaurante r ON r.restaurante_id = p.restaurante_id
            JOIN zona z ON z.zona_id = r.zona_id
            JOIN municipio m ON m.municipio_id = z.municipio_id
            JOIN departamento d ON d.departamento_id = m.departamento_id
            WHERE p.estado = 'entregado'
            GROUP BY d.departamento_id, d.nombre, to_char(p.fecha, 'YYYY-MM')
            ORDER BY d.departamento_id, anio_mes
        """,
        "dimensional": """
            SELECT dr.departamento_id, dr.departamento_nombre, df.anio_mes,
                   SUM(f.n_pedidos)::BIGINT AS n_pedidos,
                   SUM(f.total) AS ventas_totales
            FROM hechos_pedidos f
            JOIN dim_restaurante dr ON dr.restaurante_id = f.restaurante_id
            JOIN dim_fecha df ON df.fecha_id = f.fecha_id
            WHERE f.estado_id = 'entregado'
            GROUP BY dr.departamento_id, dr.departamento_nombre, df.anio_mes
            ORDER BY dr.departamento_id, df.anio_mes
        """,
        "agregada": """
            SELECT departamento_id, departamento_nombre, anio_mes,
                   SUM(n_pedidos)::BIGINT AS n_pedidos,
                   SUM(ventas_totales) AS ventas_totales
            FROM hechos_ventas_zona_mes
            GROUP BY departamento_id, departamento_nombre, anio_mes
            ORDER BY departamento_id, anio_mes
        """,
        "fingerprint_keys": ["normalizado", "dimensional", "agregada"],
    },
    "Q3_top_zonas_2025q1": {
        "titulo": "Top 20 zonas por ventas en 2025-Q1",
        "nota": "Filtro temporal selectivo. La agregada gana porque el grain zona×mes ya está materializado.",
        "normalizado": """
            SELECT z.zona_id, z.nombre AS zona_nombre,
                   SUM(p.total) AS ventas_totales,
                   COUNT(*)::BIGINT AS n_pedidos
            FROM pedido p
            JOIN restaurante r ON r.restaurante_id = p.restaurante_id
            JOIN zona z ON z.zona_id = r.zona_id
            WHERE p.estado = 'entregado'
              AND p.fecha >= DATE '2025-01-01'
              AND p.fecha <  DATE '2025-04-01'
            GROUP BY z.zona_id, z.nombre
            ORDER BY ventas_totales DESC, z.zona_id
            LIMIT 20
        """,
        "dimensional": """
            SELECT dr.zona_id, dr.zona_nombre,
                   SUM(f.total) AS ventas_totales,
                   SUM(f.n_pedidos)::BIGINT AS n_pedidos
            FROM hechos_pedidos f
            JOIN dim_restaurante dr ON dr.restaurante_id = f.restaurante_id
            JOIN dim_fecha df ON df.fecha_id = f.fecha_id
            WHERE f.estado_id = 'entregado'
              AND df.fecha >= DATE '2025-01-01'
              AND df.fecha <  DATE '2025-04-01'
            GROUP BY dr.zona_id, dr.zona_nombre
            ORDER BY ventas_totales DESC, dr.zona_id
            LIMIT 20
        """,
        "agregada": """
            SELECT zona_id, zona_nombre,
                   SUM(ventas_totales) AS ventas_totales,
                   SUM(n_pedidos)::BIGINT AS n_pedidos
            FROM hechos_ventas_zona_mes
            WHERE anio_mes IN ('2025-01', '2025-02', '2025-03')
            GROUP BY zona_id, zona_nombre
            ORDER BY ventas_totales DESC, zona_id
            LIMIT 20
        """,
        "fingerprint_keys": ["normalizado", "dimensional", "agregada"],
    },
    "Q4_segmento_dia_semana": {
        "titulo": "Ventas por segmento de cliente y día de la semana",
        "nota": "Pregunta que el grano zona×mes NO puede responder. Solo 3FN y el hecho transaccional. Demuestra que el grano es irreversible.",
        "normalizado": """
            SELECT c.segmento,
                   EXTRACT(ISODOW FROM p.fecha)::INT AS dia_semana,
                   COUNT(*)::BIGINT AS n_pedidos,
                   SUM(p.total) AS ventas_totales
            FROM pedido p
            JOIN cliente c ON c.cliente_id = p.cliente_id
            WHERE p.estado = 'entregado'
            GROUP BY c.segmento, EXTRACT(ISODOW FROM p.fecha)
            ORDER BY c.segmento, dia_semana
        """,
        "dimensional": """
            SELECT dc.segmento, df.dia_semana,
                   SUM(f.n_pedidos)::BIGINT AS n_pedidos,
                   SUM(f.total) AS ventas_totales
            FROM hechos_pedidos f
            JOIN dim_cliente dc ON dc.cliente_id = f.cliente_id
            JOIN dim_fecha df ON df.fecha_id = f.fecha_id
            WHERE f.estado_id = 'entregado'
            GROUP BY dc.segmento, df.dia_semana
            ORDER BY dc.segmento, df.dia_semana
        """,
        "fingerprint_keys": ["normalizado", "dimensional"],
    },
}


def render_md(payload: dict) -> str:
    lines = []
    lines.append("# Comparaciones Tarea 05: 3FN vs modelo dimensional")
    lines.append("")
    lines.append(f"**Fecha de medición:** {payload['timestamp']}")
    lines.append("**Motor:** PostgreSQL 16 (Docker)")
    lines.append(f"**Volumen:** {payload['n_pedidos']:,} filas en `pedido` / `hechos_pedidos`")
    lines.append("")
    lines.append("## Protocolo de tiempo")
    lines.append("")
    lines.append("1. Se descarta la primera corrida (cold cache).")
    lines.append("2. Se reporta la **mediana** de 5 corridas calientes.")
    lines.append("3. Equivalencia verificada con fingerprint MD5 del result set.")
    lines.append("4. Tiempo = `EXPLAIN (ANALYZE, FORMAT JSON)` → `Execution Time`.")
    lines.append("")
    lines.append("## Espacio en disco")
    lines.append("")
    lines.append("| Tabla / objeto | Tamaño |")
    lines.append("|----------------|--------|")
    for t in payload["sizes"]:
        lines.append(f"| `{t['tabla']}` | {t['pretty']} |")
    lines.append("")
    lines.append(f"- **Suma 3FN** (departamento+municipio+zona+restaurante+cliente+pedido): **{payload['size_3fn_pretty']}**")
    lines.append(f"- **Suma dimensional transaccional** (dims + `hechos_pedidos`): **{payload['size_dim_pretty']}**")
    lines.append(f"- **`hechos_ventas_zona_mes` (agregada, otro grano):** **{payload['size_agg_pretty']}**")
    lines.append("")

    for qid, q in payload["queries"].items():
        lines.append(f"## {qid}: {q['titulo']}")
        lines.append("")
        lines.append(f"**Nota de grano:** {q['nota']}")
        lines.append("")
        lines.append(f"**Equivalencia:** {q['equivalence']}")
        lines.append("")
        lines.append("| Variante | Mediana (ms) | Min | Max | Cold |")
        lines.append("|----------|-------------:|----:|----:|-----:|")
        for variant, m in q["mediciones"].items():
            lines.append(
                f"| {variant} | {m['median_ms']:.3f} | {m['min_ms']:.3f} | "
                f"{m['max_ms']:.3f} | {m['cold_ms']:.3f} |"
            )
        lines.append("")
        base = q["mediciones"]["normalizado"]["median_ms"]
        lines.append("### Ganancia vs 3FN")
        lines.append("")
        for variant, m in q["mediciones"].items():
            if variant == "normalizado":
                continue
            lines.append(f"- **{variant}:** {speedup(base, m['median_ms'])}")
        lines.append("")

    lines.append("## Lectura de los tiempos (lo que pide la guía)")
    lines.append("")
    lines.append(
        "La clase 05 no pide un motor concreto, pero sí que el grano y las "
        "desnormalizaciones se justifiquen. Los tiempos muestran que:"
    )
    lines.append("")
    lines.append(
        "1. **Desnormalizar la dimensión** (`dim_restaurante`) no replica geo en 3M filas; "
        "el hecho sigue delgado. El costo de espacio extra está en las dims, no en un mart ancho."
    )
    lines.append(
        "2. **La tabla agregada** es otra tabla de hechos, otro grano. Gana órdenes de magnitud "
        "en Q1–Q3 porque ya no recorre 3M pedidos. No se usa para Q4: esa pregunta exige el grano fino."
    )
    lines.append(
        "3. **Q4 no tiene variante agregada** a propósito: si el grano fuera zona×mes, "
        "«ventas por segmento y día de la semana» ya no tendría respuesta. Eso es lo que "
        "la guía llama grano irreversible."
    )
    lines.append("")
    lines.append(f"_Raw JSON: `{RAW_JSON.relative_to(ROOT).as_posix()}`_")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Contando pedidos...")
    n_pedidos = int(psql("SELECT COUNT(*) FROM pedido;"))
    n_hechos = int(psql("SELECT COUNT(*) FROM hechos_pedidos;"))
    print(f"  pedido={n_pedidos:,}  hechos_pedidos={n_hechos:,}")
    if n_pedidos != n_hechos:
        raise SystemExit("hechos_pedidos no tiene el mismo grano/conteo que pedido")
    if n_pedidos < 1_000_000:
        print("ADVERTENCIA: < 1M filas; las diferencias pueden no notarse.", file=sys.stderr)

    print("Tamaños...")
    sizes = table_sizes()
    by_name = {s["tabla"]: s for s in sizes}

    def sz(name: str) -> int:
        return by_name.get(name, {"bytes": 0})["bytes"]

    size_3fn = sum(
        sz(t)
        for t in (
            "departamento",
            "municipio",
            "zona",
            "restaurante",
            "cliente",
            "pedido",
        )
    )
    size_dim = sum(
        sz(t)
        for t in (
            "dim_fecha",
            "dim_cliente",
            "dim_restaurante",
            "dim_estado",
            "hechos_pedidos",
        )
    )

    results = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "n_pedidos": n_pedidos,
        "sizes": sizes,
        "size_3fn_bytes": size_3fn,
        "size_3fn_pretty": pretty_bytes(size_3fn),
        "size_dim_bytes": size_dim,
        "size_dim_pretty": pretty_bytes(size_dim),
        "size_agg_pretty": by_name.get("hechos_ventas_zona_mes", {}).get("pretty", "n/a"),
        "queries": {},
    }

    for qid, qdef in QUERIES.items():
        print(f"\n=== {qid} ===")
        variants = {
            k: qdef[k]
            for k in ("normalizado", "dimensional", "agregada")
            if k in qdef
        }
        fps = {}
        for key in qdef["fingerprint_keys"]:
            print(f"  fingerprint {key}...")
            fps[key] = fetch_fingerprint(variants[key])
        ok = len(set(fps.values())) == 1
        equivalence = "OK — mismo fingerprint" if ok else f"FAIL — {fps}"
        print(f"  equivalencia: {equivalence}")
        if not ok:
            raise SystemExit(f"Resultados no equivalentes en {qid}: {fps}")

        mediciones = {}
        for name, sql in variants.items():
            print(f"  midiendo {name}...")
            mediciones[name] = median_ms(sql)
            print(f"    mediana={mediciones[name]['median_ms']} ms")

        results["queries"][qid] = {
            "titulo": qdef["titulo"],
            "nota": qdef["nota"],
            "equivalence": equivalence,
            "fingerprints": fps,
            "mediciones": mediciones,
        }

    RAW_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUT.write_text(render_md(results), encoding="utf-8")
    print(f"\nEscrito: {MD_OUT}")
    print(f"Escrito: {RAW_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
