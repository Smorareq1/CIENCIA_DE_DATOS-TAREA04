# Diseño Dimensional (Parte 1)

**Ciencia de Datos 2026 --- Sección 2**\
**Ing. Max Cerna**

------------------------------------------------------------------------

## Página 1

DISEÑO DIMENSIONAL

C I E N C I A D E D A T O S 2 0 2 6

S E C C I Ó N 2

I N G . M A X C E R N A

(PARTE 1)

------------------------------------------------------------------------

## Página 2

AGENDA DE HOY

Lo que hicieron la clase pasada ya era modelado

dimensional

Diagnóstico rápido: ¿siguen distinguiendo 1FN, 2FN y 3FN?

Sustantivos o verbos: dos formas de listar las mismas tablas

Las dos piezas: hechos y dimensiones

El grano: la decisión que no se corrige después

¿Una sola tabla de hechos? ¿Cuándo creo otra?

Los tres tipos de tabla de hechos

Actividad: diseño bajo reglas de normalización

------------------------------------------------------------------------

## Página 3

Lo que hicieron

Cómo se llama

Aplanaron la jerarquía geográfica en una tabla

Construyeron una dimensión

Precalcularon el total del pedido

Definieron una medida del hecho

Resumieron por zona y día

Cambiaron el grano (grain)

Sumaron Q450 donde iban Q150 (error)

Mezclaron dos granos en una tabla

LO QUE HICIERON LA CLASE

PASADA YA ERA ESTO

La Clase anteior resolvió el problema por intuición y caso por caso.

Cada decisión que tomaron tiene un nombre formal:

L a s c i n c o t é c n i c a s r e s p o n d e n

" ¿ c ó m o a c e l e r o e s t a c o n s u l t a ? "

E l m o d e l o d i m e n s i o n a l r e s p o n d e

" ¿ c ó m o o r g a n i z o e l w a r e h o u s e p a r a q u e

c u a l q u i e r c o n s u l t a f u t u r a s e a f á c i l ? "

------------------------------------------------------------------------

## Página 4

DIAGNÓSTICO DE PROBLEMAS DE NORMALIZACION

POR CADA TABLA: ¿CUMPLE 3FN? SI NO, ¿QUÉ REGLA ROMPE?

promocion (promocion_id, nombre, zona_1, zona_2, zona_3)

asignacion_turno (repartidor_id, fecha, nombre_repartidor,
tipo_vehiculo, horas)

incidente (incidente_id, entrega_id, descripcion, codigo_severidad,
texto_severidad)

entrega(entrega_id, repartidor_id, fecha_hora, distancia_km)

Recuerden → "The key, the whole key, and nothing but the key --- so help
me Codd"

------------------------------------------------------------------------

## Página 5

SUSTANTIVOS O VERBOS:

DOS FORMAS DE LISTAR LAS MISMAS TABLAS

¿QUÉ TABLAS TENEMOS DE RUTA VERDE?

cliente

restaurante

producto

pedido

repartidor

zona

¿QUÉ MIDE RUTA VERDE?

entregar un pedido

calificar una entrega

cobrar

dónde vive "cuánto tardó la entrega" en cada modelo

------------------------------------------------------------------------

## Página 6

SUSTANTIVOS O VERBOS:

DOS FORMAS DE LISTAR LAS MISMAS TABLAS

DÓNDE VIVE "CUÁNTO TARDÓ LA ENTREGA" EN CADA

MODELO

En el de sustantivos: en ningún lado

Hay que derivarla de marcas de tiempo

repartidas entre tablas

En el de verbos: es una medida del proceso

entregar

Vive en su tabla de hechos, ya calculada

La lista de verbos es el modelo dimensional

Cada proceso será una tabla de hechos

y los sustantivos pasan a ser sus

dimensiones

Modelar por entidades (ER clasico) responde

"¿qué existe?"

Modelar por procesos responde "¿qué pasó

y cuánto?"

para diseñar dimensional, empiecen listando verbos, no sustantivos

el modelo normalizado no es el rival del dimensional, es su punto de
partida

------------------------------------------------------------------------

## Página 7

LAS DOS PIEZAS: HECHOS Y DIMENSIONES

HECHOS

lo que se mide: montos, cantidades,

duraciones, distancias

DIMENSIONES

el contexto de esa medición: quién,

cuándo, dónde, qué

Toda pregunta de negocio tiene esta forma: una medida, cortada por un
contexto

"Ventas (hecho) por zona y por mes (dimensiones)"

Si te sirve para sumar, es un hecho, si te sirve para filtrar o agrupar,
es una dimensión

------------------------------------------------------------------------

## Página 8

LAS DOS PIEZAS: HECHOS Y DIMENSIONES

------------------------------------------------------------------------

## Página 9

LA PRIMERA DECISIÓN: EL GRANO

EL GRANO ES EL QUÉ REPRESENTA UNA SOLA FILA DE LA TABLA DE HECHOS

Se declara en una frase, en presente, sin agregaciones:

"Una fila = una línea de detalle dentro de un pedido"

"Una fila = una entrega completada"

"Una fila = un evento GPS reportado por un repartidor"

------------------------------------------------------------------------

## Página 10

EL GRANO ES IRREVERSIBLE

EL GRANO DETERMINA QUÉ PREGUNTAS PODRÁ RESPONDER EL

MODELO PARA SIEMPRE

Si el grano es "una fila por zona y por día", la pregunta "¿qué pasó

el martes entre 6 y 7 de la tarde?" ya no tiene respuesta y no hay

forma de recuperarla sin rehacer el modelo desde el origen

Regla práctica: ante la duda, elige el grano más fino que la fuente

permita. Siempre puedes agregar hacia arriba; nunca puedes

desagregar hacia abajo.

La tabla que sumaba Q450 en el ejemplo de la diapositiva anterior cuando
la venta real fue Q150

tenía dos granos conviviendo: el total del pedido junto a las líneas de
detalle

no es un error de SQL, es un error de grano que aparece al consultar

------------------------------------------------------------------------

## Página 11

¿HAY UNA SOLA TABLA DE HECHOS EN EL WAREHOUSE?

NO, HAY UNA POR PROCESO DE NEGOCIO

En Ruta Verde no se mide una sola cosa:

mide entregas, mide cobros, mide calificaciones

Cada uno es un proceso distinto, con su propio grano y sus propias

medidas

hechos_entregas

grano: una entrega completada

hechos_cobros

grano: un pago recibido

hechos_calificaciones

grano: una calificación enviada

ya vimos qué pasa cuando dos granos

comparten tabla, por eso, una tabla de

hechos por proceso

------------------------------------------------------------------------

## Página 12

¿CUÁNDO CREO UNA TABLA DE HECHOS NUEVA?

LA REGLA ES UNA SOLA: GRANO DISTINTO, TABLA DISTINTA

Preguntas que la resuelven en la práctica:

Situación

¿Tabla nueva?

Mido un proceso de negocio diferente

Si

Mismo proceso, pero una fila significa otra cosa

Si

Mismo grano, solo quiero agregar una medida más

No --- agrega una columna

Quiero el mismo dato resumido por mes

Sí, pero agregada

Error Típico:

Crear una tabla de hechos por

cada

reporte

que

pide

la

gerencia.

Terminan con veinte tablas casi

iguales que nadie sabe cuál usar

------------------------------------------------------------------------

## Página 13

LOS TRES TIPOS DE TABLA DE HECHOS

No todos los procesos se miden igual

Kimball distingue tres formas, y elegir mal la forma es un error de
diseño que no se arregla con SQL

Tipo

Una fila representa

Se actualiza

Ejemplo en Ruta Verde

Transaccional

un evento que ocurrió

nunca, solo se inserta

cada entrega completada

Snapshot periódico

el estado en un corte de tiempo

se inserta una foto por periodo

pedidos pendientes al cierre de

cada día

Snapshot

acumulativo

un proceso completo con varios hitos

sí, la misma fila se actualiza

un pedido: creado → asignado →

recogido → entregado

------------------------------------------------------------------------

## Página 14

LOS TRES TIPOS DE TABLA DE HECHOS

EL TERCERO ES EL QUE MÁS SE NECESITA Y CASI NO SE ENSEÑA

El tercero sirve para

medir cuánto tarda cada

etapa

Dimensión degenerada

Es aquel identificador

que vive en el hecho sin

dimensión detrás

Por ejemplo:

El pedido_id en esa tabla

no apunta a ninguna

dimensión, no hay una

dim_pedido con atributos

que describir

------------------------------------------------------------------------

## Página 15

TAREA

UN SOLO ENTREGABLE. GRUPOS DE 3, LOS MISMOS DE LA CLASE PASADA

Utilicen el modelo en 3FN que su grupo construyó para la app que
eligieron (Spotify, Uber,

Waze, la app del banco). El mismo que presentaron y desnormalizaron

En clase:

Declaren el grano de su proceso, en una sola frase, en presente y sin
agregaciones

Clasifiquen cinco campos como hecho o dimensión, con la prueba de sumar
contra filtrar

Marquen uno donde la clasificación no sea obvia y expliquen por qué

------------------------------------------------------------------------

## Página 16

TAREA

UN SOLO ENTREGABLE. GRUPOS DE 3, LOS MISMOS DE LA CLASE PASADA

En casa:

Hagan las desnormalizacion correctamente esta vez, documenten cada
descomposición:

qué dependencia estaban rompiendo y en qué tablas quedó repartida

Elijan el tipo de tabla de hechos: transaccional, snapshot periódico o
acumulativo y

justifiquen en una frase

Cierren el círculo: ¿alguna de las desnormalizaciones que hicieron la
clase pasada

contradice el grano que acaban de declarar? Si sí, ¿cuál gana y por qué?

No dibujen todavía el modelo dimensional, eso es la próxima clase, y
esta hoja es su punto de partida

------------------------------------------------------------------------

## Página 17

RESUMEN

Para diseñar dimensional, empiecen listando verbos, no sustantivos:

los procesos serán hechos, las entidades serán dimensiones

Dos piezas: hechos (lo que se mide) y dimensiones (el contexto)

El grano es la primera decisión y la única que no se corrige después

El fan-out de la clase anterior no era un error de SQL: era un error de
grano

Las cinco técnicas de la clase pasada no se reemplazan: se vuelven
sistemáticas

Hay una tabla de hechos por proceso de negocio, no una sola, y grano
distinto significa tabla

distinta

Tres formas de medir un proceso: transaccional, snapshot periódico y
snapshot acumulativo

------------------------------------------------------------------------
