#!/usr/bin/env python3
"""Mide consultas normalizado vs desnormalizado (protocolo docs/GUIA).

Reglas:
  1) Descartar la 1ª corrida (cold)
  2) 5 corridas calientes → mediana
  3) Verificar mismos resultados entre modelos

Salida: docs/procedimiento/comparaciones.md + docs/procedimiento/raw_mediciones.json
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "procedimiento"
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
    """Tiempo total de ejecución vía EXPLAIN (ANALYZE, FORMAT JSON)."""
    wrapped = f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}"
    out = psql(wrapped)
    # psql -t -A puede devolver JSON multilinea; unir
    data = json.loads(out)
    return float(data[0]["Execution Time"])


def median_ms(sql: str, runs: int = 6) -> dict:
    times = [explain_ms(sql) for _ in range(runs)]
    hot = times[1:]  # descarta cold
    return {
        "all_ms": [round(t, 3) for t in times],
        "cold_ms": round(times[0], 3),
        "hot_ms": [round(t, 3) for t in hot],
        "median_ms": round(statistics.median(hot), 3),
        "min_ms": round(min(hot), 3),
        "max_ms": round(max(hot), 3),
    }


def fetch_fingerprint(sql: str) -> str:
    """Hash estable del resultado completo para verificar equivalencia."""
    # md5 de cada fila concatenada, luego md5 del agregado ordenado
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


# --- Consultas de negocio (comparables entre modelos) ---------------------

QUERIES = {
    "Q1_ventas_zona_mes": {
        "titulo": "Ventas totales por zona y mes (dashboard gerencial)",
        "tecnica": "Pre-join + columna derivada `anio_mes` / Tabla agregada / MV",
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
        "prejoin": """
            SELECT zona_id, zona_nombre, anio_mes,
                   COUNT(*)::BIGINT AS n_pedidos,
                   SUM(total) AS ventas_totales
            FROM mart_pedido_geo
            WHERE estado = 'entregado'
            GROUP BY zona_id, zona_nombre, anio_mes
            ORDER BY zona_id, anio_mes
        """,
        "agregada": """
            SELECT zona_id, zona_nombre, anio_mes,
                   n_pedidos, ventas_totales
            FROM agg_ventas_zona_mes
            ORDER BY zona_id, anio_mes
        """,
        "mv": """
            SELECT zona_id, zona_nombre, anio_mes,
                   n_pedidos, ventas_totales
            FROM mv_ventas_zona_mes
            ORDER BY zona_id, anio_mes
        """,
        # Para fingerprint: misma proyección en todos
        "fingerprint_keys": ["normalizado", "prejoin", "agregada", "mv"],
    },
    "Q2_ventas_departamento_mes": {
        "titulo": "Ventas por departamento y mes (rollup geográfico)",
        "tecnica": "Pre-join (elimina 4 joins) vs joins normalizados",
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
        "prejoin": """
            SELECT departamento_id, departamento_nombre, anio_mes,
                   COUNT(*)::BIGINT AS n_pedidos,
                   SUM(total) AS ventas_totales
            FROM mart_pedido_geo
            WHERE estado = 'entregado'
            GROUP BY departamento_id, departamento_nombre, anio_mes
            ORDER BY departamento_id, anio_mes
        """,
        "agregada": """
            SELECT departamento_id, departamento_nombre, anio_mes,
                   SUM(n_pedidos)::BIGINT AS n_pedidos,
                   SUM(ventas_totales) AS ventas_totales
            FROM agg_ventas_zona_mes
            GROUP BY departamento_id, departamento_nombre, anio_mes
            ORDER BY departamento_id, anio_mes
        """,
        "fingerprint_keys": ["normalizado", "prejoin", "agregada"],
    },
    "Q3_top_zonas_ultimo_trimestre": {
        "titulo": "Top 20 zonas por ventas en un trimestre fijo",
        "tecnica": "Pre-join + filtro sobre columna derivada / agregada filtrada",
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
        "prejoin": """
            SELECT zona_id, zona_nombre,
                   SUM(total) AS ventas_totales,
                   COUNT(*)::BIGINT AS n_pedidos
            FROM mart_pedido_geo
            WHERE estado = 'entregado'
              AND fecha >= DATE '2025-01-01'
              AND fecha <  DATE '2025-04-01'
            GROUP BY zona_id, zona_nombre
            ORDER BY ventas_totales DESC, zona_id
            LIMIT 20
        """,
        "agregada": """
            SELECT zona_id, zona_nombre,
                   SUM(ventas_totales) AS ventas_totales,
                   SUM(n_pedidos)::BIGINT AS n_pedidos
            FROM agg_ventas_zona_mes
            WHERE anio_mes IN ('2025-01', '2025-02', '2025-03')
            GROUP BY zona_id, zona_nombre
            ORDER BY ventas_totales DESC, zona_id
            LIMIT 20
        """,
        "fingerprint_keys": ["normalizado", "prejoin", "agregada"],
    },
}


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
        return f"{factor:.2f}x más lenta ({pct:.1f}% más tiempo) — no justifica esta técnica aquí"
    return "empate"


def render_md(payload: dict) -> str:
    lines = []
    lines.append("# Comparaciones: modelo normalizado vs desnormalizado")
    lines.append("")
    lines.append(f"**Fecha de medición:** {payload['timestamp']}")
    lines.append(f"**Motor:** PostgreSQL 16 (Docker)")
    lines.append(f"**Volumen:** {payload['n_pedidos']:,} filas en `pedido`")
    lines.append("")
    lines.append("## Protocolo")
    lines.append("")
    lines.append("Según `docs/GUIA/GUIA.md`:")
    lines.append("")
    lines.append("1. Se descarta la primera corrida (cold cache).")
    lines.append("2. Se reporta la **mediana** de 5 corridas calientes.")
    lines.append("3. Se verifica equivalencia de resultados con fingerprint MD5 del result set.")
    lines.append("4. Tiempo medido con `EXPLAIN (ANALYZE, FORMAT JSON)` → `Execution Time`.")
    lines.append("")
    lines.append("## Espacio en disco")
    lines.append("")
    lines.append("| Tabla / objeto | Tamaño |")
    lines.append("|----------------|--------|")
    for t in payload["sizes"]:
        lines.append(f"| `{t['tabla']}` | {t['pretty']} |")
    lines.append("")
    lines.append(
        f"- **Suma modelo normalizado** "
        f"(`departamento`+`municipio`+`zona`+`restaurante`+`cliente`+`pedido`): "
        f"**{payload['size_normalizado_pretty']}**"
    )
    lines.append(
        f"- **`mart_pedido_geo` (pre-join):** **{payload['size_prejoin_pretty']}**"
    )
    lines.append(
        f"- **`agg_ventas_zona_mes` (agregada):** **{payload['size_agg_pretty']}**"
    )
    lines.append(
        f"- **`mv_ventas_zona_mes` (MV):** **{payload['size_mv_pretty']}**"
    )
    lines.append("")

    for qid, q in payload["queries"].items():
        lines.append(f"## {qid}: {q['titulo']}")
        lines.append("")
        lines.append(f"**Técnica(s):** {q['tecnica']}")
        lines.append("")
        lines.append(f"**Equivalencia de resultados:** {q['equivalence']}")
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
        lines.append("### Ganancia vs normalizado")
        lines.append("")
        for variant, m in q["mediciones"].items():
            if variant == "normalizado":
                continue
            lines.append(f"- **{variant}:** {speedup(base, m['median_ms'])}")
        lines.append("")
        lines.append("### Trade-off documentado")
        lines.append("")
        for bullet in q["tradeoff"]:
            lines.append(f"- {bullet}")
        lines.append("")

    lines.append("## Decisiones y riesgos (resumen)")
    lines.append("")
    lines.append("| Decisión | Consulta que mejora | Costo de espacio | Riesgo asumido | ¿Por qué se acepta? |")
    lines.append("|----------|---------------------|------------------|----------------|---------------------|")
    for row in payload["decisiones"]:
        lines.append(
            f"| {row['decision']} | {row['consulta']} | {row['espacio']} | "
            f"{row['riesgo']} | {row['porque']} |"
        )
    lines.append("")
    lines.append("## Nota sobre consultas del reto de clase")
    lines.append("")
    lines.append(
        "El esquema entregado en la guía (`pedido`, `restaurante`, jerarquía geográfica, `cliente`) "
        "**no incluye** `repartidor`, tiempos de entrega ni `detalle_pedido`/`producto`. "
        "Por eso las consultas 2 y 3 del reto de diapositivas (tiempo por repartidor; products bought together) "
        "no se midieron aquí: requerirían ampliar el generador y el modelo. "
        "La consulta 1 del reto (ventas por zona y mes) sí se midió como **Q1**."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"_Raw JSON: `{RAW_JSON.relative_to(ROOT).as_posix()}`_")
    lines.append("")
    return "\n".join(lines)


def pretty_bytes(n: int) -> str:
    out = psql(f"SELECT pg_size_pretty({n}::BIGINT);")
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Contando pedidos...")
    n_pedidos = int(psql("SELECT COUNT(*) FROM pedido;"))
    print(f"  pedido = {n_pedidos:,}")
    if n_pedidos < 1_000_000:
        print(
            "ADVERTENCIA: < 1M filas; la guía indica que las diferencias pueden no notarse.",
            file=sys.stderr,
        )

    print("Tamaños de relación...")
    sizes = table_sizes()
    by_name = {s["tabla"]: s for s in sizes}

    def sz(name: str) -> int:
        return by_name.get(name, {"bytes": 0})["bytes"]

    norm_tables = [
        "departamento",
        "municipio",
        "zona",
        "restaurante",
        "cliente",
        "pedido",
    ]
    size_norm = sum(sz(t) for t in norm_tables)

    results = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "n_pedidos": n_pedidos,
        "sizes": sizes,
        "size_normalizado_bytes": size_norm,
        "size_normalizado_pretty": pretty_bytes(size_norm),
        "size_prejoin_pretty": by_name.get("mart_pedido_geo", {}).get("pretty", "n/a"),
        "size_agg_pretty": by_name.get("agg_ventas_zona_mes", {}).get("pretty", "n/a"),
        "size_mv_pretty": by_name.get("mv_ventas_zona_mes", {}).get("pretty", "n/a"),
        "queries": {},
        "decisiones": [],
    }

    tradeoffs = {
        "Q1_ventas_zona_mes": [
            "**Qué gana:** el dashboard deja de recorrer millones de pedidos con 2–4 joins.",
            "**Redundancia:** nombres de zona/restaurante/depto repetidos (pre-join) o métricas materializadas (agg/MV).",
            "**Riesgo:** si cambia el nombre de una zona o se corrige un `total`, hay que refrescar mart/agg/MV; datos stale hasta el refresh.",
            "**Se acepta** porque es consulta diaria de gerencia y el warehouse puede regenerarse desde el modelo normalizado.",
        ],
        "Q2_ventas_departamento_mes": [
            "**Qué gana:** elimina la cadena de joins geográficos en cada ejecución.",
            "**Redundancia:** `departamento_nombre` (y resto de jerarquía) denormalizado en el mart; o rollup desde la agregada.",
            "**Riesgo:** inconsistencia si la jerarquía geográfica se reclasifica (un municipio cambia de departamento) y no se regenera el mart.",
            "**Se acepta** en la capa de consumo (mart); el core sigue normalizado.",
        ],
        "Q3_top_zonas_ultimo_trimestre": [
            "**Qué gana:** ranking trimestral sin escanear todo `pedido` con joins (sobre todo vía tabla agregada por mes).",
            "**Redundancia:** misma del mart/agg; el filtro trimestral sobre `anio_mes` evita recalcular `to_char` sobre cada fila cruda si se usa la agregada.",
            "**Riesgo:** fan-out no aplica aquí (grain pedido o zona-mes es correcto); el riesgo es frescura del agregado.",
            "**Se acepta** para reportes periódicos; no para exploración ad-hoc sin patrón fijo.",
        ],
    }

    for qid, qdef in QUERIES.items():
        print(f"\n=== {qid} ===")
        variants = {
            k: qdef[k]
            for k in ("normalizado", "prejoin", "agregada", "mv")
            if k in qdef
        }

        # Equivalencia
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
            "tecnica": qdef["tecnica"],
            "equivalence": equivalence,
            "fingerprints": fps,
            "mediciones": mediciones,
            "tradeoff": tradeoffs[qid],
        }

    # Filas de decisiones para la tabla resumen (usa Q1 como ancla principal)
    q1 = results["queries"]["Q1_ventas_zona_mes"]["mediciones"]
    results["decisiones"] = [
        {
            "decision": "A — Pre-join + columnas derivadas (`mart_pedido_geo`)",
            "consulta": f"Q1/Q2/Q3 — mediana Q1 {q1['prejoin']['median_ms']} ms vs {q1['normalizado']['median_ms']} ms",
            "espacio": results["size_prejoin_pretty"],
            "riesgo": "Redundancia de nombres; hay que regenerar si cambia la dimensión geográfica o un pedido",
            "porque": "Acelera lecturas geográficas recurrentes; el normalizado sigue siendo fuente de verdad",
        },
        {
            "decision": "B — Tabla agregada (`agg_ventas_zona_mes`)",
            "consulta": f"Q1 — mediana {q1['agregada']['median_ms']} ms vs {q1['normalizado']['median_ms']} ms",
            "espacio": results["size_agg_pretty"],
            "riesgo": "Granularidad fija zona×mes: no responde preguntas a nivel pedido sin volver al detalle",
            "porque": "El dashboard solo necesita ese grain; el costo de espacio es mínimo vs escanear 3M filas",
        },
        {
            "decision": "C — Vista materializada (`mv_ventas_zona_mes`)",
            "consulta": f"Q1 — mediana {q1['mv']['median_ms']} ms vs {q1['normalizado']['median_ms']} ms",
            "espacio": results["size_mv_pretty"],
            "riesgo": "Hay que definir política de `REFRESH MATERIALIZED VIEW` (datos stale)",
            "porque": "Misma ganancia que la agregada, pero declarativa y versionable en SQL",
        },
    ]

    RAW_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUT.write_text(render_md(results), encoding="utf-8")
    print(f"\nEscrito: {MD_OUT}")
    print(f"Escrito: {RAW_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
