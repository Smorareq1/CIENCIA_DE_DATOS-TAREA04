# Tarea 06 — Diseño dimensional (Parte 2)

**App:** Ruta Verde (mismo 3FN de las entregas 04 y 05).  
**Motor:** PostgreSQL 16 · **3,000,000** pedidos.  
**Fecha de medición:** 2026-08-18.

Números: [comparaciones.md](./comparaciones.md) · raw: [raw_mediciones.json](./raw_mediciones.json).

La Parte 1 dejó el grano (*una fila = un pedido registrado*), una tabla de hechos por proceso y el agregado zona×mes **aparte**. Esta entrega añade lo que la Parte 2 exige: **matriz del bus**, **claves sustitutas**, **drill-across** (nunca JOIN entre hechos) y **optimización con métricas**.

---

## 1. Matriz del bus (entregable)

🟩 = el proceso usa la dimensión (conformada: misma SK, mismos atributos, misma definición).  
⬜ = la dimensión no participa.

| Proceso de negocio | Grano | Tipo | Fecha (`dim_fecha`) | Cliente (`dim_cliente`) | Restaurante / ubicación (`dim_restaurante`) | Estado (`dim_estado`) |
|--------------------|-------|------|:---:|:---:|:---:|:---:|
| **Pedidos** (`hechos_pedidos`) | Un pedido registrado | Transaccional | 🟩 `fecha_pedido_key` | 🟩 | 🟩 | 🟩 |
| **Cobros** (`hechos_cobros`) | Un pago recibido | Transaccional | 🟩 `fecha_cobro_key` (mismo `dim_fecha`, otro rol) | 🟩 | 🟩 | ⬜ |
| **Calificaciones** (`hechos_calificaciones`) | Una calificación enviada | Transaccional | 🟩 `fecha_calificacion_key` | 🟩 | 🟩 | ⬜ |
| **Cancelaciones** (`hechos_cancelaciones`) | Una cancelación ocurrida | Factless | 🟩 | 🟩 | 🟩 | ⬜ |
| **Ventas zona×mes** (`hechos_ventas_zona_mes`) | Ventas de una zona en un mes | Agregada (mismo proceso Pedidos, **otro grano**) | 🟩 mes | ⬜ | 🟩 zona | ⬜ |

No es una tabla de hechos por reporte: Pedidos / Cobros / Calificaciones / Cancelaciones son **procesos**. Zona×mes es el **mismo** proceso Pedidos resumido; vive aparte porque el grano es distinto (regla de la Parte 1).

`dim_fecha` es **role-playing**: una sola tabla física, tres papeles (`fecha_pedido`, `fecha_cobro`, `fecha_calificacion`). No hay tres copias de calendario.

Ubicación no se copo-de-nieve en `zona → municipio → departamento`: queda **aplanada en `dim_restaurante`** (estrella). El pre-join de la clase 04 era esa dimensión; el error fue pegarlo en el hecho.

```text
                    dim_fecha (1 física, N roles)
                           │
dim_cliente ──────── hechos_pedidos ──────── dim_restaurante (geo plana)
                           │
                      dim_estado

dim_cliente ──────── hechos_cobros ──────── dim_restaurante
                           │
                      dim_fecha (rol cobro)

dim_cliente ──── hechos_calificaciones ──── dim_restaurante
                           │
                      dim_fecha (rol calificación)
```

No se dibuja un copo: `municipio` y `departamento` no son tablas del mart.

---

## 2. Preguntas de la guía

### 2.1 ¿Qué dos procesos se pueden cruzar y por cuáles dimensiones conformadas?

**Pedidos y Cobros**, a través de **Fecha, Cliente y Restaurante/ubicación**.

Pregunta de negocio: *¿cuánto se vendió (pedidos entregados) y cuánto se cobró, por zona y por mes?*

Cómo se cruza (drill-across, 3 pasos):

1. Agregar `hechos_pedidos` hasta zona × `anio_mes`.
2. Agregar `hechos_cobros` hasta zona × `anio_mes` (mes de `fecha_cobro`).
3. Unir **esos resúmenes** por las dims conformadas, nunca las tablas de hechos.

También cruzan Pedidos + Calificaciones (Fecha, Cliente, Restaurante): *ventas vs puntaje promedio por zona y mes*. El promedio se calcula al final: `SUM(puntaje)/SUM(n_calificaciones)`, no se suma un % precalculado.

### 2.2 ¿Cuál cruce no tiene sentido de negocio y por qué?

**Cobros + Calificaciones por `dim_estado`.**

Estado es el ciclo del **pedido** (`entregado` / `en_camino` / `cancelado`). Un pago no está “en camino” y una calificación no tiene estado operativo: esas tablas **no usan** `dim_estado` (⬜ en la matriz). Forzar el cruce sería el análogo del ejemplo de clase: Cobros + Calificaciones por Repartidor, cuando Cobros no tiene repartidor.

Tampoco: **Ventas zona×mes + Calificaciones por segmento de cliente**. El agregado no tiene `cliente_key`; el grano zona×mes **ya tiró** el segmento. Eso es el grano irreversible de la Parte 1.

---

## 3. Cómo se ejecutó (sin romper las entregas anteriores)

| Clase | Qué se reutiliza | Qué se corrige / añade |
|-------|------------------|-------------------------|
| 04 | 3FN, 3M pedidos, protocolo de mediana, “no desnormalizar porque sí” | El mart ancho (`mart_pedido_geo`, 497 MB) no es la estrella |
| 05 | Grano de pedido, geo en la dimensión, agregado aparte | Las PK seguían siendo las del origen (`cliente_id`) |
| 06 | Misma estrella | **SK**, tres procesos más, factless, drill-across medido, % no materializado |

Cobros y calificaciones **no estaban en el CSV**. Se derivan de `pedido` solo para el laboratorio, con regla fija:

- Cobro: un pago por pedido `entregado`; si `pedido_id % 7 = 0`, **dos** pagos (grano distinto a propósito).
- Calificación: una por pedido entregado; `puntaje = 1 + (pedido_id % 5)`.
- Cancelación factless: una fila por `estado = cancelado`, sin medidas.

Así el JOIN ilegal tiene algo que inflar: **285,949** pedidos con dos cobros.

### Claves sustitutas

| Dimensión | PK (warehouse) | Llave natural (origen) |
|-----------|----------------|------------------------|
| `dim_cliente` | `cliente_key` | `cliente_id` |
| `dim_restaurante` | `restaurante_key` | `restaurante_id` |
| `dim_fecha` | `fecha_key` | `fecha_id` |
| `dim_estado` | `estado_key` | `estado_id` |

El hecho apunta a la SK. `pedido_id` en `hechos_pedidos` es **dimensión degenerada** (no hay `dim_pedido`). Listo para SCD2: el mismo `cliente_id` podría tener dos `cliente_key`; hoy hay una versión porque el origen no historiza.

### Medidas

| Medida | Tipo | Dónde |
|--------|------|--------|
| `total`, `monto`, `n_pedidos`, `n_entregados`, `n_cobros`, `puntaje` (suma), `n_calificaciones` | **Aditiva** | Hechos |
| *(no hay saldo de inventario en este 3FN)* | Semi-aditiva | No se inventa un snapshot de stock |
| `% entregado`, ticket promedio, puntaje medio | **No aditiva** | Se calcula al consultar |

Regla de oro aplicada: `hechos_ventas_zona_mes` guarda `n_entregados` y `n_pedidos`, **no** el porcentaje.

---

## 4. Tiempos y el JOIN que miente

Protocolo: descartar cold · mediana de 5 calientes · `EXPLAIN ANALYZE`.

### 4.1 JOIN directo entre hechos (prohibido)

| KPI | Valor |
|-----|------:|
| `SUM(total)` entregados (correcto) | Q485,342,952.50 |
| `SUM(monto)` cobros (correcto) | Q485,342,952.50 |
| `SUM(pedido.total)` tras `JOIN` por `pedido_id` | Q554,686,695.39 |
| Inflación | **+14.29%** (Q69.3 M de más) |

La consulta **no falla**. Devuelve un número creíble. Es el mismo tipo de mentira que el fan-out Q450 vs Q150 de la clase 04: error de **grano**, no de SQL.

| Variante | Mediana (ms) | Fingerprint |
|----------|-------------:|-------------|
| JOIN ilegal | 844.293 | `dd3b49fb…` |
| Drill-across | 751.533 | `597f7d8a…` |

Los fingerprints **difieren**: no se está midiendo lo mismo. Aunque el JOIN fuera más rápido, seguiría siendo incorrecto. La guía: *optimización al final y siempre con métricas; primero el modelo correcto*.

`fecha_cobro` puede caer 0–3 días después del pedido (role-playing). El drill-across por mes usa cada fecha en su rol; un cobro de un pedido del 31 puede aparecer en el mes siguiente. Eso es desfase operativo, no un JOIN cartesiano.

### 4.2 % no aditivo

| Método | % entregado |
|--------|------------:|
| Correcto: Σ `n_entregados` / Σ `n_pedidos` | **66.7209%** |
| Promedio de % por zona | 66.7403% |

El sesgo aquí es chico (zonas parecidas en volumen). Con el ejemplo de clase (10 vs 1,000 entregas) el promedio de porcentajes **miente**. Por eso no se guarda el `%`.

### 4.3 Optimización del dashboard (después del modelo)

Misma pregunta Q1 de 04/05, equivalencia MD5 OK entre 3FN, estrella y agregada.

| Variante | Mediana (ms) vs 3FN |
|----------|---------------------|
| 3FN (copo: restaurante→zona→…) | 708.774 |
| Estrella (`hechos_pedidos` + `dim_restaurante`) | 389.165 (**1.82×**) |
| Hechos agregados zona×mes | 2.450 (**289×**) |

Espacio: hecho de pedidos **341 MB** vs mart ancho 04 **497 MB**. La palanca “mantener el hecho angosto” se cumple: en el hecho solo SK y números.

No se particionó por fecha en este laboratorio: Q1 ya deja claro que la palanca que mueve el dashboard es el **hecho agregado**, no más ingeniería sobre el detalle. Sin medición previa, particionar habría sido una suposición.

---

## 5. Recordatorios de la guía (cumplidos)

| Recordatorio | Cómo |
|--------------|------|
| Grano primero; una tabla de hechos por proceso | Pedidos / cobros / calificaciones / cancelaciones; zona×mes es agregado, no un quinto proceso |
| Los hechos nunca se unen directo | §4.1; se alinean por dims conformadas |
| Optimización al final, con métricas | §4.3; no se adoptó el JOIN ilegal aunque midiera tiempo |

### ¿Cuándo no haríamos dimensional? (tema 9, aplicado)

Con **un solo** dashboard zona×mes, una tabla plana habría bastado (el agregado de 2.45 ms). El costo de la estrella se justifica porque ahora hay **varios consumidores/procesos** (pedidos, cobros, calificaciones) que tienen que cuadrar entre sí. El 3FN a 709 ms ya no está “bajo 200 ms”; sí hay cuello que medir.

Estructuras anidadas (técnica 4 de la clase 04) **no se usan**: Kimball no las mapea a la estrella.

---

## 6. Checklist contra `docs/06/Diseno_Dimensional_Parte_2.md`

| Pedido | ¿Dónde? |
|--------|---------|
| Dibujar la matriz del bus del modelo de la entrega previa | §1 |
| Dos procesos que se cruzan y dims conformadas | §2.1 Pedidos × Cobros por Fecha, Cliente, Restaurante |
| Cruce que no tiene sentido y por qué | §2.2 Cobros × Calificaciones por Estado |
| Grano primero; un hecho por proceso | §1 y §5 |
| Hechos no se JOIN; drill-across | §4.1 con inflación **+14.29%** medida |
| Optimización al final con métricas | §4.3 (708 / 389 / 2.45 ms) |
| SK, role-playing, estrella vs copo, medidas, factless | §1, §3 |

### Cómo reproducir

```powershell
.\scripts\db.ps1 up
.\scripts\db.ps1 dimensional06
.\scripts\db.ps1 benchmark06
```
