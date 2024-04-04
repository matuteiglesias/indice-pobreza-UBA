
import time
import numpy as np

def log_message(message, start_time=None):
    current_time = time.time()
    readable_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))
    elapsed_time = f'Elapsed time: {current_time - start_time:.2f} seconds' if start_time else ''
    print(f"[{readable_time}] {message} {elapsed_time}")

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

def run_predict_save(iter_dict):
    predict_save(**iter_dict)
    out_filename = iter_dict['out_filename']
    if out_filename == '/media/matias/Elements/suite/resultados/RFReg_0.05_2022-08-15_ARG.csv': 
        out_filename = '/media/matias/Elements/suite/resultados/RFReg_0.05_2022-08-15_ARG_.csv'
    return pd.read_csv(out_filename, index_col=['ID'])


# Funciones para transformación de ingresos y cálculo de pobreza
def personas_ingresos_por_trimestre(poblacion, Q, frac, experiment_tag='ARG'):
    # Define the path for RFReg
    path_modelo_ingresos = f'/media/matias/Elements/suite/resultados/RFC4_{str(frac)}_{Q}_{experiment_tag}.csv'
    # if path_modelo_ingresos == '/media/matias/Elements/suite/resultados/RFReg_0.05_2022-08-15_ARG.csv': 
    #     path_modelo_ingresos = '/media/matias/Elements/suite/resultados/RFReg_0.05_2022-08-15_ARG_.csv'


    # Check if the model file exists
    if not os.path.exists(path_modelo_ingresos):
        print(f"Error: archivo del modelo {path_modelo_ingresos} no existe. Calcular en notebook 02, o ignorar mensaje si el trimestre {Q} no tuvo EPH publicada por INDEC.values=")
        return None


    # Load data from RFReg, including the required column P47T
    print('reading regression results at: ', path_modelo_ingresos)
    columns_RFReg = ['ID', 'P47T']
    # columns_RFReg = ['ID'] + columnas_pesos
    regresion_ingresos = pd.read_csv(path_modelo_ingresos, usecols=columns_RFReg)
    regresion_ingresos['Q'] = Q

    # Union of household data to individual records
    regresion_ingresos = regresion_ingresos.rename(columns={'P47T': 'P47T_persona'})
    print(f"size/frac = Poblacion segun muestra pob con estimacion de ingresos: {len(regresion_ingresos)/frac}")
    
    result = poblacion.merge(regresion_ingresos, on='ID')

    # # Merge both DataFrames using the common 'ID' column
    return result


def ingresos_a_metricas_pobreza(df_ingresos, ad_eq, DPTO_Region, CB_ipc, frac, columnas_pesos=['P47T_persona']):
    """
    Transforms income data into poverty metrics and saves the results.
    
    Parameters:
    - df_ingresos (pd.DataFrame): DataFrame containing income data.
    - ad_eq (pd.DataFrame): ...
    - DPTO_Region (pd.DataFrame): ...
    - CB_ipc (pd.DataFrame): ...
    - frac (float): Fraction used for data sampling.
    - columnas_pesos (list, optional): List of columns to be processed. Default is ['P47T'].
    
    Returns:
    - None. But saves the processed data to a specified filename.
    """
    print(f"size/frac = Pob, input de ingresos_a_pobreza: {len(df_ingresos) / frac}")
    df_ingresos[columnas_pesos] = np.power(10, df_ingresos[columnas_pesos]) - 1

    # Print mean of float columns
    float_cols = df_ingresos.select_dtypes(include=['float64']).columns
    for col in float_cols:
        print(f"Mean of column {col}: {df_ingresos[col].mean()}")


    # Canasta calculation
    df_cb = canasta(df_ingresos, ad_eq, DPTO_Region, CB_ipc)
    print(f"size/frac = Pob after canasta calculation: {len(df_cb)/frac}")

    # Poverty metrics at household level
    pobreza_hogares = calculate_poverty_metrics(df_cb)
    print(f"size(hogares)/frac = Cantidad de hogares: {len(pobreza_hogares)/frac}")

    # Print mean of float columns
    float_cols = pobreza_hogares.select_dtypes(exclude=['object']).columns
    for col in float_cols:
        print(f"Mean of column {col}: {pobreza_hogares[col].mean()}")

    return pobreza_hogares

import pandas as pd
def geo_hogares(muestra_hogares, radio_ref_cols, radios_circuitos_secciones_ref, claves_dptos_cols, frac):
    """
    Transforms income data into poverty metrics and saves the results.

    Parameters:
    """
    # Selecting necessary columns
    # poblacion_cols = muestra_pob[['RADIO_REF_ID', 'DPTO', 'PROV', 'AGLOMERADO']]

    # Merge operations
    merged_df_1 = pd.merge(muestra_hogares, radio_ref_cols, on='RADIO_REF_ID', how='inner')
    print(f"size/frac = Pob after merging with radio_ref_cols: {len(merged_df_1)/frac}")
    print("maxs: ", merged_df_1.max())


    merged_df_3 = pd.merge(merged_df_1, radios_circuitos_secciones_ref, 
                           on = ['COD_2010'], how='left')
    display(merged_df_3.count())
    print(f"size/frac = Pob after merging with radios_circuitos_secciones_ref: {len(merged_df_3)/frac}")
    # print("dtypes: ", merged_df_3.dtypes)


    merged_df_4 = pd.merge(merged_df_3, claves_dptos_cols, on=['distrito_id', 'seccion_id'], how='left')
    print(f"size/frac = Pob after merging with IN1: {len(merged_df_4)/frac}")
    muestra_hogares_geo = merged_df_4
    print("dtypes: ", merged_df_4.dtypes)

    # Print mean of float columns
    float_cols = muestra_hogares.select_dtypes(include=['float64']).columns
    for col in float_cols:
        print(f"Mean of column {col}: {muestra_hogares_geo[col].mean()}")

    return muestra_hogares_geo

## Funcion para combinar preguntas de nivel educativo
def P0910(df):
    df['P10'] = 2 - df['P10']
    df['P09'] = df.P09.replace(5, 4)
    df['P0910'] = df.P09.astype(str) + df.P10.astype(str)
    return df

## Funcion para calcular la canasta
def canasta(df, ad_eq, DPTO_Region, CB_ipc):
    # Merge with additional data for canasta calculation
    df_cb = df.merge(ad_eq).merge(DPTO_Region).merge(CB_ipc)
    # el valor de canasta de una persona SE MULTIPLICA POR EL AD EQ (CB_EQUIV)
    df_cb['CBA'] *= df_cb['CB_EQUIV'] 
    df_cb['CBT'] *= df_cb['CB_EQUIV']
    return df_cb

## Funcion para calcular la pobreza de los hogares
def calculate_poverty_metrics(df, ingreso_monetario = 'P47T_persona'):
    df_cb_hogares = df.groupby(['HOGAR_REF_ID', 'Q'])[[ingreso_monetario,'CBA', 'CBT', 'CB_EQUIV']].sum()
    df_cb_hogares['Pobreza'] = df_cb_hogares[ingreso_monetario] < df_cb_hogares['CBT']
    df_cb_hogares['Indigencia'] = df_cb_hogares[ingreso_monetario] < df_cb_hogares['CBA']
    pobreza_hogares = df_cb_hogares.reset_index()
    pobreza_hogares['gap_pobreza'] = pobreza_hogares[ingreso_monetario] - pobreza_hogares.CBT
    pobreza_hogares['gap_indigencia'] = pobreza_hogares[ingreso_monetario] - pobreza_hogares.CBA
    return pobreza_hogares.rename(columns={ingreso_monetario: 'P47T_hogar'})



# # Funciones para modelado y predicción
# def train_model(data, features, target):
#     ...

# def predict_model(model, new_data):
#     ...

# Funciones de síntesis y exportación
import datetime as dt
from numpy import repeat

def sintetizar_datos(data, grouper, base='Personas', frac=0.05):
    df = data.copy()
    df['timestamp'] = dt.datetime.today()
    df['AGLOSI'] = df.AGLOMERADO != 0
    df['Total'] = True

    # Columnas comunes
    columns_to_groupby = ['Total', 'Pobreza', 'Indigencia']
    
    # Columnas específicas según base
    if 'P47T_persona' in df.columns:
        columns_to_groupby.append('P47T_persona')
    if 'P47T_hogar' in df.columns:
        columns_to_groupby.append('P47T_hogar')
    if 'CB_EQUIV' in df.columns:
        columns_to_groupby.extend(['CB_EQUIV', 'CBA', 'gap_indigencia', 'CBT', 'gap_pobreza'])

    agg_dict = {
        'Total': ['mean', 'sum'],
        'Pobreza': ['mean', 'sum'],
        'Indigencia': ['mean', 'sum']
    }
    
    if 'P47T_persona' in df.columns:
        agg_dict['P47T_persona'] = ['mean', q10, q25, 'median', q75, q90]
    if 'P47T_hogar' in df.columns:
        agg_dict['P47T_hogar'] = ['mean', q10, q25, 'median', q75, q90]
    if 'CB_EQUIV' in df.columns:
        agg_dict['CB_EQUIV'] = ['mean', 'median']
        agg_dict['CBA'] = ['mean', 'median']
        agg_dict['gap_indigencia'] = ['mean', 'median']
        agg_dict['CBT'] = ['mean', 'median']
        agg_dict['gap_pobreza'] = ['mean', 'median']

    df = df.groupby(grouper + ['timestamp'])[columns_to_groupby].agg(agg_dict)
    
    for col in ['CBA', 'CBT', 'gap_indigencia', 'gap_pobreza']: # Precision
        df[(col, 'mean')] = (df[(col, 'mean')]).round(-1).astype(int)

    for col in ['CB_EQUIV']: # Precision
        df[(col, 'mean')] = df[(col, 'mean')].round(3)

    for col in ['Total', 'Pobreza', 'Indigencia']:  ## Expansion a cant de poblacion
        df[(col, 'sum')] = (df[(col, 'sum')]/frac).round(1)
        df[(col, 'mean')] = df[(col, 'mean')].round(4)

    if 'P47T_persona' in df.columns:
        df['P47T_persona'] = df['P47T_persona'].round(-1).astype(int)
    if 'P47T_hogar' in df.columns:
        df['P47T_hogar'] = df['P47T_hogar'].round(-1).astype(int)

    agg_result = df.T.set_index(repeat(base, df.shape[1]), append=True)
    stacker_ix = [-i for i in range(len(grouper) + 1)]
    agg_result = agg_result.stack(level=stacker_ix).reset_index()
    
    agg_result = agg_result.rename(columns = {'level_0': 'observable', 'level_1': 'sintetico', 'level_2': 'base', 0: 'valor'})
    agg_result['frac'] = frac

    return agg_result

# Funciones de percentil
def q10(x):
    return x.quantile(0.1)

def q25(x):
    return x.quantile(0.25)

def q75(x):
    return x.quantile(0.75)

def q90(x):
    return x.quantile(0.9)


import os

def exportar_a_json(synth_func, data, grouper, base_str, frac, results_path = './../data/results/'):

    # Comprobar y crear el directorio de resultados si no existe
    if not os.path.exists(results_path):
        os.makedirs(results_path)


    """Función para agregar datos a un archivo JSON."""
    filename = f'{results_path}/result_{base_str}_{"-".join(grouper)}_{frac}.json'
    
    df = synth_func(data, grouper, frac)
    
    # Si el archivo no existe, lo crea. Si existe, concatena los nuevos datos.
    if not os.path.exists(filename):
        df.to_json(filename, orient="records")
    else:
        df_ = pd.concat([df, pd.read_json(filename)])
        df_.to_json(filename, orient="records")

# # Funciones utilitarias
# def calculate_percentile(...):
#     ...
import pandas as pd
import json
import os
import datetime as dt

def exportar_a_json_jerarquico(synth_func, data, grouper, base_str, frac=0.05):
    """
    Function to convert the processed DataFrame into a hierarchical JSON structure.
    Returns a JSON-compatible dictionary.
    """
    df = synth_func(data, grouper)
    timestamp = dt.datetime.now().isoformat()

    json_output = {}

    for _, row in df.iterrows():
        observable = row['observable']
        sintetico = row['sintetico']
        q_value = row['Q']

        # Initiate the hierarchy with observable
        if observable not in json_output:
            json_output[observable] = {}

        nested_data = json_output[observable]

        # Check for sintetico and initialize if not present
        if sintetico not in nested_data:
            nested_data[sintetico] = {
                'metadata': {
                    'last_updated': timestamp,
                    'frecuencia': 'Q',
                    'base_str': base_str,
                    'frac': frac  
                },
                'data': {}
            }

        # Navigate through the rest of the groupers
        for grp in grouper:
            if grp != 'Q':
                grp_val = row[grp]
                if grp_val not in nested_data[sintetico]['data']:
                    nested_data[sintetico]['data'][grp_val] = {}
                nested_data = nested_data[sintetico]['data'][grp_val]

        # Add the new Q value to the current nested_data
        nested_data[q_value] = row['valor']

    return json_output


# def merge_jsons(main_data, new_data):
#     """
#     Function to merge two JSON hierarchical structures.
#     Structure: observable -> sintetico -> grouper values -> Q values
#     """
#     for observable, metrics in new_data.items():
#         if observable not in main_data:
#             print(f"Observable {observable} not in main_data. Adding...")
#             main_data[observable] = {}
        
#         for sintetico, details in metrics.items():
#             if sintetico not in main_data[observable]:
#                 print(f"Sintetico {sintetico} not in main_data[{observable}]. Adding...")
#                 main_data[observable][sintetico] = {
#                     'metadata': details['metadata'],
#                     'data': {}
#                 }
#             else:
#                 # Update the last_updated metadata
#                 print(f"Updating last_updated metadata for {observable} -> {sintetico}")
#                 main_data[observable][sintetico]['metadata']['last_updated'] = details['metadata']['last_updated']
            
#             for grp_val, timeseries in details['data'].items():
#                 if grp_val not in main_data[observable][sintetico]['data']:
#                     print(f"Grouper value {grp_val} not in main_data[{observable}][{sintetico}]['data']. Adding...")
#                     main_data[observable][sintetico]['data'][grp_val] = {}
                
#                 # Update only the specific quarter without overwriting the entire dictionary
#                 for q, value in timeseries.items():
#                     if q not in main_data[observable][sintetico]['data'][grp_val]:
#                         print(f"Adding {observable} -> {sintetico} -> {grp_val} -> {q}: {value}")
#                     else:
#                         print(f"Updating {observable} -> {sintetico} -> {grp_val} -> {q}: {value}")
#                     main_data[observable][sintetico]['data'][grp_val][q] = value
                    
                
#     return main_data

def merge_jsons(main_data, new_data):
    """
    Function to merge two JSON hierarchical structures.
    Structure: observable -> sintetico -> grouper values -> Q values
    """
    
    def recursive_merge(dict1, dict2):
        merged = dict(dict1)
        for key, val in dict2.items():
            if key in merged:
                if isinstance(val, dict):
                    merged[key] = recursive_merge(merged[key], val)
                else:
                    merged[key] = val
            else:
                merged[key] = val
        return merged

    for observable, metrics in new_data.items():
        if observable not in main_data:
            print(f"Observable {observable} not in main_data. Adding...")
            main_data[observable] = {}
        
        for sintetico, details in metrics.items():
            if sintetico not in main_data[observable]:
                print(f"Sintetico {sintetico} not in main_data[{observable}]. Adding...")
                main_data[observable][sintetico] = {
                    'metadata': details['metadata'],
                    'data': {}
                }
            else:
                # Update the last_updated metadata
                print(f"Updating last_updated metadata for {observable} -> {sintetico}")
                main_data[observable][sintetico]['metadata']['last_updated'] = details['metadata']['last_updated']
                
            # Now use the recursive merge for the 'data' field
            main_data[observable][sintetico]['data'] = recursive_merge(main_data[observable][sintetico]['data'], details['data'])
            
    return main_data



from dateutil.relativedelta import relativedelta
from datetime import datetime

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




import os
import geopandas as gpd

def save_geojson(gdf, filename='test.geojson'):
    if not os.path.exists('./../data/geojson/'):
        os.makedirs('./../data/geojson/')
    
    filepath = './../data/geojson/' + filename
    if os.path.exists(filepath):
        os.remove(filepath)  # Eliminar si el geojson existe, porque no se admite la sobrescritura
    
    gdf.to_file(filepath, driver="GeoJSON", encoding='utf-8')


def process_and_save(data, grouper, geo_df, filename_prefix, frac=0.05):
    # Sintetizar datos, eliminar columna 'timestamp' y cambiar la forma del DataFrame
    df = sintetizar_datos(data, [grouper], base=filename_prefix, frac=frac).drop('timestamp', axis=1).set_index(list(df.drop('valor', axis=1).columns)).unstack([0, 1])['valor']
    
    # Renombrar columnas y resetear índice
    df.columns, df = ['_'.join(col) for col in df.columns.values], df.reset_index()
    
    # Fusionar con el GeoDataFrame para formar el gdf final
    gdf = gpd.GeoDataFrame(df.merge(geo_df), crs=geo_df.crs)
    
    # Guardar el gdf como GeoJSON
    filename = f'pobreza_{filename_prefix}_{grouper}.geojson'
    gdf.to_file(filename, driver='GeoJSON')
    
    # Mostrar columnas y sus dtypes
    print(filename, gdf.dtypes)
