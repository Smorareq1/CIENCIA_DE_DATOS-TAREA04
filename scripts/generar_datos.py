#!/usr/bin/env python3
"""Genera CSVs del modelo normalizado Ruta Verde (docs/GUIA.md).

Uso:
  python scripts/generar_datos.py
  python scripts/generar_datos.py --pedidos 3000000
  python scripts/generar_datos.py --pedidos 100000   # prueba rápida
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "datos"

# Volúmenes por defecto (la guía pide >= 1M; generador en 3M)
DEFAULT_PEDIDOS = 3_000_000
N_CLIENTES = 80_000
N_RESTAURANTES = 2_500

DEPARTAMENTOS = [
    "Guatemala",
    "Sacatepéquez",
    "Chimaltenango",
    "Escuintla",
    "Santa Rosa",
    "Sololá",
    "Totonicapán",
    "Quetzaltenango",
    "Suchitepéquez",
    "Retalhuleu",
    "San Marcos",
    "Huehuetenango",
    "Quiché",
    "Baja Verapaz",
    "Alta Verapaz",
    "Petén",
    "Izabal",
    "Zacapa",
    "Chiquimula",
    "Jalapa",
    "Jutiapa",
    "El Progreso",
]

MUNICIPIOS_POR_DEPTO = {
    "Guatemala": [
        "Guatemala",
        "Mixco",
        "Villa Nueva",
        "San Miguel Petapa",
        "Villa Canales",
        "Amatitlán",
        "Chinautla",
        "San José Pinula",
    ],
    "Sacatepéquez": ["Antigua Guatemala", "Ciudad Vieja", "Jocotenango", "San Lucas Sacatepéquez"],
    "Chimaltenango": ["Chimaltenango", "Tecpán", "Patzún", "Comalapa"],
    "Escuintla": ["Escuintla", "Santa Lucía Cotzumalguapa", "Palín", "Puerto San José"],
    "Quetzaltenango": ["Quetzaltenango", "Coatepeque", "Salcajá", "Cantel"],
    "Petén": ["Flores", "San Benito", "Melchor de Mencos", "Poptún"],
}

SEGMENTOS = ["frecuente", "ocasional", "nuevo", "premium"]
ESTADOS = ["entregado", "entregado", "entregado", "entregado", "cancelado", "en_camino"]
NOMBRES = [
    "Ana", "Luis", "María", "Carlos", "Sofía", "Diego", "Elena", "Jorge",
    "Laura", "Pedro", "Carmen", "Andrés", "Rosa", "Miguel", "Paula", "José",
]
APELLIDOS = [
    "García", "López", "Pérez", "Hernández", "Martínez", "Rodríguez",
    "González", "Ramírez", "Morales", "Castillo", "Reyes", "Cruz",
]
PREFIJOS_REST = ["Ruta Verde", "Verde Express", "Sazón", "Del Campo", "La Finca", "Oasis"]


def _municipios_para(depto: str) -> list[str]:
    if depto in MUNICIPIOS_POR_DEPTO:
        return MUNICIPIOS_POR_DEPTO[depto]
    # Relleno genérico para el resto de departamentos
    return [f"Cabecera {depto}", f"Norte {depto}", f"Sur {depto}", f"Este {depto}"]


def generar(n_pedidos: int, seed: int) -> None:
    rng = random.Random(seed)
    OUT.mkdir(parents=True, exist_ok=True)

    # --- departamento ---
    deptos = [(i + 1, nombre) for i, nombre in enumerate(DEPARTAMENTOS)]
    with (OUT / "departamento.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["departamento_id", "nombre"])
        w.writerows(deptos)

    # --- municipio ---
    municipios: list[tuple[int, str, int]] = []
    mid = 1
    for did, dnombre in deptos:
        for mnombre in _municipios_para(dnombre):
            municipios.append((mid, mnombre, did))
            mid += 1
    with (OUT / "municipio.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["municipio_id", "nombre", "departamento_id"])
        w.writerows(municipios)

    # --- zona (3–8 por municipio) ---
    zonas: list[tuple[int, str, int]] = []
    zid = 1
    for mun_id, _, _ in municipios:
        n_zonas = rng.randint(3, 8)
        for z in range(1, n_zonas + 1):
            zonas.append((zid, f"Zona {z}", mun_id))
            zid += 1
    with (OUT / "zona.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["zona_id", "nombre", "municipio_id"])
        w.writerows(zonas)

    zona_ids = [z[0] for z in zonas]

    # --- restaurante ---
    restaurantes: list[tuple[int, str, int]] = []
    for rid in range(1, N_RESTAURANTES + 1):
        nombre = f"{rng.choice(PREFIJOS_REST)} #{rid}"
        restaurantes.append((rid, nombre, rng.choice(zona_ids)))
    with (OUT / "restaurante.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["restaurante_id", "nombre", "zona_id"])
        w.writerows(restaurantes)

    rest_ids = list(range(1, N_RESTAURANTES + 1))

    # --- cliente ---
    with (OUT / "cliente.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cliente_id", "nombre", "segmento", "telefono"])
        for cid in range(1, N_CLIENTES + 1):
            nombre = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}"
            segmento = rng.choice(SEGMENTOS)
            telefono = f"5{rng.randint(1000000, 9999999)}"
            w.writerow([cid, nombre, segmento, telefono])

    cliente_ids = list(range(1, N_CLIENTES + 1))

    # --- pedido ---
    fecha_inicio = date(2024, 1, 1)
    dias_rango = 730  # ~2 años
    batch = 100_000
    print(f"Generando {n_pedidos:,} pedidos en {OUT} ...")

    with (OUT / "pedido.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pedido_id", "cliente_id", "restaurante_id", "fecha", "total", "estado"])
        for start in range(1, n_pedidos + 1, batch):
            end = min(start + batch - 1, n_pedidos)
            rows = []
            for pid in range(start, end + 1):
                fecha = fecha_inicio + timedelta(days=rng.randint(0, dias_rango - 1))
                total = round(rng.uniform(35.0, 450.0), 2)
                rows.append(
                    [
                        pid,
                        rng.choice(cliente_ids),
                        rng.choice(rest_ids),
                        fecha.isoformat(),
                        f"{total:.2f}",
                        rng.choice(ESTADOS),
                    ]
                )
            w.writerows(rows)
            print(f"  pedidos {end:,}/{n_pedidos:,}", flush=True)

    print("Listo:")
    for name in (
        "departamento.csv",
        "municipio.csv",
        "zona.csv",
        "restaurante.csv",
        "cliente.csv",
        "pedido.csv",
    ):
        path = OUT / name
        mb = path.stat().st_size / (1024 * 1024)
        print(f"  {name:20s} {mb:7.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera CSVs normalizados Ruta Verde")
    parser.add_argument(
        "--pedidos",
        type=int,
        default=DEFAULT_PEDIDOS,
        help=f"Filas en pedido (default {DEFAULT_PEDIDOS})",
    )
    parser.add_argument("--seed", type=int, default=42, help="Semilla reproducible")
    args = parser.parse_args()
    if args.pedidos < 1:
        raise SystemExit("--pedidos debe ser >= 1")
    generar(args.pedidos, args.seed)


if __name__ == "__main__":
    main()
