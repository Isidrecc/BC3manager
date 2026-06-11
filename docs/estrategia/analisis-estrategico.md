# Framework de estudio de viabilidad — Editor de presupuestos `.bc3` con IA integrada

> **Propósito.** Estructura analítica reutilizable para que Claude ejecute un estudio exhaustivo y trazable de la idea de producto. No es el estudio en sí: es el guion, las preguntas a responder, las lentes de análisis y la metodología de verificación. Cada bloque indica *qué responder*, *cómo investigarlo* y *qué fuente usar*.
>
> **Cómo usarlo.** Ejecutar por fases (no todo de golpe). Sugerido: Fase A (definición + mercado + competencia) → Fase B (cliente + propuesta de valor + técnico/regulatorio) → Fase C (DAFO + modelo de negocio + decisión de segmento + roadmap). Cada hallazgo debe ir con fuente y fecha.

---

## 0. Resumen de la decisión a resolver

El estudio debe analizar los siguientes puntos:

1. Propuesta de decisión: **Go / No-Go / Pivote** sobre los distintos mercados.
2. Análisis de los **segmentos de entrada** del producto: 
	1. *Redacción de proyectos*
	2. *Gestión de obra
	3. Análisis de licitaciones
	4. Elaboración de presupuestos para pequeños subcontratistas
	5. etc.
3. Análisis de la **industria de entrada**:
	1. Obra civil
	2. Edificación
	3. Pequeña rehabilitación (cambios de baño, embaldosados, parquets, etc.)
4. Propuesta de inicio del producto.

Todo el análisis se ordena para alimentar la matriz de decisión del **Bloque 11**.

---

## 1. Objetivo y preguntas de investigación

Definir explícitamente qué tiene que contestar el estudio. Preguntas maestras:

- ¿Existe un dolor real, frecuente y caro que la IA resuelve mejor que los programas actuales, y no solo "más bonito"?
- ¿Quién paga, cuánto, y con qué recurrencia?
- ¿Es defendible? ¿Dónde están las barreras defensivas (datos, integración, distribución)?
- ¿Que segmento maximiza dolor × disposición a pagar × hueco competitivo × viabilidad técnica?

Salida del bloque: lista priorizada de hipótesis refutables (H1, H2…), cada una con criterio de validación.

---

## 2. Definición de producto y alcance

Aterrizar qué es exactamente "editor `.bc3` con IA" antes de medir nada.

- **Núcleo funcional**: programa que permite abrir, editar y exportar archivos con estructura FIEBDC-3.
	- Es imprescindible asegurar la correcta apertura de los archivos .bc3 provenientes de Presto con garantías. Esto es un punto clave, no puede haber errores en la apertura de archivos, los importes, mediciones y precios, etc deben coincidir de forma exacta.
	- El programa debe poder exportar con garantías todo lo realizado, permitiendo a otros programas como presto abrir el archivo garantizando su lejibilidad y asegurando que no hay errores en los cálculos e interpretaciones.
	- Gran foco en la facilidad de edición de los presupuestos. Es muy importante que sea fácil trabjar con el programa. Copiar, pegar, tabuladores, felchas, el trabajo con el progama se tiene que sentir muy fluido.
- **Capa de IA:** hipótesis de posibles funcionalidades
  - Generación de textos descriptivos de partidas.
  - Generación de descompuestos en base a los datos del proyecto y otras bases de datos.
  - Búsqueda de partidas similares en bases de precios.
  - Detección de errores, descuadres y partidas omitidas.
  - Elaboración de peticiones para solicitud de ofertas.
  - Extracción de mediciones desde planos PDF / IFC / BIM (QTO).
  - *Benchmarking* y estimación de costes a partir de histórico.
  - Comparativo automático de ofertas / licitaciones.
  - Consulta en lenguaje natural sobre el presupuesto mediante las herramientas de las que dispone el programa con la API.
- **Ejes de segmentación de uso**: *redacción* (presupuesto como entregable de proyecto); *gestión de obra* (presupuesto como instrumento vivo de control económico); licitación de obra (presupuesto para analizar costes)

---

## 3. Análisis de mercado (dimensionamiento)

Estimar TAM / SAM / SOM con doble método (top-down y bottom-up) y reconciliar.

- **Top-down**: nº de despachos de arquitectura/ingeniería y empresas constructoras × penetración software × precio. Fuentes: INE-DIRCE (CNAE 41, 42, 43, 71.1), colegios profesionales (arquitectos, arquitectos técnicos/aparejadores, ICCP, industriales), CNC/SEOPAN para el lado constructor.
- **Bottom-up**: base instalada estimada de programas instalados (licencias Presto, CYPE/Arquímedes, TCQ) × precio de sustitución.
- **Lado público**: volumen de licitación de obra pública (Plataforma de Contratación del Sector Público) como proxy de presupuestos redactados/año.
- **Construcción privada**: Inversión en construcción privada como proxy del importe gastado en software al año.
- **Salida**: rango TAM/SAM/SOM con supuestos explícitos y nivel de confianza. Marcar cada cifra como *dato verificado* / *estimación* / *supuesto*.

---

## 4. Análisis competitivo

Mapear el tablero completo, no solo competidores directos.

- **Programas existentes directos**: Presto (RIB/Schneider), Arquímedes (CYPE), TCQ (ITeC), Menfis, Gest, Builder y otros editores de mediciones y presupuestos.
- **Sustitutos**: Excel + plantillas (probablemente el competidor #1 real, sobre todo en gestión), Word para pliegos.
- **Nuevos progamas que se están desarrollando con IA integrada**: Budqo y similares
- **Adyacentes que pueden invadir**: suites BIM (Revit + complementos QTO), ERPs de construcción, herramientas de *takeoff*/QTO.
- **Por cada competidor**: funcionalidad, precio, modelo (licencia perpetua vs. SaaS), integración BIM/CAD, base de precios incluida, presencia de IA (real o *marketing*), base instalada, fortalezas/debilidades.
- **Lentes**: 5 fuerzas de Porter (poder de proveedores de bases de precios = clave), mapa de posicionamiento (eje IA/automatización × eje redacción↔gestión) para localizar huecos.
- **Salida**: tabla comparativa + identificación explícita de espacios no cubiertos.

---

## 5. Análisis de cliente y segmentación

Separar el análisis por los dos segmentos candidatos y compararlos cara a cara.

Para **redacción de proyectos, gestión de obra, preparación de licitaciones, pequeñas subcontratas**, por separado:
- **Buyer persona y usuario** (¿quién decide, quién usa, quién paga?).
- **Jobs To Be Done**: el trabajo real que contratan al software.
- **Mapa de dolor**: tareas tediosas, caras, propensas a error; cuantificar horas/€ por proyecto u obra.
- **Frecuencia de uso**: por proyecto (bursty) vs. continua (recurrente).
- **Disposición a pagar** y sensibilidad al precio; presupuesto de software ya existente.
- **Costes y fricción de cambio** respecto al programa existente.
- **Canales**: cómo descubren y compran software (colegios, prescripción, boca a boca, distribuidores).

Salida: ficha comparada de los dos segmentos que alimenta directamente la matriz del Bloque 11.

---

## 6. Propuesta de valor e hipótesis de IA (factibilidad y defensibilidad)

Someter cada funcionalidad IA del Bloque 2 a un doble filtro.

- **Valor para el cliente** (alto/medio/bajo): ¿resuelve un dolor caro y frecuente?
- **Factibilidad técnica** realista:
  - Generación de textos de partida → fácil (LLM).
  - *Matching* semántico a base de precios → tratable (embeddings + RAG sobre la base).
  - QTO desde PDF/IFC → difícil y parcialmente un problema distinto.
  - Detección de descuadres → media (reglas + IA).
- **Defensibilidad / *moat***: ¿es replicable por Presto/CYPE en un trimestre? El *moat* probablemente NO está en la IA (commodity) sino en: datos propietarios, integraciones, distribución, o flujo de trabajo capturado.
- **Punto crítico a investigar — propiedad de datos de precios**: BEDEC (ITeC), generadores de precios (CYPE), bases autonómicas son **IP licenciada**, no scrapeable. ¿Se puede licenciar, integrar, o hay que construir base propia? Esto es a la vez el mayor riesgo y el posible *moat*.

Salida: matriz valor × factibilidad de cada *feature*; identificación del *moat* y de su viabilidad legal/comercial.

---

## 7. Análisis técnico-regulatorio

- **Formato FIEBDC-3 / `.bc3`**: especificación, versiones, qué garantiza la interoperabilidad, qué no (¿es ventaja real o estándar abierto que cualquiera implementa?).
- **Bases de precios**: condiciones de licencia de BEDEC, generadores CYPE, PREOC, bases autonómicas; alternativas abiertas.
- **BIM / openBIM**: IFC, requisitos BIM en contratación pública (es.BIM / mandato BIM), 5D (coste); ¿integración como requisito o como diferenciador?
- **Normativa de contratación**: LCSP (presupuesto base de licitación, clasificación por capítulos, justificación de precios) — qué estructura debe respetar el output.
- **Protección de datos / confidencialidad**: presupuestos y costes son sensibles; implicaciones de procesar datos de cliente con IA (on-premise vs. nube, dónde corre el modelo).

Salida: lista de requisitos técnicos/legales *must-have* vs. *nice-to-have* y de bloqueantes potenciales.

---

## 8. DAFO (análisis explícito de debilidades y oportunidades)

Construir la matriz con evidencia de los bloques anteriores, no a ojo.

- **Fortalezas** (internas): p. ej. foco IA nativa, agilidad, conocimiento del dominio.
- **Debilidades** (internas): sin base instalada, sin base de precios propia, recursos limitados, dependencia de licencias de terceros.
- **Oportunidades** (externas): Excel como competidor débil en gestión, ola IA, hueco de UX moderna, mandato BIM.
- **Amenazas** (externas): incumbentes copian la IA, dependencia de proveedores de datos, costes de cambio del cliente, ciclos de venta largos.

Salida: DAFO + **estrategias cruzadas** (FO/FA/DO/DA), no solo el cuadrante.

---

## 9. Modelo de negocio y *go-to-market*

- **Modelo de ingresos**: SaaS por suscripción vs. licencia; por usuario, por proyecto, por obra; *freemium* para penetrar.
- **Pricing**: anclar al gasto actual del cliente y al valor (horas ahorradas); comparar con precios de incumbentes.
- **GTM y distribución**: prescripción vía colegios profesionales, alianzas (¿con un proveedor de base de precios?), comunidad, contenido técnico, *bottom-up* vs. ventas.
- **Unit economics** (preliminar): CAC esperado, LTV, recurrencia. La recurrencia favorece a gestión (uso continuo) frente a redacción (bursty).

Salida: 1–2 modelos de negocio coherentes con el segmento elegido.

---

## 10. Riesgos

Catalogar y puntuar (probabilidad × impacto) con mitigación:

- **Competitivo**: el incumbente añade IA antes de alcanzar masa crítica.
- **Datos/IP**: no poder licenciar bases de precios; coste de construir una propia.
- **Adopción**: inercia, costes de cambio, desconfianza hacia la IA en cifras económicas.
- **Técnico**: precisión del *matching*/QTO insuficiente para uso profesional (un error en un presupuesto es caro).
- **Regulatorio**: cambios en LCSP/BIM/normativa.
- **Comercial**: ciclo de venta largo, mercado fragmentado y pequeño.

---

## 11. Decisión estratégica: redacción vs. gestión (matriz de scoring)

Resolver el eje con criterios ponderados, no por intuición. Puntuar cada segmento (1–5) y multiplicar por peso (definir y justificar pesos antes de puntuar).

| Criterio | Peso | Redacción | Gestión |
|---|---|---|---|
| Tamaño de mercado (SAM) | | | |
| Intensidad del dolor (caro/frecuente) | | | |
| Disposición a pagar | | | |
| Recurrencia de ingresos | | | |
| Hueco competitivo (hueco blanco) | | | |
| Encaje natural del formato `.bc3` | | | |
| Factibilidad técnica de la IA | | | |
| Defensibilidad / *moat* | | | |
| Coste y fricción de cambio del cliente | | | |
| Duración del ciclo de venta | | | |
| **Total ponderado** | | | |

Evaluar también la **estrategia de cuña**: entrar por un segmento y expandir al otro reutilizando el dato del presupuesto. Documentar la secuencia y las condiciones que la harían viable.

Salida: recomendación de segmento (o cuña) con justificación trazable a la tabla.

---

## 12. MVP y roadmap de validación

- **Definición del MVP** según segmento elegido: la *feature* IA de mayor valor × factibilidad como punta de lanza.
- **Hitos de validación** (ligados a las hipótesis del Bloque 1): entrevistas con N usuarios reales de cada segmento, prueba de concepto del *matching* sobre una base real, *landing* de validación de demanda, primeros pilotos.
- **Métricas de éxito** por hito y criterios de pivote/parada.

---

## 13. Metodología, fuentes y verificación

Requisito transversal a todos los bloques:

- **Trazabilidad**: cada afirmación cuantitativa con fuente y fecha; etiquetar *dato verificado* / *estimación* / *supuesto*.
- **Fuentes primarias preferidas**: INE-DIRCE, colegios profesionales, CNC/SEOPAN, Plataforma de Contratación del Sector Público, documentación oficial FIEBDC-3, condiciones de licencia de ITeC/CYPE, webs y *pricing* oficiales de los competidores.
- **Validación cualitativa**: entrevistas a redactores de proyecto y a jefes de obra/control de costes (insustituible; el desk research no basta para WTP ni para el dolor real).
- **Control de alucinaciones**: no inventar cifras de mercado ni de base instalada; si no hay dato, indicar el método de estimación y el rango de incertidumbre.

---

## Entregable final del estudio

1. *Executive summary* con la recomendación Go/No-Go/Pivote y el segmento.
2. Matriz de decisión del Bloque 11 cumplimentada.
3. DAFO con estrategias cruzadas.
4. Definición de MVP y plan de validación a 90 días.
5. Anexo de fuentes con trazabilidad.
