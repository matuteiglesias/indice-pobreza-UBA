# Indice de Pobreza de la UBA

Análisis y cálculo de tasas de pobreza en Argentina. Herramienta esencial para investigadores, políticos y ONGs.

### Descripción

El repositorio "Indice de Pobreza - Exactas UBA" está dedicado al cálculo, análisis y presentación de los índices de pobreza en Argentina. Aprovechando los métodos estadísticos y la integración de varios conjuntos de datos, este proyecto proporciona una comprensión profunda de los niveles de pobreza en diferentes regiones y demografías del país.

**Características clave**:

- **Análisis integral de datos**: utiliza la base de datos completa del censo para lograr la una perspectiva precisa y detallada sobre la pobreza en Argentina.
- **Visualización dinámica**: ofrece representaciones visuales de métricas de pobreza, lo que permite una comprensión más intuitiva de datos complejos.
- **Colaboración de código abierto**: alienta las contribuciones y la colaboración de investigadores, estadísticos, legisladores y cualquier persona interesada en la reducción de la pobreza.
- **Enfoque impulsado por la investigación**: basado en las últimas investigaciones y metodologías académicas, lo que garantiza la credibilidad y la relevancia.

### Objetivo:

El objetivo principal de este proyecto es contribuir a la comprensión y mitigación de la pobreza en Argentina ofreciendo una visión clara de sus diversas dimensiones. Al hacerlo, su objetivo es informar la formulación de políticas eficaces, promover la conciencia social e inspirar la acción hacia el desarrollo equitativo y sostenible.

### Uso:

Ideal para académicos, investigadores, agencias gubernamentales, ONG y cualquier persona interesada en los aspectos multifacéticos de la pobreza en Argentina. Este repositorio sirve como un recurso valioso para la investigación, la toma de decisiones y la promoción.

Antes de usar encuestadores, necesita samplear Censo con https://github.com/matuteiglesias/samplerCensoARG
Ej:
`
(base) matias@matias-ThinkPad-T470-W10DG:~/repos/samplerCensoARG/notebooks$ python samplear.py -dbp '/suite/ext_CPV2010_basico_radio_pub' -f 0.05 -y 2023 2024
/media/matias/Elements/suite/ext_CPV2010_basico_radio_pub
0.05
ARG
`[########################################] | 100% Completed | 100.56 ms

Luego, correr: `01 - Sampleos de Censo.ipynb` (Run All) para tener los muestreos de poblaciones adaptados para el notebook 02.

El script de la notebook 03 genera datasets pobreza hogares, y datasets personas. 


### **Datasets de Pobreza**

Este conjunto de datos se divide en dos tablas principales: `pobreza_hogares` y `pobreza_personas`.


#### **Tabla: pobreza_hogares**



* **Clave Primaria:** `HOGAR_REF_ID`


##### **Variables:**



* `HOGAR_REF_ID`: Identificador único para cada hogar.
* `Q`: Trimestre. Actualmente tiene un único valor.
* `P47T_hogar`: Ingresos del hogar.
* `CBA`: ...
* `CBT`: ...
* `CB_EQUIV`: ...
* `Pobreza`: Indicador booleano que denota si el hogar está en situación de pobreza.
* `Indigencia`: Indicador booleano que denota si el hogar está en situación de indigencia.
* `gap_pobreza`: ...
* `gap_indigencia`: ...


#### **Tabla: pobreza_personas**



* **Clave Primaria:** `ID`
* **Clave Externa:** `HOGAR_REF_ID`, que hace referencia a `HOGAR_REF_ID` en la tabla `pobreza_hogares`.


##### **Variables:**



* `ID`: Identificador único para cada persona.
* `RADIO_REF_ID`: Identificador de referencia de radio.
* `DPTO`: Departamento.
* `PROV`: Provincia.
* `AGLOMERADO`: Aglomerado.
* `HOGAR_REF_ID`: Identificador del hogar al que pertenece la persona. Se relaciona con la tabla `pobreza_hogares`.
* `P02`: ...
* `P03`: ...
* `P09`: ...
* `P10`: ...
* `P47T_persona`: Ingresos de la persona.
* `ANO4`: Año. Actualmente tiene un único valor.
* `Q`: Trimestre.
* `P0910`: ...
* `COD_2010`: Código 2010.
* `IDFRAC`: ...
* `NOMPROV`: Nombre de la provincia.
* `Region`: Región.
* `IN1`: ...
* `circuito`: ...

### Idioma y Herramientas:

Desarrollado con python, se usan los modelos de Random Forest del encuestador de hogares.

### Contribuir:

Aportes, sugerencias y colaboraciones son bienvenidas! Siéntase libre de clonar el repositorio, enviar pull request o abrir issue para evaluar mejoras.
