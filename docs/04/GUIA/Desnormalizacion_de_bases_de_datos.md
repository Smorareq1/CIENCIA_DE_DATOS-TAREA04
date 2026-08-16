# Desnormalización de bases de datos

**Ciencia de Datos 2026 --- Sección 2**\
**Ing. Max Cerna**

------------------------------------------------------------------------

## Página 1

DESNORMALIZACIÓN DE BASES DE DATOS Ciencia de Datos 2026 --- Sección 2
Ing. Max Cerna

------------------------------------------------------------------------

## Página 2

Agenda de hoy Qué significa realmente desnormalizar (y qué no)

Cinco técnicas: pre-join, columnas derivadas, tablas agregadas,
estructuras anidadas y vistas materializadas

Dos trampas: fan-out y la tabla que nadie entiende

Criterios para decidir cuándo no desnormalizar

Reto sobre el modelo de Ruta Verde

------------------------------------------------------------------------

## Página 3

De dónde venimos Un warehouse se organiza en capas: staging → core →
marts

       Desnormalizamos porque cada join cuesta y porque
       el dato del warehouse es una copia que se puede
       volver a generar, no el original
           si además el motor guarda por columnas, la
           redundancia casi ni pesa


       Un warehouse historiza (SCD), no sobrescribe

Ahora ya aceptamos que desnormalizar está justificado La pregunta es
cómo se hace bien?, y la respuesta es: porque hacerlo mal produce
números incorrectos ademas de lentos

------------------------------------------------------------------------

## Página 4

Resumen DB1 asumiendo que ya vieron formas normales en Bases de Datos:

                 1FN                                      2FN                                 3FN

valores atómicos, sin grupos sin dependencias parciales de sin
dependencias transitivas (un atributo no clave que depende de otro
atributo no repetidos una clave compuesta clave)

------------------------------------------------------------------------

## Página 5

Resumen DB1 1FN un solo valor por celda

------------------------------------------------------------------------

## Página 6

Resumen DB1 El síntoma: si sube el precio de la pizza, 2FN tienes que
actualizarlo en cada fila donde nada debe depender de solo parte de la
llave aparezca. Y no puedes registrar un producto Considerando una tabla
llamada detalle_pedido, nuevo hasta que alguien lo pida. con llave
compuesta (pedido_id, producto_id)

cantidad sí depende de las dos partes de la llave: necesitas La
Solucion: dos tablas

saber qué pedido y qué producto. Pero nombre_producto y detalle_pedido

precio dependen solo de producto_id, Esa es la dependencia (pedido_id,
producto_id, cantidad)

parcial producto (producto_id, nombre, precio)

------------------------------------------------------------------------

## Página 7

Resumen DB1 El síntoma: el restaurante cambia de nombre, 3FN tocas miles
de filas de pedidos. Y si borras el nada debe depender de otro campo que
no sea la llave último pedido de un restaurante, pierdes que

            Considerando una tabla pedido, llave pedido_id           ese restaurante existía.

Aquí la cadena es: pedido_id → restaurante_id → nombre_restaurante El
nombre no depende del pedido, depende del restaurante Eso es la
dependencia transitiva La Solucion: pedido (pedido_id, restaurante_id,
fecha, total) restaurante (restaurante_id, nombre, zona)

------------------------------------------------------------------------

## Página 8

La regla mnemotécnica "The key, the whole key, and nothing but the key,
so help me Codd" William Kent (1983)

Cada atributo no clave debe depender de la llave, de toda la llave y de
nada más que la llave

Se mapea exacto: de la llave → 1FN de toda la llave → 2FN de nada más
que la llave → 3FN

------------------------------------------------------------------------

## Página 9

Desnormalizar no es "no normalizar" Si no sabes qué consulta se vuelve
más Desnormalizar = introducir deliberadamente dependencias que 3FN
prohíbe, a rápida, no estás cambio de rendimiento de lectura
desnormalizando: estás repitiendo datos Error común: creer que
desnormalizar es diseñar sin criterio, o "tirar todo en porque sí una
tabla"

Lo correcto: se parte de un modelo normalizado y se relaja de forma
controlada y documentada, técnica por técnica, con una justificación por
cada decisión

------------------------------------------------------------------------

## Página 10

Técnica 1: Pre-join (aplanar jerarquías) Colapsar en una sola tabla lo
que estaba repartido en varias por relaciones 1-a-muchos hacia arriba

Ejemplo: En ruta verde pedido → restaurante → zona → municipio →
departamento

se guarda en la misma fila: zona, municipio, departamento

Gana: elimina 3-4 joins en cada consulta geográfica Cuesta: el nombre
del departamento se repite en millones de filas

------------------------------------------------------------------------

## Página 11

Técnica 1: Pre-join (aplanar jerarquías)

------------------------------------------------------------------------

## Página 12

Técnica 2: Columnas derivadas o precalculadas Almacenar el resultado de
un cálculo en lugar de computarlo en cada consulta

Ejemplo: El pedido 1001 tiene tres líneas de detalle. Cada vez que
alguien pregunta el total, calcula (2×85) + (1×15) + (1×50) = 235.00 y
es guardado en la tabla de pedidos. Otras columnas derivadas típicas:
duracion_entrega_min, dia_semana, es_hora_pico

Gana: la consulta deja de calcular y deja de necesitar el join al
detalle Cuesta: si mañana se corrige la cantidad de Pizza de 2 a 3, el
detalle suma el ETL debe garantizar que ambos se 320.00 pero
total_pedido sigue diciendo 235.00 actualicen juntos

------------------------------------------------------------------------

## Página 13

Técnica 2: Columnas derivadas o precalculadas

------------------------------------------------------------------------

## Página 14

Técnica 3: Tablas agregadas Materializar de antemano los resúmenes más
consultados, en vez de agregar sobre el detalle completo

Ejemplo: En ruta verde además dela tabla entregas_hechas (una fila por
entrega), mantener entregas_por_zona_dia (una fila por zona y día)

Gana: un dashboard que consultaba 200 millones de filas ahora consulta
Demasiado agregado y ya no puedes 50 mil responder preguntas nuevas, muy
poco y no Cuesta: hay que decidir la granularidad correcta. ganaste nada

------------------------------------------------------------------------

## Página 15

Técnica 3: Tablas agregadas

------------------------------------------------------------------------

## Página 16

Técnica 4: Estructuras anidadas (la versión moderna) El problema del
aplanado clásico: si un pedido tiene 5 productos y aplanas todo en una
tabla, ese pedido ocupa 5 filas, y sus datos de cabecera se repiten 5
veces, eso es explosión de filas

La alternativa moderna: los warehouses columnares (BigQuery, Snowflake,
Redshift) y el formato Parquet soportan tipos anidados: ARRAY y STRUCT

                                                                       Demasiado agregado y ya no puedes

Un pedido = una sola fila, con una columna productos que contiene un
responder preguntas nuevas, muy poco y no arreglo de estructuras ganaste
nada

------------------------------------------------------------------------

## Página 17

Técnica 4: Estructuras anidadas

------------------------------------------------------------------------

## Página 18

Técnica 5: Vistas materializadas y materializaciones

Vista normal: se ejecuta la consulta cada vez (no gana rendimiento, sí
legibilidad)

Vista materializada: el resultado se guarda físicamente y se refresca
según una política

Gana: desnormalización declarativa, versionada en Git, reproducible

Cuesta: hay que definir cuándo y cómo se refresca, datos "frescos" es un
requisito de negocio, no técnico

------------------------------------------------------------------------

## Página 19

Técnica 5: Vistas materializadas y materializaciones

------------------------------------------------------------------------

## Página 20

¿Hay que usar las cinco? Son un menú, no una receta

Un modelo puede usar una técnica, tres, o ninguna

Y se pueden combinar: una misma tabla puede tener pre-join, una columna
derivada y carga incremental a la vez

                                   Si el síntoma es…                             La técnica es

La consulta encadena muchos joins para llegar a un atributo 1. Pre-join

El mismo cálculo se repite en cada consulta 2. Columna derivada

Una consulta recurrente recorre millones de filas para devolver pocas 3.
Tabla agregada

Una fila se multiplica solo porque tiene varios hijos 4. Estructuras
anidadas

La transformación se repite y hay que versionarla 5. Vista materializada

------------------------------------------------------------------------

## Página 21

¿Hay que usar las cinco? Cómo se aplican, en orden: 1.Empieza
normalizado: Siempre, la desnormalización es una corrección, no un punto
de partida 2.Mide: ¿Qué consulta duele de verdad? Frecuencia × costo, no
intuición 3.Elige por síntoma, con la tabla de arriba 4.Documenta el
trade-off: qué gano, qué pierdo, por qué acepto esa pérdida 5.Vuelve a
medir: Si no mejoró, revierte.

Se desnormaliza en la capa que consume el negocio (los marts, el Gold
como el del Laboratorio 2) no en la capa de integración, donde la
prioridad sigue siendo corrección e historia

------------------------------------------------------------------------

## Página 22

Trampa 1: fan-out y doble conteo El error más caro de la
desnormalización mal hecha

        pedido               total            producto


         1001                Q150               Pizza


         1001                Q150               Bebida


         1001                Q150               Postre

SUM(total) = Q450, cuando la venta real fue Q150

El reporte no falla, devuelve un número, y es incorrecto. Ese es el
peligro: no hay error, hay una mentira plausible.

------------------------------------------------------------------------

## Página 23

Trampa 2: la tabla que nadie entiende El anti-patrón: una tabla de 300
columnas, generada por acumulación de pedidos puntuales ("agrégame esta
columna"), sin documentación ni dueño

Síntomas típicos: Tres columnas que parecen lo mismo: fecha,
fecha_carga, fecha_evento Nadie sabe cuál usar, así que cada analista
elige distinto entonces dos reportes con números diferentes Nadie se
atreve a borrar nada por miedo a romper algo

La desnormalización sin gobernanza reproduce el problema del data swamp,
pero dentro del warehouse

------------------------------------------------------------------------

## Página 24

¿Cuándo NO desnormalizar? Heurísticas prácticas: El dato cambia con
mucha frecuencia - cada cambio obliga a actualizar N copias La consulta
que querías acelerar ya es rápida - estás pagando complejidad sin
beneficio No sabes qué consultas se van a hacer - desnormalizar es
optimizar para un patrón conocido, sin patrón, mantén el modelo flexible
Estás en la capa de integración (core), no en la de consumo - ahí la
prioridad es corrección e historia, no velocidad La ganancia no está
medida - si no comparaste el antes y el después, es una suposición, no
una optimización

     Regla al trabajar: primero normalizado y correcto, después
    medido, y solo entonces desnormalizado donde la medición lo
                              justifique

------------------------------------------------------------------------

## Página 25

Ruta Verde - ER (3FN)

------------------------------------------------------------------------

## Página 26

RETO (GRUPO DE 3) Tres consultas que el negocio pide a diario: 1.Ventas
totales por zona y por mes (dashboard gerencial) 2.Tiempo promedio de
entrega por repartidor, últimos 7 días 3.Qué productos se piden juntos
con más frecuencia (análisis exploratorio, no recurrente)

Para cada una decidan: ¿desnormalizarían? ¿con qué técnica de las cinco
vistas? ¿qué riesgo introduce?

NOTA: No recurrente significa que la consulta se corre una vez, o muy de
vez en cuando. Exploratoria significa que quien pregunta todavía no sabe
bien qué busca

------------------------------------------------------------------------

## Página 27

Tarea Desnormalización de bases de datos Aplicarán las técnicas de hoy
sobre un modelo dado, documentando por cada decisión: qué consulta
mejora, qué redundancia introduce y qué riesgo asume

------------------------------------------------------------------------

## Página 28

Resumen Desnormalizar es un catálogo de técnicas, no la ausencia de
diseño

Cinco herramientas: pre-join, columnas derivadas, tablas agregadas,
estructuras anidadas, vistas materializadas

Dos trampas: fan-out (números incorrectos que parecen correctos) y
tablas sin gobernanza

Toda desnormalización debe poder responder: ¿qué consulta específica
mejora y a qué costo?
