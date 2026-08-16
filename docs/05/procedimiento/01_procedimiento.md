# Tarea 05 — Diseño dimensional (Parte 1)

**App / modelo 3FN de partida:** Ruta Verde (el mismo que el grupo desnormalizó en la clase 04).  
**Motor:** PostgreSQL 16 (Docker). **Volumen:** 3,000,000 pedidos.  
**Fecha de medición:** 2026-08-16.  
**No se dibuja el modelo dimensional:** esta hoja es el punto de partida; el dibujo es la próxima clase.

Detalle numérico de tiempos y espacio: [comparaciones.md](./comparaciones.md).  
Raw: [raw_mediciones.json](./raw_mediciones.json).

---

## 1. En clase (entregable)

### 1.1 Grano del proceso

**Proceso (verbo, no sustantivo):** registrar un pedido.

**Grano (una frase, presente, sin agregaciones):**

> Una fila = un pedido registrado.

No es “ventas por zona y mes”. Eso ya es un agregado: otro grano, otra tabla.

### 1.2 Cinco campos: hecho o dimensión

Prueba de la guía: *si te sirve para sumar, es un hecho; si te sirve para filtrar o agrupar, es una dimensión.*

| Campo | Clasificación | Prueba |
|-------|---------------|--------|
| `total` | **Hecho** (medida) | `SUM(total)` es la venta. No se usa como filtro de negocio. |
| `n_pedidos` (= 1 por fila) | **Hecho** (medida) | `SUM(n_pedidos)` cuenta pedidos. Es aditivo. |
| `fecha` / `dim_fecha` | **Dimensión** | Filtra (“en marzo”) y agrupa (“por mes”). No se suma. |
| `zona_nombre` (vía restaurante) | **Dimensión** | Filtra y agrupa el “dónde”. `SUM(zona)` no tiene sentido. |
| `segmento` (del cliente) | **Dimensión** | Corta la medida: frecuente / premium / etc. |

### 1.3 El que no es obvio: `estado`

`estado` (`entregado`, `en_camino`, `cancelado`) *parece* describir “qué pasó”, y por eso alguien lo trataría como hecho.

No pasa la prueba: **no se suma**. `SUM(estado)` no significa nada. Sirve para **filtrar** (“solo entregados”) y **agrupar** (“pedidos por estado”). Es dimensión — en este modelo, degenerada o `dim_estado`.

La confusión viene de que la *tasa de cancelación* usa un `COUNT` filtrado por estado: el estado **participa** en una medida, pero no **es** la medida.

Otro candidato a confusión es `total`: ya viene precalculado en el 3FN. Es medida del **pedido**. Si más adelante existiera `detalle_pedido`, poner `total` al lado de cada línea repetiría el grano del pedido dentro del grano de la línea (fan-out de la clase 04). Hoy no hay detalle, así que `total` en el hecho de pedido es correcto.

---

## 2. En casa

### 2.1 Verbos vs sustantivos (de dónde sale el hecho)

El 3FN lista **sustantivos**: cliente, restaurante, zona, municipio, departamento, pedido.

Ruta Verde **mide** (verbos que el 3FN actual sí soporta):

| Proceso | ¿Hay datos en el 3FN? | Tabla de hechos |
|---------|------------------------|-----------------|
| Registrar un pedido | Sí (`pedido`) | `hechos_pedidos` |
| Entregar (con duración) | No: no hay timestamps de pickup/dropoff ni repartidor | No se inventa |
| Cobrar | No hay pagos | No se inventa |
| Calificar | No hay scores | No se inventa |

“Cuánto tardó la entrega” **no vive en el modelo de sustantivos**. Habría que derivarla de marcas de tiempo que este 3FN no tiene. No se fabrica una medida sin fuente: el modelo normalizado es el punto de partida, no se sustituye con filas ficticias.

Una tabla de hechos **por proceso**. Aquí hay un proceso con datos → una transaccional. El dashboard zona×mes no es un proceso nuevo: es el **mismo** proceso a **otro grano** → tabla agregada aparte.

### 2.2 Tipo de tabla de hechos

**`hechos_pedidos` es transaccional.** Una fila es un evento que ocurrió (el pedido se registró); se inserta y no se reescribe con hitos. El 3FN solo trae una `fecha` y un `estado`, no la cadena creado → asignado → recogido → entregado con timestamps, así que no hay snapshot acumulativo que medir.

**`hechos_ventas_zona_mes` es una tabla de hechos agregada** (mismo proceso, grano distinto: una fila = ventas de una zona en un mes). La guía: *“Quiero el mismo dato resumido por mes → Sí, pero agregada”*. No es un snapshot periódico: no fotografía “pedidos pendientes al cierre del día”; resume transacciones ya ocurridas.

No se elige snapshot periódico: no modelamos inventario ni backlog diario.

### 2.3 Desnormalización correcta (cada descomposición)

La clase 04 aplanó por intuición. Ahora cada ruptura de 3FN se declara: qué dependencia se vuelve a romper y **en qué tabla queda**, sin mezclar granos.

#### D1 — Pre-join geográfico (dependencia transitiva)

**Qué rompía 3FN:**  
`restaurante_id → zona_id → municipio_id → departamento_id → departamento.nombre`  
El nombre del departamento no depende del pedido; depende del restaurante (transitiva).

**Dónde estaba repartida en 3FN:**  
`restaurante` → `zona` → `municipio` → `departamento`.

**Dónde queda ahora:**  
Solo en **`dim_restaurante`** (2,500 filas: una por restaurante). El hecho guarda `restaurante_id`, no `departamento_nombre`.

**Qué no se hace:** repetir zona/municipio/depto en cada una de las 3M filas del hecho (`mart_pedido_geo` de la clase 04). Eso era desnormalizar el **hecho**, no la dimensión.

| | Clase 04 (`mart_pedido_geo`) | Clase 05 (`dim_restaurante` + `hechos_pedidos`) |
|--|------------------------------|--------------------------------------------------|
| Dónde vive geo | En cada pedido (3M copias) | En la dimensión (2,500 copias) |
| Espacio extra | 497 MB el mart vs 331 MB `pedido` | Dim restaurante **408 kB**; hecho **342 MB** |
| Grano del hecho | Sigue siendo un pedido, pero la fila es ancha | Un pedido, fila delgada |

#### D2 — Calendario derivado (no era 3FN; era cálculo repetido)

**Dependencia:** `fecha → (año, mes, día de semana, anio_mes)`. No es una violación de formas normales del 3FN; es la técnica de columna derivada, ahora **en la dimensión de fecha**.

**Dónde queda:** **`dim_fecha`** (730 días). El hecho guarda `fecha_id`.

#### D3 — Agregado zona × mes (no es la misma desnormalización)

**No rompe una dependencia de 3FN.** Cambia el **grano**: de “un pedido” a “una zona en un mes”.

**Dónde queda:** **`hechos_ventas_zona_mes`** (~11,880 filas, **2040 kB**). Tabla nueva porque el grano es distinto.

Si esto se mezclara dentro de `hechos_pedidos` (total del pedido al lado de un resumen zona-mes, o total del pedido al lado de líneas de detalle), reaparecería el error de grano: sumar Q450 donde iban Q150. Por eso **no conviven**.

### 2.4 Cerrar el círculo: ¿la clase 04 contradice este grano?

| Desnormalización clase 04 | ¿Contradice el grano “un pedido registrado”? | ¿Quién gana? |
|---------------------------|-----------------------------------------------|--------------|
| `mart_pedido_geo` (pre-join en el hecho) | **No el grano**, sí el *lugar* de la desnormalización. Sigue siendo una fila por pedido. | Gana el diseño 05: geo en `dim_restaurante`. El mart ancho midió **peor** en rankings con filtro (Q3 clase 04: 107 ms vs 79 ms 3FN) y cuesta 497 MB. |
| `agg_ventas_zona_mes` / `mv_ventas_zona_mes` | **Sí, si se usa como si fuera el mismo hecho.** El grano pasa a zona×mes. Preguntas a nivel pedido, segmento o día de la semana **ya no tienen respuesta** en esa tabla. | Ganan **las dos tablas**, no una sola: el transaccional conserva el grano fino; el agregado existe **aparte** para el dashboard. La guía: grano distinto → tabla distinta. No se tira el agregado; se deja de fingir que es el mismo modelo. |
| Columna `anio_mes` en el mart de pedidos | No contradice el grano. | Se mueve a `dim_fecha`. |

**Regla aplicada:** si una desnormalización de la clase 04 aceleraba una consulta **cambiando el grano**, no se “corrige” metiendo el resumen en la tabla fina. Se declara un segundo hecho. Si no mejoraba (pre-join ancho en Q3), se revierte.

Q4 de esta corrida es la prueba: `hechos_ventas_zona_mes` **no tiene variante** para “ventas por segmento y día de la semana”. Si hubiéramos declarado el grano como zona×mes, esa pregunta se pierde para siempre.

---

## 3. Tiempos medidos

Protocolo (el mismo de la guía técnica de medición): se descarta la 1ª corrida; **mediana de 5** calientes; fingerprint MD5 idéntico entre variantes.

| Consulta | 3FN (ms) | Dimensional, grano pedido (ms) | Agregada, grano zona×mes (ms) |
|----------|---------:|-------------------------------:|------------------------------:|
| Q1 ventas zona × mes | 685.608 | 365.082 (1.88×) | **2.150** (319×) |
| Q2 ventas depto × mes | 480.243 | 277.719 (1.73×) | **3.301** (145×) |
| Q3 top 20 zonas 2025-Q1 | **78.814** | 108.447 (1.38× más lenta) | **1.722** (46×) |
| Q4 segmento × día semana | 340.980 | 334.715 (~igual) | *no aplica: otro grano* |

Espacio:

- 3FN: **339 MB**
- Dimensional transaccional (dims + `hechos_pedidos`): **350 MB** (~+11 MB; la geo no se duplica 3M veces)
- Agregada zona×mes: **2040 kB**
- Mart ancho clase 04, de referencia: **497 MB**

Lectura (no se desnormaliza “porque sí”):

1. El dimensional a grano de pedido **ayuda** cuando hay que recorrer historial + joins (Q1, Q2). En Q3, con filtro de fechas, el 3FN estrecho sigue ganando al hecho + dims: **no se fuerza** el dimensional para esa consulta.
2. El agregado gana el dashboard por órdenes de magnitud, **a costa de no poder responder Q4**.
3. Equivalencia de resultados: OK en Q1–Q4 entre las variantes que comparten grano.

---

## 4. Qué no se hace (guía)

- **No** una sola tabla de hechos para todo el warehouse.
- **No** una tabla de hechos por reporte de gerencia (el dashboard no crea un “proceso”).
- **No** mezclar grano de pedido con grano zona×mes en la misma tabla.
- **No** dibujar el estrella todavía.
- **No** estructuras anidadas: el 3FN no tiene hijos (detalle/producto) que exploten filas.

---

## 5. Checklist contra `docs/05/GUIA.md`

| Pedido de la guía | ¿Dónde está? |
|-------------------|--------------|
| Grano en una frase, presente, sin agregaciones | §1.1 |
| Cinco campos hecho vs dimensión, prueba sumar/filtrar | §1.2 |
| Uno no obvio, explicado | §1.3 `estado` |
| Desnormalización correcta; cada descomposición (dependencia + tablas) | §2.3 D1–D3 |
| Tipo de hecho + justificación en una frase | §2.2 transaccional / agregada |
| ¿La clase 04 contradice el grano? ¿Cuál gana y por qué? | §2.4 |
| No dibujar el modelo dimensional | Cumplido: tablas y texto, sin diagrama estrella |
| Tiempos y espacio medidos (mismo protocolo que la entrega anterior) | §3 y [comparaciones.md](./comparaciones.md) |

### Cómo reproducir

```powershell
.\scripts\db.ps1 up
.\scripts\db.ps1 dimensional
.\scripts\db.ps1 benchmark05
```
