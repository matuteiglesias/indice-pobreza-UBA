
# Indice de Pobreza de la UBA

Análisis y cálculo de tasas de pobreza en Argentina. Herramienta esencial para investigadores, políticos y ONGs.

### Descripción

El repositorio "Indice de Pobreza - Exactas UBA" está dedicado al cálculo, análisis y presentación de los índices de pobreza en Argentina. Aprovechando los métodos estadísticos y la integración de varios conjuntos de datos, este proyecto proporciona una comprensión profunda de los niveles de pobreza en diferentes regiones y demografías del país.

### Uso:

Académicos, investigadores, agencias gubernamentales, ONG y cualquier persona interesada en los aspectos multifacéticos de la pobreza en Argentina. Este repositorio sirve como un recurso valioso para la investigación y la toma de decisiones.

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

Este conjunto de datos se divide en tres tablas principales: personas_ingresos_Q_df, hogares_geo, y pobreza_hogares.

#### **Tabla: personas_ingresos_Q_df**

    Clave Primaria: ID

Variables:

    ID: Identificador único para cada persona.
    RADIO_REF_ID: Identificador de referencia de radio.
    DPTO: Departamento.
    AGLOMERADO: Aglomerado.
    HOGAR_REF_ID: Identificador del hogar al que pertenece la persona.
    P02: ...
    P03: ...
    P09: ...
    P10: ...
    ANO4: Año. Actualmente tiene un único valor.
    P0910: ...
    P47T_persona: Ingresos de la persona.
    Q: Trimestre.

#### **Tabla: hogares_geo**

    Clave Primaria: HOGAR_REF_ID
    Clave Externa: HOGAR_REF_ID, que hace referencia a HOGAR_REF_ID en la tabla pobreza_hogares.

Variables:

    RADIO_REF_ID: Identificador de referencia de radio.
    AGLOMERADO: Aglomerado.
    HOGAR_REF_ID: Identificador del hogar al que pertenece la persona. Se relaciona con la tabla pobreza_hogares.
    ANO4: Año. Actualmente tiene un único valor.
    COD_2010: Código 2010.
    IDFRAC: ...
    DPTO: Departamento.
    NOMDPTO: Nombre del departamento.
    PROV: Provincia.
    NOMPROV: Nombre de la provincia.
    Region: Región.
    IN1: ...
    circuito: ...

#### **Tabla: pobreza_hogares**


    Clave Primaria: HOGAR_REF_ID

Variables:

    HOGAR_REF_ID: Identificador único para cada hogar.
    Q: Trimestre. Actualmente tiene un único valor.
    P47T_hogar: Ingresos del hogar.
    CBA: ...
    CBT: ...
    CB_EQUIV: ...
    Pobreza: Indicador booleano que denota si el hogar está en situación de pobreza.
    Indigencia: Indicador booleano que denota si el hogar está en situación de indigencia.
    gap_pobreza: ...
    gap_indigencia: ...

### Idioma y Herramientas:

Desarrollado con python, se usan los modelos de Random Forest del encuestador de hogares.

---

### Contribuir:

Aportes, sugerencias y colaboraciones son bienvenidas! Siéntase libre de clonar el repositorio, enviar pull request o abrir issue para evaluar mejoras.

