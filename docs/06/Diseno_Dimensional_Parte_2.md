# Diseño Dimensional (Parte 2)

**Curso:** Ciencia de Datos – 2026 Sección 2  
**Catedrático:** Ing. Max Cerna  
**Institución:** Universidad Rafael Landívar  

---

## 📌 Agenda
1. No todas las medidas se pueden sumar (Tipos de medidas)
2. Claves sustitutas (*Surrogate Keys*): por qué no sirve la llave del origen
3. Una dimensión que juega varios papeles (*Role-Playing Dimensions*)
4. Esquema Estrella vs. Esquema Copo de Nieve
5. Cómo se consultan varias tablas de hechos y el error que nunca deben cometer (*Drill-Across*)
6. Dimensiones conformadas y la matriz del bus
7. Casos especiales: Relaciones Muchos-a-Muchos y Tablas de Hechos sin Hechos (*Factless Fact Tables*)
8. Cómo se optimiza un modelo dimensional
9. ¿Cuándo NO usar modelo dimensional?
10. Mapeo de técnicas de optimización vs. Modelado Dimensional
11. Tarea Práctica

---

## 🔄 De Dónde Venimos (Resumen Parte 1)
De la Parte 1 traemos tres principios fundamentales:
* **El grano declarado en una frase:** La unidad atómica de lo que representa una fila en la tabla de hechos.
* **Una tabla de hechos por proceso de negocio:** No intentar meter todo en una sola tabla de hechos.
* **Tres formas de medir un proceso:**
  * Transaccional
  * *Snapshot* periódico
  * *Snapshot* acumulativo

---

## 1. No Todas las Medidas se Pueden Sumar
Distinción crítica que causa errores reales en reportes de producción:

| Tipo | Se puede sumar... | Ejemplo |
| :--- | :--- | :--- |
| **Aditiva** | Por todas las dimensiones | Monto vendido, distancia recorrida |
| **Semi-aditiva** | Por algunas dimensiones, pero **no por tiempo** | Saldo de inventario, saldo de cuenta bancaria |
| **No aditiva** | Por ninguna dimensión | Porcentajes, razones, promedios, ratios |

> ⚠️ **Regla de oro con medidas no aditivas:**  
> **Nunca guarden el porcentaje precalculado.** Guarden el numerador y el denominador como medidas aditivas separadas en la tabla de hechos, y calculen la razón/división dinámicamente al consultar.

---

### Ejemplos Detallados de Medidas

#### A. Medida Aditiva: *Monto Vendido*
*Cuatro entregas:*
* **Zona 10:** Lunes (Q100), Martes (Q150)
* **Mixco:** Lunes (Q80), Martes (Q120)

* **Sumar por zona (juntar días):** Zona 10 vendió Q250. *(Correcto)*
* **Sumar por tiempo (juntar zonas):** El lunes se vendió Q180. *(Correcto)*
* **Sumar todo:** Q450 en total. *(Correcto)*

---

#### B. Medida Semi-aditiva: *Saldo de Inventario*
*Unidades en existencia al cierre de cada día:*
* **Bodega A:** Lunes (100 unidades), Martes (100 unidades)
* **Bodega B:** Lunes (60 unidades), Martes (60 unidades)

* ✅ **Correcto (por espacio/bodega):** Sumar Bodega A + Bodega B el lunes = 160 unidades en la empresa.
* ❌ **Falso (por tiempo):** Sumar Lunes + Martes de la Bodega A daría 200. **Son las mismas 100 unidades contadas dos veces.**

> **El Patrón:** Todo lo que es un *saldo* (inventario, saldo bancario, empleados activos, socios activos) mide **cuánto hay en un momento**, no cuánto ocurrió a lo largo del tiempo.

---

#### C. Medida No Aditiva: *Porcentaje de Entregas a Tiempo*

| Zona / Bodega | A tiempo | Total | % Directo |
| :--- | :---: | :---: | :---: |
| **Zona 10** | 9 | 10 | 90% |
| **Mixco** | 500 | 1,000 | 50% |

* ❌ **Absurdo (Sumar porcentajes):** $90\% + 50\% = 140\%$
* ❌ **Falso (Promediar porcentajes):** $(90\% + 50\%) / 2 = 70\%$ *(Le da el mismo peso a una zona con 10 entregas que a una con 1,000)*
* ✅ **Cálculo Real:** 
  $$rac{9 + 500}{10 + 1000} = rac{509}{1010} pprox 50.4\%$$

---

## 2. Claves Sustitutas (*Surrogate Keys*): ¿Por Qué No la Llave del Origen?

En una dimensión, la llave primaria (**PK**) **no debe ser el `cliente_id`** del sistema transaccional / operacional. Debe ser una **clave sustituta**: una llave nueva, entera, autoincremental/secuencial generada por el Data Warehouse, sin significado de negocio.

### Tres Razones Principales:
1. **Historia (SCD Tipo 2):** Con Slowly Changing Dimensions Tipo 2, el mismo cliente tiene varias filas vigentes en distintos periodos. Si la PK fuera `cliente_id`, se repetiría violando la unicidad.
2. **Integración:** El cliente `4471` en el ERP puede ser el `8890` en el CRM. La clave sustituta los unifica.
3. **Independencia:** Si mañana migran de sistema de origen y cambian todos los IDs operacionales, el Data Warehouse no se ve afectado.

---

### Ejemplo de SCD Tipo 2:
El cliente `4471` (Ana Cruz) se muda de **Zona 10** a **Mixco**.

#### ❌ Si la llave fuera la natural (`cliente_id`):
| cliente_id (PK) | nombre | zona | vigencia |
| :---: | :---: | :---: | :---: |
| 4471 | Ana Cruz | Zona 10 | 2025-01 a 2026-08 |
| 4471 | Ana Cruz | Mixco | 2026-08 a hoy |

*El ID `4471` aparece dos veces: **rompe la PK**. El hecho no sabría a cuál versión apuntar.*

#### ✅ Con Clave Sustituta (`dim_cliente`):
| cliente_key (PK) | cliente_id | zona | es_actual |
| :---: | :---: | :---: | :---: |
| **8801** | 4471 | Zona 10 | No |
| **8802** | 4471 | Mixco | Sí |

#### Tabla de Hechos (`hechos_pedidos`):
| pedido_id | cliente_key | fecha | monto |
| :---: | :---: | :---: | :---: |
| 1001 | **8801** | 2026-03-14 | Q150.00 |
| 1002 | **8802** | 2026-09-02 | Q220.00 |

* **Resultado:** El pedido de marzo apunta a `8801` (cuando vivía en Zona 10) y el de septiembre a `8802`. El reporte histórico de marzo sigue atribuyendo la venta a Zona 10 fielmente.

---

## 3. Una Dimensión, Varios Papeles (*Role-Playing Dimensions*)
Ocurre cuando una misma tabla de dimensión es referenciada múltiples veces desde una misma tabla de hechos con significados o roles distintos.

### Ejemplo: Ciclo de Vuelos / Pedidos
En `hechos_ciclo_pedido`:
* `fecha_creado_key` $ightarrow$ `dim_tiempo`
* `fecha_recogido_key` $ightarrow$ `dim_tiempo`
* `fecha_entregado_key` $ightarrow$ `dim_tiempo`

En `hechos_vuelos`:
* `aeropuerto_origen_key` $ightarrow$ `dim_aeropuerto`
* `aeropuerto_destino_key` $ightarrow$ `dim_aeropuerto`

> **Solución:** **No se crean tres tablas físicas de tiempo o de aeropuertos.** Es una sola dimensión física, referenciada múltiples veces mediante **alias de tabla** en SQL o vistas lógicas en la capa de BI.

---

## 4. Esquema Estrella vs. Esquema Copo de Nieve

```
      [Dimensión]       [Dimensión]
            \               /
             \             /
         [  TABLA DE HECHOS  ]
             /                         /                     [Dimensión]       [Dimensión]
```

### Esquema Estrella (*Star Schema*)
* Una tabla de hechos al centro rodeada de dimensiones **desnormalizadas (planas)**.
* Cada dimensión está a exactamente **un solo JOIN** de distancia.
* **Ventajas:**
  * Consultas simples y rápidas (los analistas no tienen que navegar grafos complejos de tablas).
  * Motores analíticos y herramientas de BI (Power BI, Tableau, Looker) están altamente optimizados para este diseño.

---

### Esquema Copo de Nieve (*Snowflake Schema*)
* Es un esquema estrella donde las dimensiones se han **normalizado** en subtablas (ej. `Producto` $ightarrow$ `Subcategoría` $ightarrow$ `Categoría`).
* **Desventajas:** Casi siempre es peor: requiere más JOINs, es más difícil de entender para el negocio y en motores columnares modernos el ahorro de espacio en disco es prácticamente insignificante.
* **¿Cuándo sí tiene sentido normalizar?:**
  1. Jerarquías enormes compartidas entre múltiples modelos que cambian con mucha frecuencia.
  2. Dimensiones con decenas de millones de filas donde la redundancia textual impacte severamente.
  3. Motores relacionales tradicionales orientados a filas (*row-oriented*) con limitaciones de almacenamiento.

*(Nota: El nombre del patrón arquitectónico "Copo de nieve" no tiene relación con Snowflake Inc., la plataforma de Data Cloud).*

---

## 5. Varias Tablas de Hechos: El Error que NUNCA Deben Cometer

### ❌ El Error Fatal: JOIN Directo entre Tablas de Hechos
```sql
-- ¡NUNCA HAGAN ESTO!
SELECT ...
FROM hechos_entregas e
JOIN hechos_cobros c ON e.pedido_id = c.pedido_id;
```
* **Por qué falla:** Tienen **granos distintos**. Si un pedido tuvo 3 entregas parciales y 2 pagos, el JOIN cartesiano a nivel de detalle produce **$3 	imes 2 = 6$ filas**.
* **Lo peligroso:** La consulta **no da error de sintaxis**, corre y devuelve números inflados pero plausibles. Nadie se entera hasta que los reportes de contabilidad y operaciones no cuadran.

---

### ✅ La Solución Correcta: *Drill-Across*
El método *Drill-Across* sigue 3 pasos:
1. **Consultar y agregar cada tabla de hechos por separado** hasta alcanzar un grano común.
2. Expresar ese grano común usando las **dimensiones compartidas** (ej. `zona` y `mes`).
3. **Unir los resultados agregados** a través de esas dimensiones conformadas.

```
Paso 1: Agregar Hechos A        Paso 1: Agregar Hechos B
[ hechos_entregas ]             [ hechos_cobros ]
      │                               │
      ▼                               ▼
Resumen A (por Zona 10)         Resumen B (por Zona 10)
Monto = Q300                    Pagado = Q300
      │                               │
      └───────────────┬───────────────┘
                      ▼
Paso 2: Unir agregados por dimensión común
       [ Zona 10 | Q300 | Q300 ] (Correcto)
```

> 💡 *Las herramientas de BI modernas resuelven el drill-across automáticamente en su capa semántica siempre y cuando el modelo esté bien diseñado.*

---

## 6. Dimensiones Conformadas y la Matriz del Bus

* **Dimensión Conformada:** Es una dimensión que significa exactamente lo mismo en cualquier lugar donde se utilice: mismas claves sustitutas, mismos nombres de atributos y mismas definiciones de negocio.
* **Matriz del Bus:** Es la herramienta estratégica de diseño dimensional para planificar el Data Warehouse corporativo antes de crear tablas físicas.

### Ejemplo de Matriz del Bus:

| Proceso de Negocio (Filas) | Dimensión: Tiempo | Dimensión: Ubicación | Dimensión: Repartidor | Dimensión: Cliente |
| :--- | :---: | :---: | :---: | :---: |
| **Entregas** | 🟩 | 🟩 | 🟩 | 🟩 |
| **Cobros** | 🟩 | 🟩 | ⬜ | 🟩 |
| **Calificaciones** | 🟩 | ⬜ | 🟩 | 🟩 |

* 🟩 = El proceso utiliza la dimensión.
* ⬜ = La dimensión no participa en el proceso.

### Reglas de Lectura de la Matriz:
* **Entregas + Cobros:** Se pueden cruzar por **Tiempo, Ubicación y Cliente**. *(¿Cuánto entregamos y cuánto cobramos por zona y mes?)*.
* **Cobros + Calificaciones:** Se pueden cruzar por **Tiempo y Cliente**. Cruzarlos por Repartidor **no tiene sentido** porque Cobros no tiene relación con Repartidor.

---

## 7. Dos Casos que Rompen la Estrella Simple

### Caso A: Relaciones Muchos a Muchos (Puente con Factor de Ponderación)
* **Problema:** El pedido `1001` costó Q300 y tuvo aplicadas **dos promociones** (`P-01: 2x1` y `P-07: Envío gratis`). Una clave foránea directa en la tabla de hechos no puede apuntar a dos filas.
* ❌ **Solución Mala:** Duplicar la fila en la tabla de hechos por cada promoción $ightarrow$ La suma del monto pasaría falsamente de Q300 a Q600.
* ✅ **Solución Correcta (Tabla Puente con Factor):**

```
[ hechos_pedidos ] ──1:N──> [ puente_pedido_promocion ] <──N:1── [ dim_promocion ]
                              - pedido_id
                              - promocion_key
                              - factor (ej. 0.5)
```

$$	ext{Ventas por Promoción} = \sum (	ext{monto} 	imes 	ext{factor})$$

> **Nota:** El factor de asignación (50/50, proporcional al descuento o 100% a la principal) es una **decisión del negocio**, no del ingeniero, y debe estar rigurosamente documentada.

---

### Caso B: Tablas de Hechos sin Hechos (*Factless Fact Tables*)
* Tablas de hechos que **no contienen medidas numéricas**, únicamente claves foráneas a dimensiones.
* **Propósito:** Registrar que un evento ocurrió (ej. asistencia a clases) o registrar condiciones de cobertura/vigencia (ej. promociones activas por tienda y fecha).
* Se consultan mediante `COUNT(*)`, no con `SUM()`.
* **Uso contraintuitivo principal:** Responder **por lo que NO pasó** (ej. identificar qué promociones estuvieron activas todo el mes pero ningún cliente utilizó).

---

## 8. Cómo se Optimiza un Modelo Dimensional

> ⚠️ **Principio de optimización:**  
> *"Si no midieron el antes y el después, no optimizaron: solo supusieron."*  
> **Orden estricto:** 1° Modelo conceptual correcto $ightarrow$ 2° Medición de cuellos de botella $ightarrow$ 3° Optimización técnica.

| Palanca | Qué hace a nivel de motor |
| :--- | :--- |
| **Particionar por fecha** | La consulta lee únicamente los bloques de datos del rango de fechas solicitado (*Partition Pruning*). |
| **Ordenar / Agrupar por dimensiones más filtradas** | El motor descarta bloques enteros de almacenamiento sin necesidad de abrirlos (*Clustering / Z-Order*). |
| **Tablas de hechos agregadas** | Los tableros ejecutivos leen resúmenes precalculados en lugar de escanear miles de millones de filas de detalle. |
| **Materialización incremental** | Los pipelines de carga procesan solo registros nuevos o modificados, no la historia completa. |
| **Mantener el hecho angosto** | Eliminar cualquier texto descriptivo de la tabla de hechos; únicamente claves foráneas y números. |

---

## 9. ¿Cuándo NO Usar Modelo Dimensional?

1. **Capa de *Features* para Machine Learning:**
   * El Feature Engineering requiere una sola fila por entidad/predicción con cientos o miles de columnas analíticas, y requiere detalle atómico crudo sin el grano impuesto por una estrella.
2. **Exploración Ad-Hoc Temprana:**
   * Cuando los usuarios de negocio aún no saben qué preguntas van a formular; el modelo dimensional optimiza patrones de consulta conocidos.
3. **Un Solo Consumidor / Dashboard Aislado:**
   * Si solo existe un tablero puntual, una tabla plana y ancha (*One Big Table - OBT*) es más simple y económica de construir. El costo del modelo dimensional se justifica con múltiples consumidores.
4. **Volumen de Datos Pequeño:**
   * Si las consultas sobre el modelo operacional normalizado tardan menos de 200 ms, no justifique ingeniería adicional ni complejidad innecesaria.

---

## 10. Mapeo: 5 Técnicas Clásicas vs. Modelo Dimensional

| Técnica Clásica | En qué se convirtió en Diseño Dimensional |
| :--- | :--- |
| **Pre-join** | La **tabla de dimensión** (una dimensión es una jerarquía aplanada y desnormalizada). |
| **Columnas derivadas** | Las **medidas calculadas** de la tabla de hechos. |
| **Tablas agregadas** | **Tablas de hechos agregadas** (donde el nivel de resumen define el nuevo grano). |
| **Estructuras anidadas (JSON/Arrays)** | **No encaja.** Nació con los motores columnares dos décadas después de Ralph Kimball y compite con la estrella. |
| **Vistas materializadas** | **Ortogonal.** Define dónde y cómo se almacena físicamente el resultado, no su estructura lógica. |

---

## 📝 Tarea Práctica

1. **Dibujar la Matriz del Bus** del modelo de la aplicación seleccionada en la entrega previa.
2. **Responder:**
   * ¿Qué dos procesos de negocio se pueden cruzar y a través de cuáles dimensiones conformadas?
   * ¿Cuál cruce de procesos **no** tendría sentido de negocio y por qué?
3. **Recordatorios para la entrega:**
   * Grano primero y una sola tabla de hechos por proceso.
   * Las tablas de hechos nunca se unen directamente: se alinean por dimensiones conformadas.
   * Optimización al final y siempre con métricas de rendimiento comparativas.
