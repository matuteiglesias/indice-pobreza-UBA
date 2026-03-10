from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from indice_pobreza_uba.config_loader import PipelineConfig
from indice_pobreza_uba.paths import (
    ensure_directory,
    render_stage_01_legacy_filename,
    render_stage_01_person_predictions_path,
)
from variables import (
    x_cols1,
    x_cols2,
    x_cols3,
    x_cols4,
    y_cols1,
    y_cols2,
    y_cols3,
    columnas_pesos,
)

import numpy as np

def transform_censo_data(table):
    """Transforma las categorías de respuestas del censo para que coincidan con las de la EPH."""
    # Adaptaciones de VIVIENDA, HOGAR y PERSONA
    table['V01'] = table['V01'].map({1:1, 2:6, 3:6, 4:2, 5:3, 6:4, 7:5, 8:6})
    table['H06'] = table['H06'].map({1:1, 2:2, 3:3, 4:4, 5:5, 6:6, 7:7, 8:9})
    table['H09'] = table['H09'].map({1:1, 2:2, 3:3, 4:4, 5:4, 6:4})
    table['H16'] = table['H16'].clip(0, 9)
    table['H14'] = table['H14'].map({1:1, 2:4, 3:2, 4:2, 5:4, 6:3, 7:4, 8:9})
    table['H13'] = table['H13'].map({1:1, 2:2, 4:0})
    table['P07'] = table['P07'].map({1:1, 2:2, 0:2})
    return table



def generate_unique_ids(table, n_digits=9):
    """Genera IDs únicos para cada fila en la tabla."""
    possible_ids = np.arange(10**(n_digits - 1), 10**n_digits)
    n_rows = len(table)
    random_numbers = np.random.choice(possible_ids, n_rows, replace=False)
    last_two_digits_year = table['ANO4'].apply(lambda x: int(str(x)[-2:]))
    table.insert(0, 'ID', random_numbers * 100 + last_two_digits_year)
    return table


def ajustar_empleo(data, q, empleo, CONDACT_cnts, tasa_C2010, verbose=False):
        
    ratio = empleo.loc[pd.to_datetime(q)].censo2010_ratio
    n_desempleados_ = ratio*(CONDACT_cnts[1] + CONDACT_cnts[2])*tasa_C2010
    desemp_adic = round(n_desempleados_ - CONDACT_cnts.loc[2]) # Desempleados adicionales
    
    print(str(q)[:10])

    if desemp_adic > 0:
        data.loc[
            data.query('CONDACT == 1').sample(desemp_adic).index,
            'CONDACT'
        ] = 2
    elif desemp_adic < 0:
        data.loc[
            data.query('CONDACT == 2').sample(- desemp_adic).index,
            'CONDACT'
        ] = 1

    if verbose:
        desempleo = data.CONDACT.value_counts().loc[2] / (data.CONDACT.value_counts().loc[1] + data.CONDACT.value_counts().loc[2])
        print('desempleo:' + str(desempleo))
    
    return data

import joblib
# import gc
import os

def predict_save(X_data, x_cols, y_cols, model_filename, out_filename, tag, overwrite = False):

    # Si todavia no existe la training data de ese anio, o si la opcion overwrite esta activada:
    if (not os.path.exists(out_filename)) or (overwrite): 
        # display(X_data.count())

        # Check for NaN values in X_data
        if X_data[x_cols].isnull().any().any():
            print("Error: The data contains NaN values, possibly due to mismatched IDs after updating the synthetic populations data.")
            print("Consider setting the 'overwrite' parameter to True.")
            # return
        # print(model_filename)
        CLF = joblib.load(model_filename)
        
        y_out = CLF.predict(X_data[x_cols].values)

        ## Listo
        y_censo_fit = pd.DataFrame(y_out, index = X_data.index, columns=y_cols)
        
        # Xy_censo = pd.concat([X_data, y_censo_fit], axis = 1)

#             save
        y_censo_fit = y_censo_fit.round(5)
        if out_filename == '/media/matias/Elements/suite/resultados/RFReg_0.05_2022-08-15_ARG.csv': 
            out_filename = '/media/matias/Elements/suite/resultados/RFReg_0.05_2022-08-15_ARG_.csv'
        print(out_filename)
        y_censo_fit.to_csv(out_filename, index = True) #, index_label = 'ID')
        print('File saved at '+ out_filename)
        del X_data; del CLF

    # return y_censo_fit
#             gc.collect()

def run_predict_save(iter_dict, overwrite=False):
    predict_save(**iter_dict)
    out_filename = iter_dict['out_filename']

    if out_filename == '/media/matias/Elements/suite/resultados/RFReg_0.05_2022-08-15_ARG.csv': 
        out_filename = '/media/matias/Elements/suite/resultados/RFReg_0.05_2022-08-15_ARG_.csv'

    if not overwrite and os.path.exists(out_filename):
        print(f"File {out_filename} already exists. Read from csv...")
        return pd.read_csv(out_filename, index_col=['ID'])



def shift_to_mid_quarter_index(df):
    """
    Shift the index of a DataFrame to the 15th of the second month of each quarter.
    """
    df.index = df.index.map(lambda d: pd.Timestamp(year=d.year, month=(d.month + 1) // 3 * 3 - 1, day=15))
    return df

def resample_and_interpolate(df, freq='Q-FEB'):
    """
    Resample the DataFrame to the specified frequency and interpolate missing values.
    """
    df_resampled = df.resample(freq).asfreq()
    df_resampled.index = df_resampled.index.map(lambda x: pd.Timestamp(year=x.year, month=x.month, day=15))
    df_resampled = df_resampled.interpolate(method='linear')
    df_resampled.fillna(df.mean(), inplace=True)
    return df_resampled



# Assumed to already exist in this file, migrated from legacy funciones.py:
# - ajustar_empleo
# - run_predict_save
# - generate_Qs_from_year


def load_labor_inputs(cfg: PipelineConfig) -> tuple[pd.DataFrame, float]:
    """
    Load labor-market series used to adjust CONDACT by quarter.

    Legacy notebook logic:
    - reads 45.2_ECTDT.csv
    - keeps column 45.2_ECTDT_0_T_33
    - computes censo2010_ratio relative to 2010-11-15
    - reads desoc_AGLOsi_C2010.csv and extracts Tasa desocupacion where AGLOSI == True
    """
    labor_dir = cfg.paths["labor_series_dir"]

    empleo_file = labor_dir / "45.2_ECTDT.csv"
    desempleo_file = labor_dir / "desoc_AGLOsi_C2010.csv"

    empleo_raw = pd.read_csv(empleo_file, index_col=0, parse_dates=True)
    empleo = empleo_raw[["45.2_ECTDT_0_T_33"]].copy()
    empleo["censo2010_ratio"] = empleo["45.2_ECTDT_0_T_33"] / empleo.loc["2010-11-15", "45.2_ECTDT_0_T_33"]

    desoc_c2010 = pd.read_csv(desempleo_file).rename(columns={"AGLO_si": "AGLOSI"})
    tasa_c2010 = desoc_c2010.loc[desoc_c2010["AGLOSI"] == True, "Tasa desocupacion"].values[0]

    return empleo, float(tasa_c2010)


def resolve_quarters(cfg: PipelineConfig) -> list[str]:
    """
    Resolve target quarters.

    Priority:
    1. run.quarters if explicitly set
    2. all quarters generated from each year in run.years
    """
    run_cfg = cfg.run
    explicit_quarters = run_cfg.get("quarters")
    if explicit_quarters:
        return list(explicit_quarters)

    years = run_cfg["years"]
    quarters: list[str] = []
    for year in years:
        quarters.extend(generate_Qs_from_year(year))
    return quarters


def load_synthetic_population_for_year(cfg: PipelineConfig, year: int | str) -> pd.DataFrame:
    """
    Load the yearly synthetic population input using the configured filename pattern.

    The legacy notebook reads only the columns needed for the RFC chain:
    x_cols1 + ID and several household/geographic ids. :contentReference[oaicite:3]{index=3}
    """
    frac = cfg.run["frac"]
    experiment_tag = cfg.run["experiment_tag"]

    filename = cfg.inputs["synthetic_population"]["filename_pattern"].format(
        frac=frac,
        year=year,
        experiment_tag=experiment_tag,
    )
    input_path = cfg.paths["synthetic_population_dir"] / filename

    usecols = list(dict.fromkeys(
        x_cols1 + [
            "ID",
            "AGLOMERADO",
            "DPTO",
            "HOGAR_REF_ID",
            "PERSONA_REF_ID",
            "RADIO_REF_ID",
            "URP",
        ]
    ))

    df = pd.read_csv(
        input_path,
        usecols=usecols,
        index_col=["ID"],
    ).fillna(0)

    return df


def build_model_path(cfg: PipelineConfig, stage_num: int, q: str, year: int | str) -> Path:
    """
    Reconstruct the legacy model naming convention from the notebook.

    Legacy behavior:
    - clf1_{year}_{MODELS_TAG}
    - clf2_{year}_{MODELS_TAG}
    - clf3_{year}_{MODELS_TAG}
    - clf4_{q[:10]}_{MODELS_TAG}
    """
    models_dir = cfg.paths["trained_models_dir"]
    models_tag = cfg.run["experiment_tag"]

    if stage_num == 4:
        model_name = f"clf4_{q[:10]}_{models_tag}"
    else:
        model_name = f"clf{stage_num}_{year}_{models_tag}"

    return models_dir / model_name


def build_legacy_output_paths(cfg: PipelineConfig, q: str) -> list[Path]:
    """
    Compatibility output paths for the RFC1..RFC4 chain.

    These preserve the legacy intermediate files while the downstream migration
    is still in progress.
    """
    frac = cfg.run["frac"]
    experiment_tag = cfg.run["experiment_tag"]
    stage_dir = cfg.paths["stage_predict_dir"]

    ensure_directory(stage_dir)

    return [
        render_stage_01_legacy_filename(stage_dir, stage_num=i, frac=frac, q=q[:10], tag=experiment_tag)
        for i in range(1, 5)
    ]


def run_prediction_for_quarter(
    cfg: PipelineConfig,
    q: str,
    empleo: pd.DataFrame,
    tasa_c2010: float,
    run_ctx: dict[str, Any] | None = None,
) -> pd.DataFrame | None:
    """
    Run the full RFC1 -> RFC4 prediction chain for one quarter.

    Returns the final RFC4 dataframe if successful, otherwise None.
    """
    year = int(str(q)[:4])
    overwrite = bool(cfg.run.get("overwrite", False))

    # The legacy notebook gates execution on the clf4 model existing first. :contentReference[oaicite:4]{index=4}
    clf4_model = build_model_path(cfg, stage_num=4, q=q, year=year)
    if not clf4_model.exists():
        print(f"Warning: Model file {clf4_model} for {q} not found. Skipping this quarter.")
        return None

    # Check yearly synthetic population input exists.
    synthetic_filename = cfg.inputs["synthetic_population"]["filename_pattern"].format(
        frac=cfg.run["frac"],
        year=year,
        experiment_tag=cfg.run["experiment_tag"],
    )
    synthetic_path = cfg.paths["synthetic_population_dir"] / synthetic_filename
    if not synthetic_path.exists():
        print(f"Warning: Data file {synthetic_path} for year {year} not found. Skipping.")
        return None

    # Load base synthetic population.
    x_censo = load_synthetic_population_for_year(cfg, year)

    # Quarter-specific adjustments.
    condact_cnts = x_censo["CONDACT"].value_counts()
    x_q = x_censo.copy()
    x_q["Q"] = q
    x_q = ajustar_empleo(x_q, q, empleo, condact_cnts, tasa_c2010)

    # Legacy-compatible RFC intermediate outputs.
    filenames = build_legacy_output_paths(cfg, q)

    # Iteration 1
    predict_save_iter_dict1 = {
        "X_data": x_q,
        "x_cols": x_cols1,
        "y_cols": y_cols1,
        "out_filename": str(filenames[0]),
        "model_filename": str(build_model_path(cfg, stage_num=1, q=q, year=year)),
        "tag": f"clf1_{year}_{cfg.run['experiment_tag']}",
        "overwrite": overwrite,
    }
    result1 = run_predict_save(predict_save_iter_dict1, overwrite=overwrite)

    # Iteration 2
    predict_save_iter_dict2 = {
        "X_data": pd.concat([x_q, result1], axis=1),
        "x_cols": x_cols2,
        "y_cols": y_cols2,
        "out_filename": str(filenames[1]),
        "model_filename": str(build_model_path(cfg, stage_num=2, q=q, year=year)),
        "tag": f"clf2_{year}_{cfg.run['experiment_tag']}",
        "overwrite": overwrite,
    }
    result2 = run_predict_save(predict_save_iter_dict2, overwrite=overwrite)

    # Iteration 3
    predict_save_iter_dict3 = {
        "X_data": pd.concat([x_q, result1, result2], axis=1),
        "x_cols": x_cols3,
        "y_cols": y_cols3,
        "out_filename": str(filenames[2]),
        "model_filename": str(build_model_path(cfg, stage_num=3, q=q, year=year)),
        "tag": f"clf3_{year}_{cfg.run['experiment_tag']}",
        "overwrite": overwrite,
    }
    result3 = run_predict_save(predict_save_iter_dict3, overwrite=overwrite)

    # Iteration 4
    predict_save_iter_dict4 = {
        "X_data": pd.concat([x_q, result1, result2, result3], axis=1),
        "x_cols": x_cols4,
        "y_cols": columnas_pesos,
        "out_filename": str(filenames[3]),
        "model_filename": str(build_model_path(cfg, stage_num=4, q=q, year=year)),
        "tag": f"clf4_{year}_{cfg.run['experiment_tag']}",
        "overwrite": overwrite,
    }
    result4 = run_predict_save(predict_save_iter_dict4, overwrite=overwrite)

    if result4 is None:
        final_csv = filenames[3]
        if final_csv.exists():
            result4 = pd.read_csv(final_csv, index_col=["ID"])

    if result4 is None:
        print(f"Warning: RFC4 output for {q} could not be loaded after prediction.")
        return None

    # Canonical stage-01 artifact
    canonical_out = render_stage_01_person_predictions_path(
        cfg,
        q=q,
        frac=cfg.run["frac"],
        experiment_tag=cfg.run["experiment_tag"],
    )
    ensure_directory(canonical_out.parent)

    canonical_df = result4.copy()
    canonical_df["Q"] = q
    canonical_df.to_parquet(canonical_out)

    print(f"Canonical stage output saved to {canonical_out}")
    return canonical_df


def run_stage_01_predict(
    cfg: PipelineConfig,
    run_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Public entrypoint for stage 01.

    Runs the quarter-level prediction chain and writes canonical artifacts.
    """
    empleo, tasa_c2010 = load_labor_inputs(cfg)
    quarters = resolve_quarters(cfg)

    completed: list[str] = []
    skipped: list[str] = []

    for q in quarters:
        result = run_prediction_for_quarter(
            cfg=cfg,
            q=q,
            empleo=empleo,
            tasa_c2010=tasa_c2010,
            run_ctx=run_ctx,
        )
        if result is None:
            skipped.append(q)
        else:
            completed.append(q)

    return {
        "stage_name": "stage_01_predict",
        "completed_quarters": completed,
        "skipped_quarters": skipped,
        "n_completed": len(completed),
        "n_skipped": len(skipped),
    }