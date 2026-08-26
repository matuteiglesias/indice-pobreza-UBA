# Índice de pobreza UBA

Infraestructura de investigación para clasificar hogares/personas de una muestra Census a partir de insumos **ya materializados, versionados y aprobados**. El runner de pobreza es deliberadamente un consumidor: no descarga EPH, no entrena modelos y no ejecuta sklearn.

## Interfaz canónica

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

## Universo soportado actualmente

La interfaz v1 soporta `department_2010` / CPV-2010. La tabla nacional reconcilia esos departamentos. Radios, fracciones, provincias, aglomerados EPH, geografía electoral, publicación web, empleo, nowcasts y estadísticas oficiales quedan fuera de esta interfaz salvo una evolución explícita del contrato.

## Separación de responsabilidades

Este repositorio **sí** posee metodología de pobreza específica del proyecto: equivalencia adulta aprobada, comparación contra CBA/CBT, clasificación, gaps, estimandos permitidos y agregación de hogares/personas ya clasificados.

No posee:

- estadísticas oficiales de pobreza;
- adquisición de EPH o Census;
- muestreo Census;
- modelado/entrenamiento de ingresos;
- alineación semántica EPH↔Censo;
- autoridad geográfica argentina;
- despliegue web remoto.

## Notebooks históricos

Los notebooks numerados 1–5 se conservan como evidencia histórica/exploratoria. No son una secuencia de producción y no están autorizados para muestrear Census, cargar modelos upstream, descargar insumos mutables ni escribir la release canónica.

Después de producir una release, pueden leerla mediante `POVERTY_RELEASE_DIR` para exploración sin reemplazar sus tablas.

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

## Cómo colaborar

Son especialmente útiles contribuciones acotadas que mejoren una superficie que el repositorio realmente posee:

- evidencia/revisión de equivalencia adulta o canastas;
- tests adversariales de locks, joins, pesos y clasificación;
- QA/reconciliación de agregados;
- documentación de decisiones metodológicas y limitaciones;
- mejoras de lectura, inspección o visualización **a partir de releases existentes**.

Una propuesta de modelado de ingresos, adquisición de EPH, muestreo Census o geografía debería dirigirse al repositorio que posee esa autoridad, en lugar de duplicarla aquí.

## Datos, resultados y licencia

Ver `docs/data.md` para documentación de datos y `docs/maintenance.md` para mantenimiento. Este proyecto se distribuye bajo licencia MIT. Los resultados derivados deben conservar sus manifests, limitaciones, procedencia y condición de estimación de investigación/no oficial.
