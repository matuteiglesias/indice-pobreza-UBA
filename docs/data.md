

### **Guía de Documentación de Datos del Proyecto de Análisis de Pobreza**

Para cualquier pregunta, aclaración o comentario sobre los conjuntos de datos o las metodologías empleadas, por favor, comuníquese con:

- **Nombre**: Matias Iglesias
- **Correo Electrónico**: matuteiglesias@gmail.com
  
## 1. **Descripción General del Proyecto**

El análisis y la investigación sobre la pobreza son esenciales para comprender las dinámicas socioeconómicas de una región o país y para formular políticas públicas eficaces. Este proyecto aborda el desafío de analizar la pobreza a través de técnicas avanzadas de procesamiento de datos y modelado estadístico.

- **Objetivo**: El principal objetivo del proyecto es utilizar la información disponible, especialmente los datos del censo de 2010, para predecir ingresos y, por ende, obtener métricas relevantes sobre la pobreza en diferentes regiones y subgrupos poblacionales.

- **Aplicaciones**:
  - **Formulación de Políticas**: Las métricas y hallazgos derivados de este proyecto pueden guiar a los formuladores de políticas en la toma de decisiones informadas.
  - **Investigación Académica**: Este proyecto puede ser una base para investigaciones académicas más profundas en el campo socioeconómico.
  - **Conciencia Pública**: Los resultados pueden usarse para informar y educar al público sobre la situación actual de la pobreza en diferentes regiones.

## 2. **Aspectos Destacados del Procesamiento de Datos**

- **Ajuste Temporal**: Una característica distintiva del tratamiento de datos en este proyecto es el ajuste temporal. Mediante el uso de técnicas avanzadas, los datos históricos y actuales se ajustan para ser coherentes con el año y trimestre relevantes, garantizando así un análisis preciso y contextual. Los precios se actualizan periódicamente para reflejar condiciones económicas actuales.

- **Ingeniería de Características**: A través de técnicas de ingeniería de características, se han derivado nuevas variables y métricas a partir de los conjuntos de datos originales, especialmente de los ingresos. Estas características derivadas enriquecen el conjunto de datos y proporcionan perspectivas adicionales para el análisis de pobreza.

- **Agregación**: En el 'results_path', se encuentran estadísticas calculadas a partir de agrupaciones basadas en múltiples columnas, como `Q`, `AGLOMERADO`, y `Región`. Estas agrupaciones permiten analizar subconjuntos específicos de la población y obtener insights relevantes.

- **Integración Geoespacial**: Una fortaleza clave del proyecto es la fusión de datos de hogares con datos geográficos. Esta integración permite realizar análisis geoespaciales detallados y obtener insights regionales específicos sobre la pobreza.

- **Base de Datos de Censo 2010**: El censo de 2010 proporciona una base sólida y confiable. Su integración en el proyecto garantiza que las predicciones y análisis estén arraigados en datos empíricos robustos.

- **Modelos de Conjunto en Etapa**: A través de técnicas avanzadas de modelado, se aplican modelos de conjunto en etapas para predecir los ingresos de individuos y hogares. Posteriormente, estas predicciones se utilizan para calcular las diferencias con los gastos a nivel del hogar, proporcionando una imagen clara de la situación económica de las unidades familiares.

- **Riqueza del Censo**: Con la integración del censo, el proyecto ahora tiene acceso a una amplia variedad de datos y métricas. Estos datos enriquecen el análisis y permiten filtrar o desglosar la condición de pobreza en múltiples dimensiones, desde geográficas hasta demográficas.

---


## 3. Conjuntos de datos


### 3.1 Fuentes de Datos

#### **Datos del Censo - Censo 2010**

- **Nombre**: Datos del Censo 2010
- **Fuente**: `'./'`
- **Variables clave**:
   - `VIVIENDA_REF_ID`: Identificador de referencia de la vivienda.
   - `RADIO_REF_ID`: Identificador de referencia del radio censal.
   - `TIPVV`: Tipo de vivienda.
   - `V01`: Tipo de vivienda según observación directa.
   - `URP`: Zona geográfica (urbana/rural).
   - `DPTO`: Nombre o código del departamento.
   - `PROV`: Nombre o código de la provincia.
   - `AGLOMERADO`: Código del aglomerado urbano.
   - `HOGAR_REF_ID`: Identificador de referencia del hogar.
   - `H05` a `H16`: Variables que describen características específicas de las viviendas y hogares, tales como materiales de construcción, servicios básicos, número de habitaciones, entre otros.
   - `PROP`: Régimen de tenencia de la vivienda.
   - `TOTPERS`: Número total de personas en el hogar.
   - `PERSONA_REF_ID`: Identificador de referencia de la persona.
   - `P01` a `P10` y `CONDACT`: Variables que describen características demográficas y socioeconómicas de las personas, tales como sexo, edad, lugar de nacimiento, nivel educativo, entre otros.

#### **Aglo RK**
- **Nombre**: Aglo RK
- **Fuente**: `''`
- **Variables clave**:
   - `ANO4`: Año.
   - `Región`: nombre de la región.
   - `Aglo_rk`: [Ranking del aglomerado por ingreso medio en EPH.]
   

#### **Reg RK**
- **Nombre**: Reg RK
- **Fuente**: `''`
- **Variables clave**:
   - `ANO4`: Año.
   - `Región`: nombre de la región.
   - `Reg_rk`: [Ranking de la region por ingreso medio en EPH.]

#### **Región DPTO**
- **Nombre**: Departamento y Región
- **Derivado de**: conjunto de datos de referencia de radio
- **Variables clave**:
   - `DPTO`: Departamento.
   - `Región`: nombre de la región.

#### **Empleo**
- **Nombre**: Empleo
- **Fuente**: `'https://raw.githubusercontent.com/matuteiglesias/empleoARG/main/datos/45.2_ECTDT.csv'`
- **Variables clave**:
   - `45.2_ECTDT_0_T_33`: [Descripción necesaria]
   - `censo2010_ratio`: Ratio respecto a los datos de empleo del censo de 2010.


#### **Adulto Equivalente y Canasta Básica - Regional Deflactada**
- **Nombre**: Adulto Equivalente y Canasta Básica Regional Deflactada
- **Fuente**: `'./../data/info/adulto_eq.csv'` y `'https://raw.githubusercontent.com/matuteiglesias/canastasINDEC/main/data/CB_Reg_defl_Q.csv'`
- **Variables clave**:
   - `Q`: Fecha, que probablemente represente el trimestre.
   - `Región`: nombre de la región.
   - `CBA`: Costo de la Canasta Básica Alimentaria.
   - `CBT`: Costo de la Canasta Básica Total.

#### **Información Geográfica - Radio Ref**
- **Nombre**: Información Geográfica - Referencia de Radio
- **Fuente**: `'./../data/info/radio_ref.csv'`
- **Variables clave**:
   - `RADIO_REF_ID`: ID de referencia de la radio.
   - `DPTO`: Departamento.
   - `FRAC_REF_ID`: ID de referencia de la fracción.
   - `NOMDPTO`: Nombre del departamento.
   - `COD_2010`: Código del año 2010.
   - `Región`: nombre de la región.

#### **Claves Dptos Ref**
- **Nombre**: Claves de Departamentos de Referencia
- **Fuente**: `'https://raw.githubusercontent.com/matuteiglesias/elecciones-ARG/main/datos/BD/claves_dptos_ref.csv'`
- **Variables clave**:
   - `distrito_id`: ID del distrito.
   - `seccion_id`: ID de sección.
   - `IN1`: [Descripción necesaria]
   - `NAM`: [Descripción necesaria, posiblemente nombre del distrito o sección.]

#### **Radios Circuitos Secciones Ref**
- **Nombre**: Referencia de Radios, Circuitos y Secciones
- **Fuente**: `'./../../CNE-INDEC-georef/info/radios_circuitos_secciones_ref.csv'`
- **Variables clave**:
   - `COD_2010`: Código del año 2010.
   - `distrito_id`: ID del distrito.
   - `seccion_id`: ID de sección.
   - `seccion_nombre`: Nombre de la sección.
   - `circuito`: [Descripción necesaria, posiblemente nombre del circuito o ID.]


#### **Índice de Precios al Consumidor (IPC)**
- **Nombre**: Índice de Precios al Consumidor (IPC)
- **Fuente**: [Repositorio GitHub de Matías Iglesias - IPC Argentina](https://raw.githubusercontent.com/matuteiglesias/IPC-Argentina/main/data/info/indice_precios_M.csv)
- **Variables clave**:
   - **Fecha del índice (fechahora)**: La fecha para la cual se registra el índice de precios.
   - **Valor del índice (flotante)**: El valor del índice de precios al consumidor para la fecha determinada.
   - **Fecha actual (cadena)**: la fecha actual en la que se ejecuta el script.
   - **Relación del índice de precios (flotante)**: La relación del índice de precios actual con respecto al índice de precios del año base (2016-01).
   - **Año base para el índice (cadena)**: el año base para el índice de precios es 2016-01, con un valor de índice de 1.

#### **Geometrías Geoespaciales - Provincias, Departamentos y Fracciones**
- **Nombre**: Geometrías geoespaciales
- **Fuente**:
   - Provincias: `'./../../geoespacial-censo-IGN/IGN_shp/ign_provincia'`
   - Departamentos: `'./../../geoespacial-censo-IGN/censos_shp_CONICET_dissolved/dptos_2010.shp'`
   - Fracciones: `'./../../geoespacial-censo-IGN/censos_shp_CONICET_dissolved/fracs_2010.shp'`
- **Variables clave**:
   - **PROV (int64)**: Código de provincia.
   - **DPTO (int64)**: Código de departamento.
   - **IDFRAC (objeto)**: ID de fracción, construido a partir de códigos de provincia, departamento y fracción.
   - **geometría (geometría)**: Forma geométrica de la división administrativa.
   - **area_km2 (float64)**: Área de la división administrativa en kilómetros cuadrados.
   - Otros atributos como `'OBJECTID', 'Entidad', 'Objeto', 'FNA', 'GNA', 'NAM', 'SAG', 'FDC', 'IN1', 'SHAPE_STAr', 'SHAPE_STLe'` son disponibles en el conjunto de datos de la provincia, pero es posible que no sean relevantes para este análisis.

**Detalles adicionales**:
Estos conjuntos de datos proporcionan límites geoespaciales para diferentes divisiones administrativas de Argentina. Los datos de provincias, departamentos y fracciones provienen de diferentes conjuntos de datos. Estas geometrías se utilizan para unirse espacialmente con los datos de pobreza y generar GeoJSON que visualizan las métricas de pobreza en estas divisiones.


### 3.2 Bases de Datos Derivadas

#### **Pobreza en Argentina - Datos GeoJSON por Niveles Geográficos**

Los datos geoespaciales que poseemos están distribuidos en varios archivos GeoJSON, cada uno representando diferentes niveles geográficos y métodos de cálculo de pobreza. A continuación, presentamos un resumen de estos archivos y su contenido:

##### 1. Niveles Geográficos:
- **DPTO (Departamentos)**
- **IDFRAC (Fracciones)**
- **PROV (Provincias)**

##### 2. Métodos de Cálculo:
- **H:** [Detallar método]
- **M14:** [Detallar método]
- **M24:** [Detallar método]
- **P:** [Detallar método]

##### 3. Métricas Disponibles en los Archivos:

- **Totales**
- **Pobreza**: Representa la cantidad o proporción de personas/hogares que se encuentran bajo la línea de pobreza.
- **Indigencia**: Representa la cantidad o proporción de personas/hogares que se encuentran bajo la línea de indigencia.
- **Ingresos (P47T)**: Contiene información sobre los ingresos a nivel de persona y hogar. Disponemos de diferentes percentiles para analizar la distribución de ingresos.
- **Canasta Básica**: Se incluyen métricas relacionadas con la Canasta Básica Total (CBT), Canasta Básica Alimentaria (CBA) y Canasta Básica Equivalente (CB_EQUIV).
- **Brecha de Pobreza e Indigencia**: Representa la diferencia entre los ingresos de los hogares y el valor de la canasta básica.
- **Área**: Se proporciona el área en km^2 de cada unidad geográfica.

 

#### **Población Sintética por Año**
La serie de archivos "Población Sintética por Año" representa datasets generados de poblaciones sintéticas basados en diversas configuraciones y parámetros. Estos archivos son producidos por el notebook "1. Generador de Población Sintética.ipynb".

##### Detalles del Nombre del Archivo:

Los nombres de archivo siguen un formato específico que refleja los parámetros utilizados en la generación:

- `table_f[FRAC]_[YEAR]_[COUNTRY].csv`
  
Donde:
- `[FRAC]` es el fraccionamiento utilizado.
- `[YEAR]` es el año de referencia para la población.
- `[COUNTRY]` es el código de país (por ejemplo, "ARG" para Argentina).

Por ejemplo, `table_f0.005_2015_ARG.csv` se refiere a un archivo de población sintética basado en el año 2015, para Argentina, y con un fraccionamiento de 0.005.

##### Variables Clave:

A continuación, se detallan las principales columnas que representan los atributos de la población sintética:

- **ID**: Identificador único.
- **VIVIENDA_REF_ID**: Identificador de referencia de vivienda.
- **RADIO_REF_ID**: Identificador de referencia del radio censal.
- **TIPVV**: Tipo de vivienda.
- **V01**: Tipo de vivienda (observación directa).
- **URP**: Zona geográfica (urbana/rural).
- **DPTO**: Identificador del departamento.
- **PROV**: Identificador de la provincia.
- **AGLOMERADO**: Identificador del aglomerado urbano.
- **HOGAR_REF_ID**: Identificador de referencia del hogar.
- **H05-H16**: Variables relacionadas con las características de la vivienda y el hogar. Incluyen detalles sobre la construcción, los servicios y las instalaciones del hogar.
- **PROP**: Régimen de tenencia de la vivienda.
- **IX_TOT**: Índice compuesto (detalle específico pendiente).
- **PERSONA_REF_ID**: Identificador de referencia de persona.
- **P01-P12**: Variables relacionadas con las características demográficas y socioeconómicas de las personas.
- **CONDACT**: Condición de actividad laboral.
- **ANO4**: Año de referencia (detalle específico pendiente).
- **Region**: Región geográfica.
- **AGLO_rk**: Ranking o categoría basado en el aglomerado (detalle específico pendiente).
- **Reg_rk**: Ranking o categoría basado en la región (detalle específico pendiente).


#### **Ingresos Ajustados por Trimestre y Año**
Los datos de ingresos ajustados por trimestre y año reflejan el procesamiento y ajuste de ingresos a lo largo del tiempo. Estos datos son generados por el notebook "2. Preprocesamiento de Ingresos.ipynb".

Los resultados intermedios de los modelos reflejan las etapas intermedias en el proceso de modelado. Hay resultados para varias etapas, desde la etapa 1 hasta la etapa 4.

##### Detalles del Nombre del Archivo:

Los nombres de los archivos siguen un formato específico:

- `RFC[STAGE]_[FRAC]_[DATE]_[COUNTRY].csv`
  
Donde:
- `[STAGE]` es la etapa del modelo (por ejemplo, 1, 2, 3, 4).
- `[FRAC]` es el fraccionamiento utilizado.
- `[DATE]` es la fecha de referencia para los resultados.
- `[COUNTRY]` es el código del país (por ejemplo, "ARG").

Por ejemplo, `RFC1_0.01_2018-05-15_ARG.csv` se refiere a un archivo de resultados de la etapa 1 con fecha de referencia 15 de mayo de 2018, para Argentina, y con un fraccionamiento de 0.01.

##### Variables Clave por Etapa:

1. **Etapa 1**:
   - **ID**: Identificador único.
   - **CAT_OCUP**: Categoría de ocupación.
   - **CAT_INAC**: Categoría de inactividad.
   - **CH07**: Estado civil actual. Las opciones incluyen unido, casado, separado/divorciado, viudo, y soltero.

2. **Etapa 2**:
   - **ID**: Identificador único.
   - **INGRESO**: Ingreso total.
   - **INGRESO_NLB**: Ingreso no laboral.
   - **INGRESO_JUB**: Ingresos provenientes de jubilación o pensión.
   - **INGRESO_SBS**: Ingresos provenientes de subsidios o ayudas sociales.

3. **Etapa 3**:
   - **ID**: Identificador único.
   - **PP07G1**: Indicador de si en el trabajo actual se otorgan vacaciones pagas.
   - **PP07G_59**: Indicador de si no se tiene ninguno de los beneficios laborales listados (ej. vacaciones pagas, aguinaldo, etc.).
   - **PP07I**: Indicador de si se aporta por sí mismo a algún sistema jubilatorio.
   - **PP07J**: Turno habitual de trabajo, que puede ser de día, de noche, u otro tipo.
   - **PP07K**: Forma en la que se recibe el pago por el trabajo.

4. **Etapa 4**:
   - **ID**: Identificador único.
   - **P21**: Monto de ingreso de la ocupación principal.
   - **p47T**: Monto del ingreso total individual, que es la sumatoria de ingresos.
   - **PP08D1**: Monto total de sueldos/jornales, salario familiar, horas extras, otras bonificaciones habituales y tickets, vales o similares.
   - **TOT_P12**: (Detalle pendiente)
   - **T_Vi**: Monto total de ingresos no laborales.
   - **V12_M**: Monto del ingreso por cuotas de alimentos o ayuda en dinero de personas que no viven en el hogar.
   - **V2_M**: Indicador de si las personas del hogar han vivido de alguna jubilación o pensión en los últimos tres meses.
   - **V3_M**: Indicador de si las personas del hogar han vivido de indemnización por despido en los últimos tres meses.
   - **V5_M**: Indicador de si las personas del hogar han vivido de un subsidio o ayuda social (en dinero) del gobierno, iglesias, etc. en los últimos tres meses.


Estas variables proporcionan una descripción detallada de los atributos más relevantes utilizados en cada etapa del análisis. Las descripciones son derivadas directamente de la información proporcionada anteriormente. Las variables para las cuales no se proporcionó una descripción directa tienen un "Detalle pendiente" para que puedan ser completadas más adelante.


#### Base de Datos: Pobreza para Hogares por Año y Trimestre
Las métricas de pobreza para hogares reflejan la situación de pobreza de los hogares durante diferentes años y trimestres. Estos datos son calculados y generados por el notebook "3. Cálculo de Pobreza.ipynb".

##### Detalles del Nombre del Archivo:

Los nombres de los archivos siguen un formato específico:

1. **Personas Ingresos**: 
   - Formato: `individual_income_sample[FRAC]_[Q]_[EXPERIMENT_TAG].csv`
   - Ejemplo: `individual_income_sample0.01_2022-01_ARG.csv`
   
2. **Pobreza Hogares**:
   - Formato: `household_poverty_sample[FRAC]_q[Q].csv`
   - Ejemplo: `household_poverty_sample0.01_q2022-01.csv`
   
3. **Hogares Geo**:
   - Formato: `geo_households_sample[FRAC]_[YEAR]_[EXPERIMENT_TAG].csv`
   - Ejemplo: `geo_households_sample00.01_2022_ARG.csv`

Donde:
- `[FRAC]` es el fraccionamiento utilizado.
- `[Q]` representa el trimestre y año (por ejemplo, "2022-01").
- `[EXPERIMENT_TAG]` es una etiqueta que representa detalles adicionales del experimento, como el país (por ejemplo, "ARG").

##### Variables Clave:

1. **Personas Ingresos**:
   - **ID**: Identificador único.
   - **HOGAR_REF_ID**: Identificador del hogar de referencia.
   - **Q**: Trimestre y año.
   - **P47T_persona**: (Detalle pendiente)
   - **P02**: (Detalle pendiente)
   - **P03**: (Detalle pendiente)
   - **P0910**: (Detalle pendiente)

2. **Pobreza Hogares**:
   - **HOGAR_REF_ID**: Identificador del hogar de referencia.
   - **Q**: Trimestre y año.
   - **P47T_hogar**: Total de ingresos del hogar.
   - **CBA**: Canasta Básica Alimentaria.
   - **CBT**: Canasta Básica Total.
   - **CB_EQUIV**: Equivalencia de la Canasta Básica.
   - **Pobreza**: Indicador booleano de pobreza (True si es pobre, False en caso contrario).
   - **Indigencia**: Indicador booleano de indigencia (True si es indigente, False en caso contrario).
   - **gap_pobreza**: Brecha de pobreza.
   - **gap_indigencia**: Brecha de indigencia.

3. **Hogares Geo**:
   - **RADIO_REF_ID**: Identificador de radio de referencia.
   - **AGLOMERADO**: Código de aglomerado.
   - **HOGAR_REF_ID**: Identificador del hogar de referencia.
   - **FRAC_REF_ID**: Identificador de fracción de referencia.
   - **DPTO**: Código de departamento.
   - **NOMDPTO**: Nombre del departamento.
   - **PROV**: Código de provincia.
   - **NOMPROV**: Nombre de la provincia.
   - **Region**: Región geográfica.
   - **COD_2010**: Código 2010.
   - **distrito_id**: ID de distrito.
   - **seccion_id**: ID de sección.
   - **seccion_nombre**: Nombre de sección.
   - **circuito**: Circuito.
   - **IN1**: (Detalle pendiente)
   - **NAM**: (Detalle pendiente)

**Merges**:

- **info_personas**: Resulta de combinar `personas_ingresos_Q`, `pobreza_hogares` y `hogares_geo` en la columna `HOGAR_REF_ID` y `Q`.

- **info_hogares**: Resulta de combinar `pobreza_hogares` y `hogares_geo` en la columna `HOGAR_REF_ID`.
- 


#### **Datasets Procesados - Estadísticas Descriptivas en 'results_path'**


Estos conjuntos de datos procesados, almacenados en la ruta 'results_path', representan las estadísticas descriptivas generadas para diferentes subgrupos de la población y se calculan en el notebook "4. Estadísticas Descriptivas.ipynb".

##### Detalles del Nombre del Archivo:

Los nombres de los archivos siguen un formato específico:

- Formato: `result_[base_str]_Q-[grouper]_[FRAC].csv`
- Ejemplo: `result_H_Q-Total_pais_0.005.csv`

Donde:
- `[base_str]` es una cadena que representa el subgrupo de datos (por ejemplo, "P" para personas, "H" para hogares, "M24" para personas mayores de 24 años, etc.).
- `Q` representa el trimestre y año.
- `[grouper]` es una lista de columnas que se utilizan para agrupar los datos.
- `[FRAC]` es el fraccionamiento utilizado.

##### Variables Clave:

1. **observable**: Tipo de métrica o variable observada (por ejemplo, "CBA", "CBT", "Indigencia", etc.).
2. **sintetico**: Tipo de métrica sintética (por ejemplo, "mean", "median", "sum", etc.).
3. **base**: Indica el subconjunto de datos base (por ejemplo, "H" para hogares).
4. **Q**: Trimestre y año.
5. **timestamp**: Fecha y hora de generación del dato.
6. **[grouper column]**: Valor de la columna de agrupación.
7. **valor**: Valor numérico de la métrica.
8. **frac**: Fraccionamiento utilizado.

Además de las variables anteriores, las columnas cambian en función de los "groupers". Estos "groupers" son listas de columnas que se utilizan para agrupar los datos antes de calcular las estadísticas descriptivas. 

**Ejemplo de groupers**:

- `groupersP = [['Q','Total'], ['Q','AGLOSI'], ['Q','AGLOMERADO'], ...]`
- `groupersH = [['Q','Total'], ['Q','AGLOSI'], ['Q','AGLOMERADO'], ...]`

Dependiendo de los "groupers" seleccionados, se generarán diferentes archivos CSV con nombres y columnas específicos.

**Nota**: La estructura y el contenido exacto de cada archivo dependerán del "grouper" seleccionado y del subconjunto de datos base (`[base_str]`). Las variables clave mencionadas anteriormente son comunes en todos los archivos, pero el número y el nombre de las columnas adicionales variarán en función de los "groupers".


## 4. Herramientas y Código

- **Herramientas/Librerías Utilizadas**:
  - **Pandas**: Para la manipulación y análisis de datos.
  - **NumPy**: Para operaciones numéricas.
  - **Datetime**: Para manejar datos de fecha y hora.
  
- **Scripts/Notebooks Principales**:
  - [1. Recolección y Limpieza de Datos.ipynb](#)
  - [2. Preprocesamiento de Ingresos.ipynb](#)
  - [3. Cálculo de Pobreza.ipynb](#)
  - [4. Estadísticas Descriptivas.ipynb](#)
  
  *(Nota: Los enlaces son marcadores de posición y deben ser reemplazados con las rutas reales a los cuadernos.)*

## 5. Contacto

Para cualquier pregunta, aclaración o comentario sobre los conjuntos de datos o las metodologías empleadas, por favor, comuníquese con:

- **Nombre**: Matias Iglesias
- **Correo Electrónico**: matuteiglesias@gmail.com

## 6. Licencia

Los conjuntos de datos y los materiales asociados se proporcionan bajo los términos que requieren simplemente el reconocimiento del autor original al ser utilizados. Por favor, asegúrese de citar o reconocer adecuadamente al autor o la fuente cuando utilice o se refiera a estos datos.

