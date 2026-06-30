import pandas as pd
import random

def generar_dataset_fine_tuning(oa_path, links_path, output_path):
    # 1. Cargar datasets
    df_oa = pd.read_csv(oa_path, sep=';', dtype={'ID_Objetivo': str})
    df_links = pd.read_csv(links_path, sep=';', dtype={
        'ID_Objetivo': str, 
        'ID_Objetivo_Prerrequisito': str
    })
    
    # 2. Limpieza de datos
    df_oa = df_oa[df_oa['ID_Objetivo'] != 'ID_Objetivo'].drop_duplicates()
    df_links = df_links[df_links['ID_Objetivo'] != 'ID_Objetivo'].drop_duplicates()
    
    dict_objetivos = pd.Series(df_oa.Objetivo.values, index=df_oa.ID_Objetivo).to_dict()
    
    # --- NUEVO: Extraer a qué Ramo pertenece cada RA ---
    # Asumimos que el ID tiene el formato "ING 1206_RA1" o "ING 1206 - RA1"
    # Ajusta esta función de split si tus IDs tienen otro separador en el CSV
    def extraer_ramo(id_string):
        if pd.isna(id_string): return "Desconocido"
        return str(id_string).replace('-', '_').split('_')[0].strip()

    df_oa['Ramo'] = df_oa['ID_Objetivo'].apply(extraer_ramo)
    
    # 3. Crear Dataframe de Positivos (Los que SÍ tienen link)
    positivos = df_links.copy()
    positivos['Texto_Objetivo'] = positivos['ID_Objetivo'].map(dict_objetivos)
    positivos['Texto_Prerrequisito'] = positivos['ID_Objetivo_Prerrequisito'].map(dict_objetivos)
    positivos = positivos.dropna(subset=['Texto_Objetivo', 'Texto_Prerrequisito'])
    
    # 4. Generar Muestras Negativas ("Ninguna") limitadas al contexto del Ramo
    positivos['Ramo_Act'] = positivos['ID_Objetivo'].apply(extraer_ramo)
    positivos['Ramo_Pre'] = positivos['ID_Objetivo_Prerrequisito'].apply(extraer_ramo)
    
    # Descubrir qué parejas de Ramos tienen relación de prerrequisito
    pares_ramos_validos = positivos[['Ramo_Act', 'Ramo_Pre']].drop_duplicates().values.tolist()
    
    # Set de links reales para filtrar rápido
    links_reales = set(zip(positivos['ID_Objetivo'], positivos['ID_Objetivo_Prerrequisito']))
    negativos_data = []
    
    for ramo_act, ramo_pre in pares_ramos_validos:
        # Obtener todos los RAs del Ramo Actual y del Ramo Prerrequisito
        ras_act = df_oa[df_oa['Ramo'] == ramo_act]['ID_Objetivo'].tolist()
        ras_pre = df_oa[df_oa['Ramo'] == ramo_pre]['ID_Objetivo'].tolist()
        
        # Producto cartesiano: Cruzar todos con todos
        for ra_a in ras_act:
            for ra_p in ras_pre:
                # Si este cruce específico NO está en el CSV original, es un negativo
                if (ra_a, ra_p) not in links_reales:
                    if ra_a in dict_objetivos and ra_p in dict_objetivos:
                        negativos_data.append({
                            'ID_Objetivo': ra_a,
                            'Texto_Objetivo': dict_objetivos[ra_a],
                            'ID_Objetivo_Prerrequisito': ra_p,
                            'Texto_Prerrequisito': dict_objetivos[ra_p],
                            'Importancia': 'Ninguna'  # <--- NUEVA CLASE PARA LA IA
                        })
                        
    negativos = pd.DataFrame(negativos_data)
    
    # BALANCEO DE DATOS: Limitamos los negativos para que sean exactamente 
    # la misma cantidad que los positivos, evitando que el modelo se vuelva pesimista.
    if len(negativos) > len(positivos):
        negativos = negativos.sample(n=len(positivos), random_state=42)

    # 5. Unir y mezclar
    df_final = pd.concat([positivos, negativos], ignore_index=True)
    df_final = df_final.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # 6. Guardar
    columnas_ordenadas = [
        'ID_Objetivo', 'Texto_Objetivo',
        'ID_Objetivo_Prerrequisito', 'Texto_Prerrequisito',
        'Importancia'
    ]
    df_final = df_final[columnas_ordenadas]
    df_final.to_csv(output_path, sep=';', index=False, encoding='utf-8')
    
    print(f"\n--- Reporte del Nuevo Dataset ---")
    print(f"Enlaces Positivos (Baja/Media/Alta): {len(positivos)}")
    print(f"Enlaces Negativos (Ninguna) inyectados: {len(negativos)}")
    print(f"Total filas preparadas: {len(df_final)}")
    print(f"Archivo guardado en: {output_path}\n")
    
    return df_final


if __name__ == "__main__":
    df_resultado = generar_dataset_fine_tuning(
        oa_path='OA.csv', 
        links_path='OA_links.csv', 
        output_path='dataset_entrenamiento_beto.csv'
    )