# Indice de pobreza UBA
**Análisis Socioeconómico de Argentina**

Este proyecto da herramientas potentes para analisis detallado de las metricas socioeconómicas de Argentina, utilizando diversos conjuntos de datos y metodologías avanzadas para obtener insights valiosos sobre la pobreza, empleo, y otros indicadores clave.

## Contenido

1. [Descripción General](#descripción-general)
2. [Metodología](#metodología)
3. [Conjuntos de Datos](docs/data.md)
4. [Resultados](#resultados)
5. [Mantenimiento](docs/maintenance.md)
6. [Sumate al Equipo](#sumate-al-equipo)
7. [Licencia](#licencia)

## Descripción General

Este proyecto tiene como objetivo principal analizar la situación socioeconómica de Argentina. Se centra en áreas clave como pobreza, empleo, distribución de ingresos, entre otros. Las metodologías y técnicas de análisis utilizadas permiten una comprensión profunda de las tendencias y desafíos socioeconómicos en el país.

## Metodología

El análisis se basa en una combinación de técnicas estadísticas, análisis geoespacial, y modelado predictivo. 
<!--Para obtener detalles específicos sobre la metodología utilizada, refiérase al documento detallado [aquí](link-a-documento-metodología).-->

![Diagrama de Flujo del Proyecto](https://github.com/matuteiglesias/indice-pobreza-UBA/blob/main/images/graphviz.svg?raw=true)

### Ejecución canónica de pobreza

Después de la aprobación científica de los insumos y políticas, existe **una sola
interfaz canónica**. Recibe la ruta de un lock `poverty-slice-lock/v1`; no recibe
rutas adicionales ni descarga datos:

```bash
PYTHONPATH=src python -m poverty_pipeline run-lock <poverty-slice-lock/v1-path>
```

El comando valida primero todos los pins y escribe una versión inmutable en
`<lock.outputs.release_root>/<lock.slice_id>/<lock.outputs.release_version>/`.
Una ejecución científica usa `mode: poverty_release` y
`scientific_execution_authorized: true`. El modo existente `contracts_only` se
mantiene sin cambios: exige insumos metodológicos no resueltos, prohíbe el kernel
y nunca produce una estimación.

#### Insumos directos y linaje upstream

El lock de ejecución fija por `release_id`, ruta local y SHA-256 del manifiesto
exactamente cuatro tipos de artefacto directos:

| Rol | Tipo obligatorio | Uso en esta ejecución |
|---|---|---|
| muestra | `research.census-sample/v1` | personas, hogares, pesos aprobados y departamento CPV-2010 |
| ingresos | `research.person-income-predictions/v1` | predicción por persona en el mismo namespace y período |
| equivalencia | `research.poverty-adult-equivalence/v1` | coeficiente aprobado por dominio de sexo y edad |
| canastas | `research.regional-baskets/v1` | CBA/CBT por región, período y referencia monetaria |

La EPH anual (`research.eph-annual-input/v1`) y la ejecución del modelo
(`research.eph-model-execution/v1`) son **linaje upstream** de la release de
predicciones. El lock registra sus identidades y hashes para trazabilidad, pero
el runner de pobreza no los abre, no entrena ni ejecuta modelos y no acepta EPH
como insumo directo. La referencia monetaria de ingresos y canastas debe
coincidir exactamente.

Cada lock de ejecución también debe incluir las releases aprobadas y versionadas
de equivalencia adulta y canastas, y registrar identificadores de aprobación para
las políticas de: comparación de umbrales (estricta o inclusiva, explícita para
pobreza e indigencia), signo del gap y pesos/estimandos permitidos. Los joins son
estrictos y la salida de ingreso del kernel es ARS lineal; una falta de cobertura,
un namespace diferente o una referencia monetaria distinta detiene la ejecución.

#### Universos soportados

El universo geográfico soportado es exclusivamente `department_2010` / CPV-2010.
La tabla nacional es la reconciliación de esos departamentos; un GeoJSON de
departamentos 2010 es opcional. Aglomerados EPH, radios, fracciones, provincias,
geografía electoral y publicación web quedan fuera de esta interfaz.

Los universos estadísticos soportados son (1) hogares de la muestra Census
clasificados y (2) personas que viven en esos hogares. Sólo se calculan los
estimandos enumerados y aprobados en `weight.permitted_estimands`. Quedan fuera
M14/M24, empleo, subgrupos, nowcasts, población presente y cualquier estadística
oficial.

#### Configuración y roles del bundle

`outputs` es obligatorio: fija `release_root`, una `release_version` explícita,
formato tabular CSV (Parquet puede ser un derivado opcional), opción espacial (`none` o
`department_2010_geojson`) y los roles del bundle. Los roles mínimos son:

* `person_classification` y `aggregates_tidy`: personas clasificadas y agregados normalizados;
* `household_classification`: una fila por hogar y período, con umbrales,
  clasificación y gaps;
* `department_summary` y `national_summary`: agregados ponderados y reconciliables;
* `release_manifest`: identidades/hashes de inputs, políticas, software y archivos;
* `run_qa`: cobertura, cardinalidad, dominios, invariantes y reconciliaciones;
* `limitations`: alcance científico y exclusiones legibles por humanos;
* `checksums`: digests del bundle para verificación posterior;
* `department_spatial`: opcional y sólo cuando se solicita GeoJSON departamental.

La agregación productiva vive en `poverty_pipeline.aggregation`: recibe solamente
tablas ya clasificadas y pesos muestrales aprobados, y emite el contrato tidy
reconciliado. `poverty_pipeline.packaging` crea el bundle tabular determinístico.
La conversión GeoJSON es una acción posterior y explícita de
`poverty_pipeline.publication.geojson`; el comando canónico no contiene clientes,
credenciales ni comandos de despliegue de Mapbox u otro servicio remoto.

Las funciones `sintetizar_datos`, `exportar_a_json`, `process_and_save` y sus
variantes permanecen en `notebooks/funciones.py` exclusivamente para poder abrir
notebooks históricos. Ningún módulo bajo `src/` las importa ni las utiliza para
producir releases.

El lock no puede reemplazar estos roles por notebooks, gráficos o publicación.

### Notebooks históricos (1–5)

Los notebooks numerados 1–5 se conservan **únicamente como evidencia histórica y
exploratoria**. No forman parte de una secuencia de producción, no deben
ejecutarse de punta a punta y no están autorizados para muestrear el Censo,
deserializar modelos upstream, descargar canastas/IPC mutables ni escribir una
release canónica de pobreza. Su código original quedó como celdas `raw` para
trazabilidad.

Para producir resultados use solamente el slice lock gobernado:

```bash
PYTHONPATH=src python -m poverty_pipeline run-lock <poverty-slice-lock/v1-path>
```

Después de esa ejecución, los notebooks pueden usarse para investigación
leyendo las tablas inmutables de la release mediante `POVERTY_RELEASE_DIR`. Esa
ruta debe apuntar al directorio versionado escrito por el comando anterior; los
notebooks no actualizan ni reemplazan sus tablas.


## [Conjuntos de Datos](docs/data.md)

Una variedad de conjuntos de datos se utilizan en este proyecto, tanto fuentes originales como bases de datos derivadas. Para una descripción detallada de cada conjunto de datos, sus fuentes, y cómo se procesan, consulte el documento vinculado en [docs/data.md](docs/data.md).

## Resultados

Los resultados del análisis se presentan en forma de gráficos, mapas y tablas. También se proporcionan insights y conclusiones basadas en los hallazgos. Consulte la sección de resultados para una revisión detallada.


## Mantenimiento rápido del repo

### Sprint-zero contracts and synthetic adapters

The isolated `poverty_pipeline` package validates immutable shared envelopes and
adapts only synthetic Census and person-income fixtures. It does not load a
model or execute a poverty methodology. Run:

```bash
make contracts-check
make contracts-smoke
make adapters-smoke
PYTHONPATH=src python -m poverty_pipeline validate-lock fixtures/slice-locks/contracts-only.yaml
```

`make smoke` remains the historical structural notebook check; it is not a
scientific validation or poverty execution.

Para revisar higiene del repositorio y diferencias con remoto (si está configurado):

```bash
make hygiene
make policy-check
```

`policy-check` inspecciona los módulos de producción en `src/` y rechaza rutas
absolutas del autor, inputs desde `raw.githubusercontent.com`, deserialización de
modelos y selección directa mediante reloj de pared. La excepción declarada se
limita a `notebooks/` y `notebooks_legacy/`, que son archivos históricos y nunca
se importan desde producción.

Esto genera un reporte con:
- rama actual y remotos configurados,
- divergencia ahead/behind contra upstream,
- resumen del working tree (agregados/modificados/eliminados/no trackeados),
- top 20 archivos versionados más pesados.

## Sumate al Equipo

Sumate si te interesa ser parte del proyecto con alguno de estos perfiles.

1. **Científic/a de Datos/Analista**: Mantener la parte científica del análisis.
   
2. **Especialista GIS**: Mantener los mapas.
   
3. **Ingenier/a de Datos**: gestionar los datos.
   
4. **Desarrollador/a Front-end**: Mantener la página.

5. **Especialista en Documentación y Difusión**: Redactar, documentar y difundír el proyecto.

6. **Gestor/a de Proyecto**: Coordinar todo para que funcione.
   
7. **Community Manager**: Manejar la comunidad y las colaboraciones.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulte el archivo `LICENSE` para obtener más detalles.

### Visible synthetic release and local recovery

The governed, deterministic demonstration is explicitly synthetic and is never an
official estimate. Build, verify, load, plot, map, inspect, and determinism-check it with:

```bash
make poverty-release-smoke
PYTHONPATH=src python -m poverty_pipeline inspect-release build/releases/synthetic-visible-poverty-2024q1/v1
make local-artifact-inventory
make release-index
```

The canonical v1 bundle uses manifest-addressed CSV tables. Every scientific
input and output role is identified by `release_manifest.json`; optional Parquet
files are derivatives only. Local recovery inventories historical files read-only
and refuses fuzzy, positional, or monetarily incompatible joins.
