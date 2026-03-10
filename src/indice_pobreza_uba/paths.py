

from dateutil.relativedelta import relativedelta
from datetime import datetime
import geopandas as gpd

def generate_Qs(start_date, end_date):
    """
    Generate a list of quarterly dates between start_date and end_date.
    Dates are in the format YYYY-MM-DD and occur on the 15th of the mid month of each quarter.
    
    Parameters:
    - start_date: string, the start date in the format 'YYYY-MM-DD'
    - end_date: string, the end date in the format 'YYYY-MM-DD'
    
    Returns:
    - A list of quarterly dates.
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    current = start
    Qs = []
    
    while current <= end:
        Qs.append(current.strftime('%Y-%m-%d'))
        current += relativedelta(months=3)
    
    return Qs

def generate_Qs_from_year(year):
    """
    Generate a list of quarterly dates for a given year.
    Dates are in the format YYYY-MM-DD and occur on the 15th of the mid month of each quarter.
    
    Parameters:
    - year: int or string, the year for which the quarterly dates are to be generated
    
    Returns:
    - A list of quarterly dates.
    """
    quarters = ["-02-15", "-05-15", "-08-15", "-11-15"]
    return [str(year) + q for q in quarters]


def process_and_save(data, grouper, geo_df, filename_prefix, frac=0.05):
    # Sintetizar datos, eliminar columna 'timestamp' y cambiar la forma del DataFrame
    df_ = sintetizar_datos(data, [grouper], base=filename_prefix, frac=frac)
    df_ = df_.drop('timestamp', axis=1)
    df = df_.set_index(list(df_.drop('valor', axis=1).columns)).unstack([0, 1])['valor']

    # Renombrar columnas y resetear índice
    # df.columns, df = ['_'.join(col) for col in df.columns.values], df.reset_index()
    df.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in df.columns]
    df = df.reset_index()
    

    # print(df.columns)
    
    # Fusionar con el GeoDataFrame para formar el gdf final
    # display(df.head())
    # display(geo_df.head())
    gdf = gpd.GeoDataFrame(df.merge(geo_df), crs=geo_df.crs)
    # display(gdf.head())
    # Guardar el gdf como GeoJSON
    filename = f'poverty_{filename_prefix}_{grouper}.geojson'
    gdf.to_file('./../data/geojson/' + filename, driver='GeoJSON')
    
    # Mostrar columnas y sus dtypes
    # print(filename, gdf.dtypes)



from pathlib import Path

from indice_pobreza_uba.config_loader import PipelineConfig


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def render_stage_01_legacy_filename(
    stage_dir: Path,
    stage_num: int,
    frac: float,
    q: str,
    tag: str,
) -> Path:
    return stage_dir / f"RFC{stage_num}_{frac}_{q}_{tag}.csv"


def render_stage_01_person_predictions_path(
    cfg: PipelineConfig,
    q: str,
    frac: float,
    experiment_tag: str,
) -> Path:
    return cfg.artifact_path(
        "stage_01_predict",
        "person_predictions",
        Q=q,
        frac=frac,
        experiment_tag=experiment_tag,
    )