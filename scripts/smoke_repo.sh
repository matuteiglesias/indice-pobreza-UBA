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

pipeline = [
    "notebooks/1. Configuración y Datos Auxiliares.ipynb",
    "notebooks/2. Procesamiento Principal de Datos.ipynb",
    "notebooks/3. Calculo de Pobreza.ipynb",
    "notebooks/4. Estadisticas Descriptivas.ipynb",
    "notebooks/5. Manejo de Datos Geoespaciales.ipynb",
]

for nb_path in pipeline:
    nb = json.loads(Path(nb_path).read_text())
    code = "\n".join("".join(cell.get("source", [])) for cell in nb["cells"] if cell.get("cell_type") == "code")
    if "FRAC" not in code:
        raise SystemExit(f"missing FRAC parameter in {nb_path}")
    if nb_path.endswith("3. Calculo de Pobreza.ipynb") and "individual_income_sample" not in code:
        raise SystemExit(f"expected poverty output references not found in {nb_path}")

print("ok: notebook structure and key markers")
PY

echo "smoke check passed"
