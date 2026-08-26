# Índice de pobreza UBA

Infraestructura de investigación para clasificar hogares/personas de una muestra Census a partir de insumos **ya materializados, versionados y aprobados**. El runner de pobreza es deliberadamente un consumidor: no descarga EPH, no entrena modelos y no ejecuta sklearn.

> **Evolución v2 en curso.** El destino del repositorio es una autoridad científica más fina: recibir un frame/población gobernado, estimaciones de bienestar ya desplegadas, un método de pobreza versionado y líneas compatibles; producir medición/estimación de pobreza, FGT, incertidumbre propagada cuando exista evidencia para ello y validación científica. Ver [`docs/ARCHITECTURE_V2.md`](docs/ARCHITECTURE_V2.md), [`docs/DEVELOPMENT_PROGRAM_V2.md`](docs/DEVELOPMENT_PROGRAM_V2.md) y [`docs/UPSTREAM_HANDOFFS_V2.md`](docs/UPSTREAM_HANDOFFS_V2.md). La interfaz v1 descripta abajo sigue siendo la superficie ejecutable mientras esa evolución se prueba.

## Interfaz canónica actual (v1)

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
