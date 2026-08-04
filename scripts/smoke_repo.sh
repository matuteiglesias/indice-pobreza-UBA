#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

echo "# Smoke check: indice-pobreza-UBA"

required_files=(
  "notebooks/1. Configuración y Datos Auxiliares.ipynb"
  "notebooks/2. Procesamiento Principal de Datos.ipynb"
  "notebooks/3. Calculo de Pobreza.ipynb"
  "notebooks/4. Estadisticas Descriptivas.ipynb"
  "notebooks/5. Manejo de Datos Geoespaciales.ipynb"
  "notebooks/funciones.py"
  "notebooks/variables.py"
  "data/info/radio_ref.csv"
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { echo "missing: $file"; exit 1; }
  echo "ok: $file"
done

python - <<'PY'
import json
from pathlib import Path

notebooks = [
    "notebooks/1. Configuración y Datos Auxiliares.ipynb",
    "notebooks/2. Procesamiento Principal de Datos.ipynb",
    "notebooks/3. Calculo de Pobreza.ipynb",
    "notebooks/4. Estadisticas Descriptivas.ipynb",
    "notebooks/5. Manejo de Datos Geoespaciales.ipynb",
]

for nb_path in notebooks:
    nb = json.loads(Path(nb_path).read_text())
    cells = nb.get("cells", [])
    if nb.get("metadata", {}).get("poverty_pipeline_status") != "historical-exploratory":
        raise SystemExit(f"missing historical metadata in {nb_path}")
    if not cells or "HISTÓRICO / EXPLORATORIO" not in "".join(cells[0].get("source", [])):
        raise SystemExit(f"missing historical banner in {nb_path}")
    code = [cell for cell in cells if cell.get("cell_type") == "code"]
    if len(code) != 1 or "load_released_tables" not in "".join(code[0].get("source", [])):
        raise SystemExit(f"notebook does not exclusively import released tables: {nb_path}")

print("ok: historical notebooks are read-only released-output consumers")
PY

echo "smoke check passed"
