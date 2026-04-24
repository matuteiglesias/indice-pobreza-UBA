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

Este smoke no ejecuta el pipeline completo (que depende de notebooks, datos locales y librerías pesadas), pero valida una base mínima:

- presencia de notebooks núcleo del flujo actual (1→5),
- presencia de helpers (`notebooks/funciones.py`, `notebooks/variables.py`),
- presencia de un insumo local clave (`data/info/radio_ref.csv`),
- estructura básica del notebook (parámetros esperados como `FRAC` y referencias a salidas de pobreza).

Si este chequeo falla, conviene corregir estructura/rutas antes de intentar una corrida manual de notebooks.
