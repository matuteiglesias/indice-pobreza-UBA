# %% [markdown]
# 
# ## **Índice**
# 
# 1. **Configuración inicial**
# 2. **Carga de información accesoria**
#     - Regiones y Aglomerados
#     - Rankings de Region y Aglo
# 3. **Proceso de muestreo del censo**
# 
# ---
# 
# ## **1. Configuración inicial**
# 
# En esta sección, configuraremos el entorno y prepararemos los recursos necesarios para el proceso
# 

# %%
import os
import pandas as pd
import numpy as np
import time

# Si no existe el directorio, clonamos el repositorio
if not os.path.exists('./../../samplerCensoARG/'):
    !git clone https://github.com/matuteiglesias/samplerCensoARG.git ./../../


# %% [markdown]
# 
# ## **2. Carga de información accesoria**
# 
# ### **2.1 Regiones y Aglomerados**
# 
# Cargamos información sobre regiones y aglomerados que se utilizará más adelante en el proceso.
# 

# %%
# Cargamos la referencia de radios
radio_ref = pd.read_csv('./../data/info/radio_ref.csv')

# Cargamos información sobre los aglomerados
radio_AGLO = pd.read_csv('https://raw.githubusercontent.com/matuteiglesias/Aglomerados-EPH-INDEC/main/result/radios_aglo_EPH.csv')
radio_AGLO['radio'] = radio_AGLO.COD_2010.str.replace('XX', '99').astype(int)
radio_AGLO['AGLOMERADO'] = radio_AGLO.eph_codagl
radio_AGLO['NOMAGLO'] = radio_AGLO.eph_aglome

radio_ref = radio_ref.drop(['AGLOMERADO'], axis = 1).merge(radio_AGLO[['radio','AGLOMERADO', 'NOMAGLO']], how = 'left')
radio_ref['AGLOMERADO'] = radio_ref['AGLOMERADO'].fillna(0).astype(int)

# Cargamos el mapeo de departamentos a regiones
dpto_region = pd.read_csv('./../data/info/DPTO_PROV_Region.csv')
radio_ref = radio_ref.merge(dpto_region)


# %% [markdown]
# 
# 
# ### **2.2 Rankings de Region y Aglo**
# 
# Cargamos los rankings de las regiones y aglomerados.
# 
# 

# %%
AGLO_rk = pd.read_csv('./../../encuestador-de-hogares/data/info/AGLO_rk')
rk_table = AGLO_rk.set_index(['ANO4', 'AGLOMERADO']).unstack()
AGLO_rk_filled = rk_table.fillna(rk_table.mean()).stack().reset_index()
AGLO_rk = AGLO_rk_filled

Reg_rk = pd.read_csv('./../../encuestador-de-hogares/data/info/Reg_rk')
Reg_rk['Region'] = Reg_rk['region_']
Reg_rk = Reg_rk.drop('region_', axis=1)


# %% [markdown]
# 
# ## **3. Proceso de muestreo del censo**
# 
# En esta sección, realizamos un loop de muestreo del censo, extrayendo y transformando los datos, y luego guardando los resultados.
# 

# %%
# Importamos las funciones necesarias desde funciones.py
from funciones import log_message, transform_censo_data, generate_unique_ids

# Configuración inicial
frac = 0.05
startyr = 2022
endyr = 2024
n_digits = 9
possible_ids = np.arange(10**(n_digits - 1), 10**n_digits)

log_message("Script started.")

for yr in [str(s) for s in range(startyr, endyr)]:
    log_message(f"Processing year: {yr}")

    # Extracción de datos
    input = pd.read_csv(f'./../../samplerCensoARG/data/censo_samples/table_f{frac}_{yr}_ARG.csv')
    table = input.copy()
    table['ANO4'] = int(yr)
    
    # Transformación de datos
    table = transform_censo_data(table)
    
    # Agregar la región
    table = table.merge(dpto_region[['DPTO', 'Region']])
    
    # Generar IDs únicos
    table = generate_unique_ids(table, n_digits)
    
    # Agregar ranking de Region y Aglo
    table = table.merge(AGLO_rk[['AGLOMERADO', 'ANO4', 'AGLO_rk']]).merge(Reg_rk[['Region', 'ANO4', 'Reg_rk']])
    
    # Guardar los datos transformados
    directory = '/media/matias/Elements/suite/poblaciones'
    if not os.path.exists(directory):
        os.makedirs(directory)
    table.to_csv(f'{directory}/table_f{frac}_{yr}_ARG.csv', index=False)

log_message("Script completed.")


# %%



