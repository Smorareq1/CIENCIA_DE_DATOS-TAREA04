#!/usr/bin/env python3
"""Tarea 06: drill-across vs JOIN ilegal, medidas no aditivas, 3FN vs estrella vs agregada.

Protocolo de tiempo (misma guía de medición):
  1) Descartar la 1ª corrida (cold)
  2) 5 corridas calientes → mediana
  3) Fingerprint solo cuando las variantes DEBEN coincidir

Salida: docs/06/procedimiento/comparaciones.md
        docs/06/procedimiento/raw_mediciones.json
"""

from __future__ import annotations

import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "06" / "procedimiento"
RAW_JSON = OUT_DIR / "raw_mediciones.json"
MD_OUT = OUT_DIR / "comparaciones.md"

PG = [
    "docker", "compose", "exec", "-T", "postgres",
    "psql", "-U", "ruta_verde", "-d", "ruta_verde",
    "-v", "ON_ERROR_STOP=1", "-q", "-t", "-A",
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
    data = json.loads(psql(f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}"))
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


SQL_WRONG = """
            SELECT dr.zona_id, df.anio_mes,
                   SUM(fp.total) AS ventas,
                   SUM(hc.monto) AS cobrado
            FROM hechos_pedidos fp
            JOIN hechos_cobros hc ON hc.pedido_id = fp.pedido_id
            JOIN dim_restaurante dr ON dr.restaurante_key = fp.restaurante_key
            JOIN dim_fecha df ON df.fecha_key = fp.fecha_pedido_key
            WHERE fp.n_entregados = 1
            GROUP BY dr.zona_id, df.anio_mes
            ORDER BY dr.zona_id, df.anio_mes
        """

SQL_DRILL = """
            WITH ped AS (
              SELECT dr.zona_id, df.anio_mes,
                     SUM(fp.total) AS ventas
              FROM hechos_pedidos fp
              JOIN dim_restaurante dr ON dr.restaurante_key = fp.restaurante_key
              JOIN dim_fecha df ON df.fecha_key = fp.fecha_pedido_key
              WHERE fp.n_entregados = 1
              GROUP BY dr.zona_id, df.anio_mes
            ),
            cob AS (
              SELECT dr.zona_id, df.anio_mes,
                     SUM(hc.monto) AS cobrado
              FROM hechos_cobros hc
              JOIN dim_restaurante dr ON dr.restaurante_key = hc.restaurante_key
              JOIN dim_fecha df ON df.fecha_key = hc.fecha_cobro_key
              GROUP BY dr.zona_id, df.anio_mes
            )
            SELECT COALESCE(ped.zona_id, cob.zona_id) AS zona_id,
                   COALESCE(ped.anio_mes, cob.anio_mes) AS anio_mes,
                   ped.ventas,
                   cob.cobrado
            FROM ped
            FULL OUTER JOIN cob
              ON cob.zona_id = ped.zona_id AND cob.anio_mes = ped.anio_mes
            ORDER BY 1, 2
        """

SQL_Q1_3FN = """
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
        """

SQL_Q1_DIM = """
            SELECT dr.zona_id, dr.zona_nombre, df.anio_mes,
                   SUM(f.n_entregados)::BIGINT AS n_pedidos,
                   SUM(f.total) FILTER (WHERE f.n_entregados = 1) AS ventas_totales
            FROM hechos_pedidos f
            JOIN dim_restaurante dr ON dr.restaurante_key = f.restaurante_key
            JOIN dim_fecha df ON df.fecha_key = f.fecha_pedido_key
            WHERE f.n_entregados = 1
            GROUP BY dr.zona_id, dr.zona_nombre, df.anio_mes
            ORDER BY dr.zona_id, df.anio_mes
        """

SQL_Q1_AGG = """
            SELECT zona_id, zona_nombre, anio_mes,
                   n_entregados AS n_pedidos,
                   ventas_entregadas AS ventas_totales
            FROM hechos_ventas_zona_mes
            ORDER BY zona_id, anio_mes
        """


def render_md(p: dict) -> str:
    k = p["kpis"]
    inf = k["inflacion_pct"]
    lines = [
        "# Comparaciones Tarea 06: drill-across, medidas y estrella",
        "",
        f"**Fecha de medición:** {p['timestamp']}",
        "**Motor:** PostgreSQL 16 (Docker)",
        f"**Volumen:** {p['n_pedidos']:,} pedidos · {p['n_cobros']:,} cobros · {p['n_calificaciones']:,} calificaciones",
        "",
        "## Protocolo de tiempo",
        "",
        "1. Se descarta la primera corrida (cold cache).",
        "2. Se reporta la **mediana** de 5 corridas calientes.",
        "3. Tiempo = `EXPLAIN (ANALYZE, FORMAT JSON)` → `Execution Time`.",
        "4. El JOIN ilegal y el drill-across **no** deben coincidir: el error es de grano, no de SQL.",
        "",
        "## El error que nunca hay que cometer (JOIN entre hechos)",
        "",
        "Un subconjunto de pedidos entregados tiene **dos cobros**. El JOIN `hechos_pedidos ⋈ hechos_cobros` duplica esas filas de pedido. La consulta corre y el número se ve plausible.",
        "",
        "| KPI | Valor |",
        "|-----|------:|",
        f"| Pedidos | {p['n_pedidos']:,} |",
        f"| Pedidos entregados | {k['n_entregados']:,} |",
        f"| Pedidos entregados con 2 cobros | {k['n_split']:,} |",
        f"| Filas en `hechos_cobros` | {p['n_cobros']:,} |",
        f"| `SUM(total)` entregados (correcto) | Q{k['ventas_correctas']:,.2f} |",
        f"| `SUM(monto)` cobros (correcto) | Q{k['cobrado_correcto']:,.2f} |",
        f"| `SUM(pedido.total)` tras JOIN ilegal | Q{k['ventas_join_ilegal']:,.2f} |",
        f"| Inflación del JOIN ilegal | **+{inf:.2f}%** (Q{k['delta_join']:,.2f} de más) |",
        "",
        "Cobrado correcto = ventas entregadas (cada quetzal se cobra una vez). El JOIN ilegal **no avisa**: infla ventas.",
        "",
        "| Variante | Mediana (ms) | Min | Max | Cold | Fingerprint |",
        "|----------|-------------:|----:|----:|-----:|-------------|",
    ]
    for name, m in p["drill"]["mediciones"].items():
        fp = p["drill"]["fingerprints"][name][:12] + "…"
        lines.append(
            f"| {name} | {m['median_ms']:.3f} | {m['min_ms']:.3f} | "
            f"{m['max_ms']:.3f} | {m['cold_ms']:.3f} | `{fp}` |"
        )
    w = p["drill"]["mediciones"]["join_ilegal"]["median_ms"]
    rgt = p["drill"]["mediciones"]["drill_across"]["median_ms"]
    lines += [
        "",
        f"Tiempo: drill-across es {speedup(w, rgt)} respecto del JOIN ilegal, "
        "pero el punto no es la velocidad: **el JOIN ilegal está mal aunque fuera más rápido**.",
        "",
        f"Fingerprints distintos: `{p['drill']['fingerprints']['join_ilegal']}` vs "
        f"`{p['drill']['fingerprints']['drill_across']}` — no miden lo mismo.",
        "",
        "## Medida no aditiva: % entregado",
        "",
        "Nunca se guarda el porcentaje. Se guardan `n_entregados` y `n_pedidos` (aditivos) y se divide al consultar.",
        "",
        "| Método | Resultado |",
        "|--------|----------:|",
        f"| Correcto: Σ entregados / Σ pedidos | **{k['pct_correcto']:.4f}%** |",
        f"| Incorrecto: promedio de % por zona | {k['pct_promedio_zonas']:.4f}% |",
        f"| Sesgo al promediar porcentajes | {k['pct_sesgo']:.4f} puntos |",
        "",
        "## Optimización: dashboard zona × mes (mismo protocolo que 04/05)",
        "",
        f"**Equivalencia 3FN / estrella / agregada:** {p['q1']['equivalence']}",
        "",
        "| Variante | Mediana (ms) | Min | Max | Cold |",
        "|----------|-------------:|----:|----:|-----:|",
    ]
    for name, m in p["q1"]["mediciones"].items():
        lines.append(
            f"| {name} | {m['median_ms']:.3f} | {m['min_ms']:.3f} | "
            f"{m['max_ms']:.3f} | {m['cold_ms']:.3f} |"
        )
    base = p["q1"]["mediciones"]["normalizado_3fn"]["median_ms"]
    lines += ["", "### Ganancia vs 3FN", ""]
    for name, m in p["q1"]["mediciones"].items():
        if name == "normalizado_3fn":
            continue
        lines.append(f"- **{name}:** {speedup(base, m['median_ms'])}")
    lines += [
        "",
        "## Espacio",
        "",
        "| Tabla | Tamaño |",
        "|-------|--------|",
    ]
    for t in p["sizes"]:
        if t["tabla"].startswith(("hechos_", "dim_", "pedido", "mart_")):
            lines.append(f"| `{t['tabla']}` | {t['pretty']} |")
    lines += [
        "",
        "Hecho angosto (`hechos_pedidos`) vs mart ancho clase 04 (`mart_pedido_geo`): "
        "el texto geográfico no se copia 3 millones de veces.",
        "",
        f"_Raw: `{RAW_JSON.relative_to(ROOT).as_posix()}`_",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    n_pedidos = int(psql("SELECT COUNT(*) FROM hechos_pedidos;"))
    n_cobros = int(psql("SELECT COUNT(*) FROM hechos_cobros;"))
    n_cal = int(psql("SELECT COUNT(*) FROM hechos_calificaciones;"))
    n_can = int(psql("SELECT COUNT(*) FROM hechos_cancelaciones;"))
    print(f"pedidos={n_pedidos:,} cobros={n_cobros:,} calif={n_cal:,} cancel={n_can:,}")

    print("KPIs de grano / inflación...")
    n_entregados = int(psql("SELECT SUM(n_entregados) FROM hechos_pedidos;"))
    n_split = int(psql("""
        SELECT COUNT(*) FROM (
          SELECT pedido_id FROM hechos_cobros GROUP BY pedido_id HAVING COUNT(*) > 1
        ) s;
    """))
    ventas = float(psql("SELECT SUM(total) FROM hechos_pedidos WHERE n_entregados = 1;"))
    cobrado = float(psql("SELECT SUM(monto) FROM hechos_cobros;"))
    ventas_wrong = float(psql("""
        SELECT SUM(fp.total)
        FROM hechos_pedidos fp
        JOIN hechos_cobros hc ON hc.pedido_id = fp.pedido_id
        WHERE fp.n_entregados = 1;
    """))
    pct_ok = float(psql("""
        SELECT 100.0 * SUM(n_entregados) / SUM(n_pedidos) FROM hechos_pedidos;
    """))
    pct_avg = float(psql("""
        SELECT AVG(pct) FROM (
          SELECT 100.0 * SUM(f.n_entregados) / SUM(f.n_pedidos) AS pct
          FROM hechos_pedidos f
          JOIN dim_restaurante dr ON dr.restaurante_key = f.restaurante_key
          GROUP BY dr.zona_id
        ) s;
    """))

    kpis = {
        "n_entregados": n_entregados,
        "n_split": n_split,
        "ventas_correctas": round(ventas, 2),
        "cobrado_correcto": round(cobrado, 2),
        "ventas_join_ilegal": round(ventas_wrong, 2),
        "delta_join": round(ventas_wrong - ventas, 2),
        "inflacion_pct": round(100.0 * (ventas_wrong - ventas) / ventas, 4),
        "pct_correcto": round(pct_ok, 4),
        "pct_promedio_zonas": round(pct_avg, 4),
        "pct_sesgo": round(pct_avg - pct_ok, 4),
    }
    print(f"  inflación JOIN = {kpis['inflacion_pct']}%")
    print(f"  % entregado correcto={kpis['pct_correcto']} vs avg zonas={kpis['pct_promedio_zonas']}")

    print("Fingerprints drill-across...")
    fp_wrong = fetch_fingerprint(SQL_WRONG)
    fp_drill = fetch_fingerprint(SQL_DRILL)
    print(f"  distinctos: {fp_wrong != fp_drill}")

    print("Tiempos JOIN ilegal vs drill-across...")
    med_wrong = median_ms(SQL_WRONG)
    print(f"  join_ilegal mediana={med_wrong['median_ms']} ms")
    med_drill = median_ms(SQL_DRILL)
    print(f"  drill_across mediana={med_drill['median_ms']} ms")

    print("Q1 3FN / estrella / agregada...")
    fps = {
        "normalizado_3fn": fetch_fingerprint(SQL_Q1_3FN),
        "estrella": fetch_fingerprint(SQL_Q1_DIM),
        "agregada": fetch_fingerprint(SQL_Q1_AGG),
    }
    ok = len(set(fps.values())) == 1
    if not ok:
        raise SystemExit(f"Q1 no equivalente: {fps}")
    q1_med = {
        "normalizado_3fn": median_ms(SQL_Q1_3FN),
        "estrella": median_ms(SQL_Q1_DIM),
        "agregada": median_ms(SQL_Q1_AGG),
    }
    for n, m in q1_med.items():
        print(f"  {n} mediana={m['median_ms']} ms")

    results = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "n_pedidos": n_pedidos,
        "n_cobros": n_cobros,
        "n_calificaciones": n_cal,
        "n_cancelaciones": n_can,
        "kpis": kpis,
        "drill": {
            "fingerprints": {"join_ilegal": fp_wrong, "drill_across": fp_drill},
            "mediciones": {"join_ilegal": med_wrong, "drill_across": med_drill},
        },
        "q1": {
            "equivalence": "OK — mismo fingerprint" if ok else "FAIL",
            "fingerprints": fps,
            "mediciones": q1_med,
        },
        "sizes": table_sizes(),
    }
    RAW_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUT.write_text(render_md(results), encoding="utf-8")
    print(f"\nEscrito: {MD_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
