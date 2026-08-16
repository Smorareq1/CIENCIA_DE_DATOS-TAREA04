<#
.SYNOPSIS
  Helper para iterar con Postgres (Docker) en la Tarea 04.

.EXAMPLES
  .\scripts\db.ps1 up
  .\scripts\db.ps1 generate          # 3M pedidos (tarda)
  .\scripts\db.ps1 generate -Pedidos 100000
  .\scripts\db.ps1 load              # carga CSVs al modelo normalizado
  .\scripts\db.ps1 reset             # down -v + up + schema + load
  .\scripts\db.ps1 soft-reset        # DROP SCHEMA + schema + load (sin borrar volumen)
  .\scripts\db.ps1 psql
  .\scripts\db.ps1 size
  .\scripts\db.ps1 down
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "up", "down", "reset", "soft-reset", "load", "schema", "denorm",
        "dimensional", "benchmark", "benchmark05", "generate", "psql", "status", "size", "help"
    )]
    [string]$Cmd = "help",

    [int]$Pedidos = 3000000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Wait-Postgres {
    Write-Host "Esperando a que Postgres esté listo..."
    $deadline = (Get-Date).AddMinutes(2)
    do {
        docker compose exec -T postgres pg_isready -U ruta_verde -d ruta_verde 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "Postgres no quedó listo a tiempo. Revisa: docker compose logs postgres"
}

function Invoke-SqlFile([string]$RelativePath) {
    $name = Split-Path $RelativePath -Leaf
    docker compose exec -T postgres psql -U ruta_verde -d ruta_verde -v ON_ERROR_STOP=1 -f "/sql/$name"
}

function Ensure-Datos {
    $pedido = Join-Path $Root "datos\pedido.csv"
    if (-not (Test-Path $pedido)) {
        throw "No existe datos/pedido.csv. Corre primero: .\scripts\db.ps1 generate"
    }
}

switch ($Cmd) {
    "help" {
        Write-Host @"
Comandos:
  up           Levanta Postgres
  down         Apaga contenedores (mantiene volumen)
  reset        Borra volumen, recrea DB, carga CSVs (empezar de 0)
  soft-reset   DROP SCHEMA + schema + load (sin borrar volumen Docker)
  schema       Aplica sql/01_schema_normalizado.sql
  load         TRUNCATE + COPY de datos/*.csv
  denorm       Construye marts desnormalizados clase 04 (sql/03_...)
  dimensional  Construye hechos + dims clase 05 (sql/05_...)
  benchmark    Corre mediciones clase 04
  benchmark05  Corre mediciones clase 05 → docs/05/procedimiento/
  generate     Genera CSVs (usa -Pedidos N)
  psql         Abre psql interactivo
  status       docker compose ps
  size         Tamaño de tablas (pg_total_relation_size)

Flujo tipico (laboratorio):
  .\scripts\db.ps1 generate -Pedidos 3000000
  .\scripts\db.ps1 up
  .\scripts\db.ps1 load
  .\scripts\db.ps1 denorm
  .\scripts\db.ps1 benchmark
"@
    }
    "up" {
        docker compose up -d
        Wait-Postgres
        Write-Host "OK: postgres en localhost:$env:POSTGRES_PORT (default 5432)"
        Write-Host "    user/db/pass: ruta_verde / ruta_verde / ruta_verde"
    }
    "down" {
        docker compose down
    }
    "status" {
        docker compose ps
    }
    "generate" {
        python (Join-Path $Root "scripts\generar_datos.py") --pedidos $Pedidos
    }
    "schema" {
        Wait-Postgres
        Invoke-SqlFile "sql/01_schema_normalizado.sql"
    }
    "load" {
        Ensure-Datos
        Wait-Postgres
        Write-Host "Cargando CSVs (pedido grande puede tardar varios minutos)..."
        Invoke-SqlFile "sql/02_load_normalizado.sql"
        Write-Host "Carga terminada."
    }
    "denorm" {
        Wait-Postgres
        Write-Host "Construyendo modelos desnormalizados..."
        Invoke-SqlFile "sql/03_schema_desnormalizado.sql"
        Write-Host "Denorm listo."
    }
    "dimensional" {
        Wait-Postgres
        Write-Host "Construyendo modelo dimensional (hechos + dims)..."
        Invoke-SqlFile "sql/05_schema_dimensional.sql"
        Write-Host "Dimensional listo."
    }
    "benchmark" {
        Wait-Postgres
        python (Join-Path $Root "scripts\benchmark.py")
    }
    "benchmark05" {
        Wait-Postgres
        python (Join-Path $Root "scripts\benchmark_05.py")
    }
    "soft-reset" {
        Ensure-Datos
        Wait-Postgres
        Write-Host "Soft reset: DROP SCHEMA + schema + load..."
        Invoke-SqlFile "sql/00_drop_all.sql"
        Invoke-SqlFile "sql/01_schema_normalizado.sql"
        Invoke-SqlFile "sql/02_load_normalizado.sql"
        Write-Host "Soft reset listo."
    }
    "reset" {
        Ensure-Datos
        Write-Host "Hard reset: docker compose down -v ..."
        docker compose down -v
        docker compose up -d
        Wait-Postgres
        # El init ya aplicó 01_schema; solo falta cargar
        Write-Host "Cargando CSVs..."
        Invoke-SqlFile "sql/02_load_normalizado.sql"
        Write-Host "Reset completo: DB limpia + datos cargados."
    }
    "psql" {
        Wait-Postgres
        docker compose exec postgres psql -U ruta_verde -d ruta_verde
    }
    "size" {
        Wait-Postgres
        docker compose exec -T postgres psql -U ruta_verde -d ruta_verde -c @"
SELECT relname AS tabla,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS tamano
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY pg_total_relation_size(c.oid) DESC;
"@
    }
}
