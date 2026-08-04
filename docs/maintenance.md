# Mantenimiento y diferencias local/remoto

## 1) Estado rápido

```bash
git status --short --branch
```

## 2) Verificar remotos

```bash
git remote -v
```

Si no hay remotos configurados, agregá `origin` antes de comparar local/remoto.

## 3) Reporte de higiene (recomendado)

```bash
make hygiene
```

Este comando ejecuta `scripts/repo_hygiene_report.sh` y muestra:

- rama actual y remotos,
- divergencia `ahead/behind` con upstream,
- resumen de cambios locales,
- archivos versionados más pesados.

## 4) Checklist operativo

- Confirmar si hay archivos grandes que deban salir de git (`data/`, outputs intermedios).
- Revisar notebooks modificados y limpiar outputs antes de commitear.
- Evitar commitear artefactos locales (`artifacts/`, `notes/`, `tags`, caches).
- Mantener un commit por tema (higiene, datos, notebooks, docs).


## 5) Smoke check operacional mínimo

```bash
make smoke
```

Este smoke no ejecuta ciencia; valida el archivo histórico de los notebooks:

- presencia de los notebooks históricos 1–5 y de su advertencia de archivo,
- presencia de helpers (`notebooks/funciones.py`, `notebooks/variables.py`),
- presencia de un insumo local clave (`data/info/radio_ref.csv`),
- estructura segura (una única celda de código que importa tablas de una release
  gobernada; el código anterior permanece como celdas `raw`).

Si falla, corrija la estructura de archivo. No realice una corrida manual: use
`PYTHONPATH=src python -m poverty_pipeline run-lock <poverty-slice-lock/v1-path>`.
