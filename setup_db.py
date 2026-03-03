import pandas as pd
import sqlite3
import os

# CONFIGURACIÓN
ARCHIVO_EXCEL = 'Listados maestro EMBALAJES de camiones.xlsx'
NOMBRE_DB = 'datos_logistica.db'
HOJAS_A_IGNORAR = ['BASE', 'BOM', 'Hoja1', 'Hoja2', 'Validaciones', 'Listas']

def encontrar_fila_encabezados(df_raw):
    """
    Busca en las primeras 5 filas dónde están los títulos reales.
    Retorna el índice de la fila y una lista de columnas limpia.
    """
    for i in range(min(5, len(df_raw))):
        fila = df_raw.iloc[i].astype(str).str.upper().tolist()
        # Buscamos palabras clave que sabemos que existen
        texto_fila = " ".join(fila)
        if "MATERIALNUMBER" in texto_fila and "EMBALAJE" in texto_fila:
            return i
    return None

def normalizar_columnas(cols):
    """Limpia nombres de columnas (quita espacios y caracteres raros)"""
    nuevas_cols = []
    for c in cols:
        c = str(c).strip()
        nuevas_cols.append(c)
    return nuevas_cols

def crear_base_datos():
    print("--- INICIANDO MIGRACIÓN (MODO AUTO-DETECTAR FILAS) ---")
    
    conn = sqlite3.connect(NOMBRE_DB)
    
    try:
        print(f"Leyendo {ARCHIVO_EXCEL}...")
        # Leemos sin encabezado primero (header=None) para ver los datos crudos
        xls = pd.read_excel(ARCHIVO_EXCEL, sheet_name=None, header=None)
        
        df_total = pd.DataFrame()
        hojas_procesadas = 0
        
        for nombre_hoja, df_raw in xls.items():
            if nombre_hoja in HOJAS_A_IGNORAR:
                continue
            
            print(f"   Analizando hoja: {nombre_hoja}...")
            
            # 1. BUSCAR DÓNDE ESTÁN LOS TÍTULOS
            idx_header = encontrar_fila_encabezados(df_raw)
            
            if idx_header is None:
                print(f"      ⚠️ ALERTA: No se encontraron encabezados válidos en '{nombre_hoja}'. Se salta.")
                continue
            
            print(f"      ✅ Encabezados detectados en la fila {idx_header + 1}")
            
            # 2. RECONSTRUIR EL DATAFRAME USANDO LA FILA CORRECTA
            # Tomamos los datos desde la fila siguiente al header
            df_final = df_raw.iloc[idx_header + 1:].copy()
            # Asignamos los nombres de columnas correctos
            df_final.columns = normalizar_columnas(df_raw.iloc[idx_header])
            
            # 3. BUSCAR LA COLUMNA 'BOX' (EMBALAJE PROVEEDOR)
            col_box = None
            for col in df_final.columns:
                if "EMBALAJE" in col.upper() and "PROVEEDOR" in col.upper():
                    col_box = col
                    break
            
            if not col_box:
                print(f"      ❌ ERROR: Encabezados encontrados pero falta 'EMBALAJE Proveedor'.")
                continue

            # 4. RENOMBRAR Y LIMPIAR
            df_final = df_final.rename(columns={
                col_box: 'BOX',
                'Materialnumber': 'Material',
                'Medio de Abastecimiento': 'Medio'
            })
            
            # Seleccionamos solo columnas útiles para ahorrar espacio (Opcional)
            cols_a_guardar = ['BOX', 'Material', 'Medio']
            # Verificamos que existan todas antes de filtrar
            if all(col in df_final.columns for col in cols_a_guardar):
                df_final = df_final[cols_a_guardar]
            
            df_final['ModeloCamion'] = nombre_hoja.strip()
            
            # Acumulamos
            df_total = pd.concat([df_total, df_final], ignore_index=True)
            hojas_procesadas += 1

        # 5. GUARDAR
        if df_total.empty:
            print("\n❌ ERROR FATAL: No se pudieron extraer datos de ninguna hoja.")
        else:
            print("-" * 30)
            print(f"Guardando {len(df_total)} registros de {hojas_procesadas} modelos...")
            df_total.to_sql('piezas', conn, if_exists='replace', index=False)
            
            conn.execute("CREATE INDEX idx_modelo ON piezas (ModeloCamion)")
            conn.execute("CREATE INDEX idx_box ON piezas (BOX)")
            
            print(f"✅ ¡ÉXITO TOTAL! Base de datos lista.")
            print(f"   Archivo: {NOMBRE_DB}")

    except Exception as e:
        print(f"❌ ERROR DE EJECUCIÓN: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    crear_base_datos()