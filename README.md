# Índice de pobreza UBA

Infraestructura científica terminal para medir y estimar pobreza a partir de insumos **ya materializados, versionados y aprobados**. El estimador productivo es deliberadamente consumidor: no adquiere EPH/Census, no entrena modelos y no ejecuta sklearn. Los harnesses bajo `science/` sí pueden leer evidencia EPH/Census explícita para validación y commissioning sin convertirse en productores upstream.

> **v2 es la arquitectura científica activa.** El repositorio recibe un frame/población gobernado, bienestar ya desplegado, un método de pobreza versionado, líneas compatibles y, cuando hace falta, un binding explícito de área de umbral; produce medición/estimación FGT, releases verificables y evidencia de validación/commissioning. La interfaz v1 se conserva sólo como compatibilidad y evidencia de regresión. Ver [`docs/ARCHITECTURE_V2.md`](docs/ARCHITECTURE_V2.md), [`docs/DEVELOPMENT_PROGRAM_V2.md`](docs/DEVELOPMENT_PROGRAM_V2.md) y [`docs/UPSTREAM_HANDOFFS_V2.md`](docs/UPSTREAM_HANDOFFS_V2.md).

## Superficie científica actual (v2)

La superficie activa ya no es un runner atado a una única geografía. En `main` están implementados y probados:

- contrato de método y kernel puro de medición FGT0/FGT1/FGT2;
- estimación separada de la medición, con pesos/diseño explícitos y dominios gobernados;
- `poverty-estimate-release/v2` detached, con `capabilities.json`, contrato de join geográfico, QA, limitaciones y checksums;
- productores predictivos gobernados para `province_2010`, `department_2010` y `eph_agglomerate`;
- agregados no espaciales explícitos: `national/ARG` para las superficies administrativas y `eph_coverage/EPH_TOTAL` para la cobertura EPH;
- Telescope A (EPH observado), Telescope B (observado → OOF point → predictivo) y Telescope C (transporte EPH → Census);
- dashboard de commissioning y comparador observado-vs-predictivo por aglomerado.

La geografía sigue siendo una clave, nunca una geometría calculada dentro de Poverty. `eph_agglomerate` es una geografía de cobertura EPH de primer nivel: puede cruzar provincias/departamentos y no recibe un padre administrativo inventado.

## Interfaz legacy compatible (v1)

Una corrida científica recibe un único lock `poverty-slice-lock/v1`:

```bash
PYTHONPATH=src python -m poverty_pipeline run-lock <poverty-slice-lock/v1-path>
```

El lock fija por `release_id`, ruta local y SHA-256 exactamente cuatro tipos de artefacto directos:

| Rol | Tipo obligatorio | Uso |
|---|---|---|
| muestra | `research.census-sample/v1` | personas, hogares, pesos y geografía Census aprobada |
| ingresos | `research.person-income-predictions/v1` | ingreso por persona en el mismo namespace/período |
| equivalencia | `research.poverty-adult-equivalence/v1` | coeficientes aprobados por sexo/edad |
| canastas | `research.regional-baskets/v1` | CBA/CBT por región, período y referencia monetaria |

### Frontera de consumo

La EPH anual, el entrenamiento del modelo, la alineación EPH↔Censo y la ejecución que produce `research.person-income-predictions/v1` son **linaje upstream**. Pueden quedar registrados en manifests para trazabilidad, pero el runner de pobreza no los abre ni los reejecuta.

En particular, este repositorio no debe:

- importar `income-modeling-eph` para deserializar o entrenar modelos;
- ejecutar `eph-censo-aligner` durante una corrida de pobreza;
- reconstruir una muestra Census;
- aceptar EPH como input directo del kernel;
- elegir una geografía upstream ni inventar una asignación espacial;
- convertir una predicción logarítmica a ingreso lineal sin una política monetaria/retransformación explícita en el artefacto correspondiente.

Su trabajo comienza cuando la muestra, los ingresos, la equivalencia adulta y las canastas ya existen como artefactos compatibles.

## Qué produce

Una ejecución autorizada escribe una release inmutable bajo:

```text
<release_root>/<slice_id>/<release_version>/
```

Los roles mínimos del bundle son:

- `person_classification`;
- `household_classification`;
- `aggregates_tidy`;
- `department_summary`;
- `national_summary`;
- `release_manifest`;
- `run_qa`;
- `limitations`;
- `checksums`;
- `department_spatial`, sólo si se solicita el derivado GeoJSON.

Los joins fallan ante namespaces incompatibles, cobertura incompleta, cardinalidades inválidas o referencias monetarias incompatibles.

## Universo de la interfaz legacy v1

La interfaz v1 soporta `department_2010` / CPV-2010. La tabla nacional reconcilia esos departamentos. Radios, fracciones, provincias, aglomerados EPH, geografía electoral, publicación web, empleo, nowcasts y estadísticas oficiales quedan fuera de esta interfaz salvo una evolución explícita del contrato.

La arquitectura v2 separa explícitamente `frame_vintage` de `estimation_period`: usar un frame derivado de CPV-2010 para una estimación posterior no convierte ese frame en un Censo del período de análisis. También desplaza la región de línea/canasta fuera de la identidad geográfica intrínseca del frame.

## Separación de responsabilidades

Este repositorio **sí** posee metodología de pobreza específica del proyecto: equivalencia adulta aprobada, comparación contra CBA/CBT, clasificación, gaps/FGT, estimandos permitidos y agregación/estimación de hogares/personas ya materializados.

No posee:

- estadísticas oficiales de pobreza;
- adquisición de EPH o Census;
- muestreo Census;
- modelado/entrenamiento de ingresos;
- scoring Census de modelos promocionados;
- alineación semántica EPH↔Censo;
- autoridad geográfica argentina;
- despliegue web remoto.

## Notebooks históricos

Los notebooks numerados 1–5 se conservan como evidencia histórica/exploratoria. No son una secuencia de producción y no están autorizados para muestrear Census, cargar modelos upstream, descargar insumos mutables ni escribir la release canónica.

Después de producir una release, pueden leerla mediante `POVERTY_RELEASE_DIR` para exploración sin reemplazar sus tablas.

Otros notebooks históricos de empleo, nowcasting, geografía y publicación permanecen preservados hasta una wave explícita de decommission; su presencia física no amplía la autoridad actual del repo.

## Verificación y mantenimiento

```bash
make contracts-check
make contracts-smoke
make adapters-smoke
make poverty-release-smoke
make hygiene
make policy-check
```

`policy-check` protege la frontera productiva bajo `src/`: rechaza rutas absolutas del autor, inputs remotos mutables y deserialización de modelos. Los notebooks históricos están explícitamente fuera del runtime canónico.

La demostración visible es sintética y no constituye una estimación oficial:

```bash
PYTHONPATH=src python -m poverty_pipeline inspect-release \
  build/releases/synthetic-visible-poverty-2024q1/v1
make local-artifact-inventory
make release-index
```

### Releases predictivas por geografía gobernada (v2)

El productor canónico es `scripts/build_predictive_geography_release.py`. Los perfiles versionados en `configs/geographies/predictive_geography_profiles_v1.json` fijan inventario, campo de dominio, política de subconjunto y semántica del agregado.

Ejemplo administrativo:

```bash
PYTHONPATH=src python3 scripts/build_predictive_geography_release.py \
  --period 2024-Q3 \
  --geography-level department_2010 \
  --welfare-release /ruta/al/research.household-welfare-predictive/v1 \
  --frame /ruta/al/population-frame.json \
  --baskets /ruta/al/poverty-basket-slice.csv \
  --output /ruta/de/salida/poverty-department-2024-q3
```

Para `eph_agglomerate`, el frame debe haber sido augmentado con el handoff gobernado de `samplerCensoARG` y el productor exige un binding explícito `eph_agglomerate_id -> poverty_region_id`. Sólo contribuyen hogares con `mapped_to_eph_frame=true`; no se redistribuyen pesos ni se calibra masa poblacional. El agregado de la release es `eph_coverage/EPH_TOTAL`, nunca `national/ARG`.

`scripts/build_predictive_province_release.py` permanece como oracle de regresión de la primera integración provincial; no es la frontera general de geografía.


## Cómo colaborar

Son especialmente útiles contribuciones acotadas que mejoren una superficie que el repositorio realmente posee:

- evidencia/revisión del método de pobreza y equivalencia adulta;
- tests adversariales de contratos, joins, pesos y clasificación;
- FGT, incertidumbre y QA/reconciliación de estimandos;
- validación/paridad contra mediciones directas compatibles;
- documentación de decisiones metodológicas y limitaciones;
- mejoras de lectura/inspección **a partir de releases existentes**.

Una propuesta de modelado de ingresos, adquisición de EPH, muestreo Census, geografía o visualización pública debería dirigirse al repositorio que posee esa autoridad, en lugar de duplicarla aquí.

## Datos, resultados y licencia

Ver `docs/data.md` para documentación de datos y `docs/maintenance.md` para mantenimiento. Este proyecto se distribuye bajo licencia MIT. Los resultados derivados deben conservar sus manifests, limitaciones, procedencia y condición de estimación de investigación/no oficial.
