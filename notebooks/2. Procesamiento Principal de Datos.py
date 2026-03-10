# %% [markdown]
# 
# ---
# 
# ### **2. Procesamiento Principal de Datos.ipynb**
#   - **2.1. Iteración por año y trimestre:**
#     - **2.1.1.** Carga de datos de población sintética.
#     - **2.1.2.** Fusión de datos de población sintética con datos de ingresos.
#     - **2.1.3.** Guardado de resultados en directorios respectivos.
#     - **2.1.4.** Manejo de archivos faltantes con advertencias.

# %%
# import time
# time.sleep(1500)

# %%
import os
import pandas as pd
import numpy as np
from funciones import ajustar_empleo, run_predict_save, generate_Qs_from_year
from variables import *  # x_cols1, x_cols2, etc


# -------------------
# Parameters and Configuration
# -------------------

FRAC = 0.02
# START_YEAR = 2024
START_YEAR = 2024
END_YEAR = 2025

EXPERIMENT_TAG = 'ARG'
MODELS_TAG = 'ARG'
MODELS_PATH = './../../encuestador-de-hogares'
ADAPTED_CENSO_FILES_PATH = '/media/matias/Elements/suite/poblaciones'


# Ensure the results directory exists
if not os.path.exists('./../data/prediccion'):
    os.makedirs('./../data/prediccion')

RESULTS_PATH = '/media/matias/Elements/suite/out/'


# %%


# %% [markdown]
# ### Datos Empleo

# %%


## sspm	45	45.2		
# R/P3M	
#eph_continua_tasa_desempleo_total	Porcentaje	
# Tasa de desempleo total. En porcentaje.	Tasa de desempleo. Valores trimestrales	
# Subsecretaría de Programación Macroeconómica	
# https://infra.datos.gob.ar/catalog/sspm/dataset/45/distribution/45.2/download/tasa-desempleo-valores-trimestrales.csv	
# Principales variables ocupacionales. EPH continua. Desempleo	Instituto Nacional de Estadística y Censos (INDEC)	
# Principales variables ocupacionales. EPH continua. Desempleo	Tasa de desempleo por aglomerados urbanos	Empleo e Ingresos	
# 2003-01-01	

df = pd.read_csv('./../data/info/45.2_ECTDT.csv', index_col=0, parse_dates=True)
empleo = df[['45.2_ECTDT_0_T_33']]

empleo['censo2010_ratio'] = (empleo / empleo.loc['2010-11-15'])

desoc_C2010 = pd.read_csv('./../data/info/desoc_AGLOsi_C2010.csv').rename(columns = {'AGLO_si': 'AGLOSI'})
tasa_C2010 = desoc_C2010.loc[desoc_C2010.AGLOSI == True]['Tasa desocupacion'].values[0]


# %%
# pip install scikit-learn==1.0.2

# %%


# %% [markdown]
# ## Loop Prediccion and Save

# %%
import warnings
from sklearn.exceptions import InconsistentVersionWarning

# Suppress specific warning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)


# %%


all_Qs = []
for yr in range(START_YEAR, END_YEAR):
    all_Qs.extend(generate_Qs_from_year(yr))

for q in all_Qs:
    yr = q.split('-')[0]
    model_file = f'{MODELS_PATH}/modelos/clf4_{q[:10]}_{MODELS_TAG}' # model_file
    if not os.path.exists(model_file):
        print(f"Warning: Model file {model_file} for {q} not found. Skipping this quarter.")
        continue

    file_ = f'{ADAPTED_CENSO_FILES_PATH}/table_f{FRAC}_{yr}_{EXPERIMENT_TAG}.csv'
    if not os.path.exists(file_):
        # Add code to handle missing data file
        print(f"Warning: Data file {file_} for year {yr} not found. Skipping.")
        continue

    X_censo = pd.read_csv(file_, usecols=x_cols1 + ['ID', 'AGLOMERADO', 'DPTO', 'HOGAR_REF_ID', 'PERSONA_REF_ID',
                                                    'RADIO_REF_ID', 'URP'], index_col=['ID']).fillna(0)
    CONDACT_cnts = X_censo.CONDACT.value_counts()
    X_q = X_censo.copy()
    X_q['Q'] = q
    X_q = ajustar_empleo(X_q, q, empleo, CONDACT_cnts, tasa_C2010)
    # ... continue with the rest of your code

    # Generate the filenames
    filenames = [f'{RESULTS_PATH}RFC{i}_{FRAC}_{q[:10]}_{EXPERIMENT_TAG}.csv' for i in range(1, 5)]

    ow = False  # overwrite previous results if needed            
    # Iteration 1
    predict_save_iter_dict1 = {'X_data': X_q, 'x_cols': x_cols1, 'y_cols': y_cols1, 'out_filename': filenames[0], 
                               'model_filename': f'{MODELS_PATH}/modelos/clf1_{yr}_{MODELS_TAG}', 'tag': f'clf1_{yr}_{MODELS_TAG}', 'overwrite': ow}
    result1 = run_predict_save(predict_save_iter_dict1)  ## ojo con el ow
    
    # Iteration 2
    predict_save_iter_dict2 = {'X_data': pd.concat([X_q, result1], axis=1), 'x_cols': x_cols2, 'y_cols': y_cols2, 'out_filename': filenames[1], 
                               'model_filename': f'{MODELS_PATH}/modelos/clf2_{yr}_{MODELS_TAG}', 'tag': f'clf2_{yr}_{MODELS_TAG}', 'overwrite': ow}
    result2 = run_predict_save(predict_save_iter_dict2)
    
    # Iteration 3
    predict_save_iter_dict3 = {'X_data': pd.concat([X_q, result1, result2], axis=1), 'x_cols': x_cols3, 'y_cols': y_cols3, 'out_filename': filenames[2], 
                               'model_filename': f'{MODELS_PATH}/modelos/clf3_{yr}_{MODELS_TAG}', 'tag': f'clf3_{yr}_{MODELS_TAG}', 'overwrite': ow}
    result3 = run_predict_save(predict_save_iter_dict3)
    
    # Iteration 4
    predict_save_iter_dict4 = {'X_data': pd.concat([X_q, result1, result2, result3], axis=1), 'x_cols': x_cols4, 'y_cols': columnas_pesos, 'out_filename': filenames[3], 
                               'model_filename': f'{MODELS_PATH}/modelos/clf4_{q[:10]}_{MODELS_TAG}', 'tag': f'clf4_{yr}_{MODELS_TAG}', 'overwrite': ow}
    result4 = run_predict_save(predict_save_iter_dict4)


# %%
# # Error: archivo del modelo /media/matias/Elements/suite/resultados/RFReg_0.005_2019-08-15_ARG.csv no existe. Calcular en notebook 02, o ignorar mensaje si el trimestre 2019-08-15 no tuvo EPH publicada por INDEC.values=
# print out column namesss

# %%
# /media/matias/Elements/suite/resultados/RFC1_0.01_2018-02-15_ARG.csv
# File saved at /media/matias/Elements/suite/resultados/RFC1_0.01_2018-02-15_ARG.csv
# /media/matias/Elements/suite/resultados/RFC2_0.01_2018-02-15_ARG.csv
# File saved at /media/matias/Elements/suite/resultados/RFC2_0.01_2018-02-15_ARG.csv
# /media/matias/Elements/suite/resultados/RFC3_0.01_2018-02-15_ARG.csv
# File saved at /media/matias/Elements/suite/resultados/RFC3_0.01_2018-02-15_ARG.csv
# /media/matias/Elements/suite/resultados/RFC4_0.01_2018-02-15_ARG.csv
# File saved at /media/matias/Elements/suite/resultados/RFC4_0.01_2018-02-15_ARG.csv
# 2018-05-15
# /media/matias/Elements/suite/resultados/RFC1_0.01_2018-05-15_ARG.csv

# %%


# %%


# %%


# %%


# %%



