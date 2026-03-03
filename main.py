import flet as ft
import sqlite3
import pandas as pd
import os
import shutil
import unicodedata
import webbrowser 
import urllib.parse
from datetime import datetime

# --- CONFIGURACIÓN DE COLORES CORPORATIVOS ---
COLOR_AZUL_CEVA = "#002060"
COLOR_ROJO_CEVA = "#C00000"
COLOR_VERDE_OK = "#28a745"
COLOR_FONDO = "#F5F7FA"

# --- MANEJO DE RUTAS PARA ANDROID / PC ---
def get_base_dir():
    # Detectamos si estamos en Android
    if os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_ROOT"):
        # En Android, usamos la carpeta interna de la app para asegurar permisos de escritura
        return os.path.expanduser("~")
    else:
        # En PC (Desarrollo), usamos la carpeta del script
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
DB_NAME = 'datos_logistica.db'
USUARIOS_NAME = 'Usuarios.xlsx'
REPORTE_NAME = 'Reporte_Escaneos.xlsx'

DB_PATH = os.path.join(BASE_DIR, DB_NAME)
USUARIOS_PATH = os.path.join(BASE_DIR, USUARIOS_NAME)
REPORTE_PATH = os.path.join(BASE_DIR, REPORTE_NAME)

def main(page: ft.Page):
    # --- CONFIGURACIÓN DE LA PÁGINA ---
    page.title = "CEVA Logistics - Control de Camiones"
    page.padding = 15
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = COLOR_FONDO
    page.scroll = ft.ScrollMode.ADAPTIVE

    # --- INICIALIZACIÓN DE ARCHIVOS (Solo en Android) ---
    def init_files():
        if os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_ROOT"):
            for fname in [DB_NAME, USUARIOS_NAME]:
                dest = os.path.join(BASE_DIR, fname)
                if not os.path.exists(dest):
                    # Intentamos varias rutas posibles donde Flet guarda assets en Android
                    posibles_origenes = [
                        os.path.join(os.getcwd(), "assets", fname),
                        os.path.join("assets", fname),
                        fname
                    ]
                    for src in posibles_origenes:
                        try:
                            if os.path.exists(src):
                                print(f"DEBUG: Archivo {fname} encontrado en {src}. Copiando...")
                                shutil.copy(src, dest)
                                break
                        except Exception as ex:
                            print(f"DEBUG: Error copiando {fname} desde {src}: {ex}")
        else:
            print("DEBUG: Entorno PC detectado.")

    init_files()

    # --- ESTADO GLOBAL DE LA APP ---
    class AppState:
        def __init__(self):
            self.usuario = ""
            self.modelo = ""
            self.box = ""
            self.reporte_id = ""
            self.piezas_teoricas = [] # [(BOX, Material, Medio)]
            self.piezas_escaneadas = [] # [Material]
            self.ruta_foto_box = None
            self.ruta_foto_lista = None

    state = AppState()

    # --- UTILIDADES ---
    def normalizar(t):
        if not t: return ""
        t = str(t).upper().strip()
        t = unicodedata.normalize('NFKD', t)
        return "".join([c for c in t if not unicodedata.combining(c)]).replace(" ", "")

    def guardar_en_excel(pieza, carro, resultado):
        now = datetime.now()
        data = {
            "Timestamp": [now.strftime("%Y-%m-%d %H:%M:%S")],
            "ID_Reporte": [state.reporte_id],
            "Usuario": [state.usuario],
            "Modelo": [state.modelo],
            "BOX": [state.box],
            "Pieza": [pieza],
            "Carro_Escaneado": [carro],
            "Resultado": [resultado]
        }
        df_nuevo = pd.DataFrame(data)
        try:
            if os.path.exists(REPORTE_PATH):
                df_old = pd.read_excel(REPORTE_PATH)
                df_final = pd.concat([df_old, df_nuevo], ignore_index=True)
                df_final.to_excel(REPORTE_PATH, index=False)
            else:
                df_nuevo.to_excel(REPORTE_PATH, index=False)
        except Exception as e:
            print(f"Error guardando Excel: {e}")

    # --- COMPONENTES GLOBALES ---
    # COMENTADO TEMPORALMENTE PARA DEPURAR PANTALLA ROJA
    # file_picker = ft.FilePicker()
    # page.overlay.append(file_picker)

    # --- PANTALLAS ---

    def show_login():
        page.clean()
        
        # Cargar datos para dropdowns
        usuarios = []
        try:
            if os.path.exists(USUARIOS_PATH):
                df = pd.read_excel(USUARIOS_PATH)
                usuarios = df.iloc[:, 0].dropna().unique().tolist()
        except: pass
        if not usuarios: usuarios = ["Cargando..."]

        modelos = []
        try:
            if os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                modelos = [r[0] for r in conn.execute("SELECT DISTINCT ModeloCamion FROM piezas").fetchall()]
                conn.close()
        except: pass
        if not modelos: modelos = ["Sin datos"]

        dd_user = ft.Dropdown(label="Usuario", options=[ft.dropdown.Option(u) for u in usuarios], width=300)
        dd_model = ft.Dropdown(label="Modelo", options=[ft.dropdown.Option(m) for m in modelos], width=300)

        def login_click(e):
            # Bypass para depuración: Si no hay selección, usamos valores por defecto
            u = dd_user.value if dd_user.value else "Usuario_Debug"
            m = dd_model.value if dd_model.value else "Modelo_Debug"
            
            print(f"DEBUG: Intento de login con {u} / {m}")
            state.usuario = u
            state.modelo = m
            show_setup()

        page.add(
            ft.Column([
                ft.Container(height=40),
                ft.Image(src="logo_ceva.png", width=180),
                ft.Container(height=20),
                ft.Image(src="foto_camiones.jpg", width=350, border_radius=10),
                ft.Container(height=20),
                ft.Text("Acceso al Sistema", size=24, weight="bold", color=COLOR_AZUL_CEVA),
                dd_user,
                dd_model,
                ft.ElevatedButton("INGRESAR", bgcolor=COLOR_AZUL_CEVA, color="white", width=250, height=50, on_click=login_click),
                ft.Container(height=20),
                ft.Image(src="logo_vw.png", width=60)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def show_setup():
        page.clean()
        txt_qr = ft.TextField(label="Escanee Semana (QR)", autofocus=True)
        txt_box = ft.TextField(label="BOX Detectado", read_only=True, bgcolor=ft.Colors.GREY_100)
        lbl_status = ft.Text("Esperando escaneo...", size=16, italic=True)
        btn_start = ft.ElevatedButton("COMENZAR VERIFICACIÓN", disabled=True, bgcolor=COLOR_ROJO_CEVA, color="white", width=300, height=60)

        def on_qr_change(e):
            val = txt_qr.value
            if len(val) >= 3:
                box = normalizar(val[:3])
                txt_box.value = box
                state.box = box
                # Consultar DB
                try:
                    conn = sqlite3.connect(DB_PATH)
                    res = conn.execute("SELECT Material, Medio FROM piezas WHERE ModeloCamion=? AND BOX=?", (state.modelo, box)).fetchall()
                    conn.close()
                    state.piezas_teoricas = res
                    if res:
                        lbl_status.value = f"Piezas encontradas: {len(res)}"
                        lbl_status.color = "green"
                        btn_start.disabled = False
                    else:
                        lbl_status.value = "⚠️ No se encontraron piezas para este BOX"
                        lbl_status.color = "orange"
                        btn_start.disabled = True
                except:
                    lbl_status.value = "Error al consultar Base de Datos"
                    lbl_status.color = "red"
            page.update()

        txt_qr.on_change = on_qr_change

        def pick_file(target):
            # def handle_result(e):
            #     if e.files:
            #         if target == "BOX": state.ruta_foto_box = e.files[0].path
            #         else: state.ruta_foto_lista = e.files[0].path
            #         page.snack_bar = ft.SnackBar(ft.Text(f"Foto {target} capturada"))
            #         page.snack_bar.open = True
            #         page.update()
            # file_picker.on_result = handle_result
            # file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
            page.snack_bar = ft.SnackBar(ft.Text("Módulo de cámara desactivado por depuración"))
            page.snack_bar.open = True
            page.update()

        btn_start.on_click = lambda _: [setattr(state, "reporte_id", f"REP-{datetime.now().strftime('%y%m%d%H%M')}"), show_validation()]

        page.add(
            ft.Column([
                ft.Text(f"Configuración - {state.modelo}", size=20, weight="bold", color=COLOR_AZUL_CEVA),
                txt_qr,
                txt_box,
                lbl_status,
                ft.Row([
                    ft.IconButton(ft.Icons.CAMERA_ALT, on_click=lambda _: pick_file("BOX"), tooltip="Foto BOX", icon_color=COLOR_AZUL_CEVA),
                    ft.Text("Foto BOX"),
                    ft.IconButton(ft.Icons.CAMERA_ALT, on_click=lambda _: pick_file("LISTA"), tooltip="Foto Lista", icon_color=COLOR_AZUL_CEVA),
                    ft.Text("Foto Lista"),
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=20),
                btn_start
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def show_validation():
        page.clean()
        
        txt_pieza = ft.TextField(label="Escanear Pieza", autofocus=True)
        txt_carro = ft.TextField(label="Escanear Carro", disabled=True)
        
        banner_msg = ft.Text("ESCANEE PIEZA", size=22, weight="bold", color="white")
        banner_container = ft.Container(
            content=banner_msg,
            padding=30,
            alignment=ft.Alignment(0,0),
            bgcolor=COLOR_AZUL_CEVA,
            border_radius=10,
            expand=True
        )

        expected_medio = {"val": ""}

        def process_pieza(e):
            p_in = normalizar(txt_pieza.value)
            if not p_in: return

            found_item = None
            for item in state.piezas_teoricas:
                if normalizar(item[0]) == p_in: # item[0] es Material en la consulta
                    found_item = item
                    break
            
            if found_item:
                expected_medio["val"] = str(item[1]) # item[1] es Medio
                banner_msg.value = f"COLOCAR EN:\n{expected_medio['val'].upper()}"
                banner_container.bgcolor = "green"
            else:
                expected_medio["val"] = "NO LISTADA"
                banner_msg.value = "PIEZA NO LISTADA"
                banner_container.bgcolor = "orange"
            
            txt_pieza.disabled = True
            txt_carro.disabled = False
            page.update()
            txt_carro.focus()

        def process_carro(e):
            c_in = normalizar(txt_carro.value)
            p_raw = txt_pieza.value.strip()
            
            # Comparación (Si no listada, cualquier carro sirve para confirmar)
            if expected_medio["val"] == "NO LISTADA" or normalizar(expected_medio["val"]) == c_in:
                res = "OK" if expected_medio["val"] != "NO LISTADA" else "NO LISTADA"
                state.piezas_escaneadas.append(p_raw)
                guardar_en_excel(p_raw, txt_carro.value, res)
                
                # Reset
                txt_pieza.value = ""
                txt_carro.value = ""
                txt_pieza.disabled = False
                txt_carro.disabled = True
                banner_container.bgcolor = COLOR_AZUL_CEVA
                banner_msg.value = "SIGUIENTE PIEZA"
                page.update()
                txt_pieza.focus()
            else:
                banner_container.bgcolor = "red"
                banner_msg.value = f"ERROR\nESPERADO: {expected_medio['val'].upper()}"
                txt_carro.value = ""
                # Sonido de error (opcional en web, automático en algunos lectores Android)
                page.update()
                txt_carro.focus()

        txt_pieza.on_submit = process_pieza
        txt_carro.on_submit = process_carro

        def clear_input(tf):
            tf.value = ""
            tf.disabled = False
            if tf == txt_pieza:
                txt_carro.disabled = True
                banner_container.bgcolor = COLOR_AZUL_CEVA
                banner_msg.value = "ESCANEE PIEZA"
            page.update()
            tf.focus()

        page.add(
            ft.Column([
                ft.Row([ft.Text(f"BOX: {state.box}", weight="bold"), ft.Spacer(), ft.Text(state.modelo)]),
                ft.Row([txt_pieza, ft.IconButton(ft.Icons.CLOSE, icon_color="red", on_click=lambda _: clear_input(txt_pieza))]),
                banner_container,
                ft.Row([txt_carro, ft.IconButton(ft.Icons.CLOSE, icon_color="red", on_click=lambda _: clear_input(txt_carro))]),
                ft.ElevatedButton("VER RESUMEN", icon=ft.Icons.LIST_ALT, width=200, on_click=lambda _: show_summary())
            ], expand=True)
        )

    def show_summary():
        page.clean()
        
        teoricas_set = set(normalizar(p[0]) for p in state.piezas_teoricas)
        escaneadas_set = set(normalizar(p) for p in state.piezas_escaneadas)
        faltantes = [p[0] for p in state.piezas_teoricas if normalizar(p[0]) not in escaneadas_set]

        def send_email(e):
            asunto = f"Reporte de Escaneo: BOX {state.box} - {state.modelo}"
            cuerpo = f"Usuario: {state.usuario}\nModelo: {state.modelo}\nBOX: {state.box}\n\n"
            cuerpo += f"Teoricas: {len(state.piezas_teoricas)}\n"
            cuerpo += f"Escaneadas: {len(state.piezas_escaneadas)}\n\n"
            cuerpo += f"FALTANTES:\n" + "\n".join(faltantes)
            
            mailto = f"mailto:?subject={urllib.parse.quote(asunto)}&body={urllib.parse.quote(cuerpo)}"
            webbrowser.open(mailto)

        page.add(
             ft.Column([
                ft.Text("Resumen de Verificación", size=24, weight="bold"),
                ft.Row([
                    ft.Column([ft.Text("Teóricas"), ft.Text(str(len(state.piezas_teoricas)), size=30, weight="bold", color=COLOR_AZUL_CEVA)]),
                    ft.Column([ft.Text("Escaneadas"), ft.Text(str(len(state.piezas_escaneadas)), size=30, weight="bold", color=COLOR_VERDE_OK)]),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ft.Divider(),
                ft.Text("PIEZAS FALTANTES", weight="bold", color="red"),
                ft.Container(
                    content=ft.Column([ft.Text(f) for f in faltantes], scroll=ft.ScrollMode.AUTO),
                    height=200, border=ft.border.all(1, ft.Colors.BLACK12), padding=10, border_radius=5
                ),
                ft.Row([
                    ft.ElevatedButton("ENVIAR CORREO", icon=ft.Icons.EMAIL, on_click=send_email),
                    ft.ElevatedButton("FINALIZAR OK", bgcolor=COLOR_VERDE_OK, color="white", on_click=lambda _: [guardar_en_excel("FIN", "FIN", "COMPLETO"), show_login()])
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    show_login()

# Ejecución
ft.app(target=main, assets_dir="assets")
