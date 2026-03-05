import flet as ft
import sqlite3
import os
import shutil
from datetime import datetime
import requests

# --- CONFIGURACIÓN ---
# Update: Fix blank boot (Build #28)
DB_NAME = "datos_logistica.db"
USUARIOS_NAME = "Usuarios.xlsx"
MASTER_NAME = "Listados maestro EMBALAJES de camiones.xlsx"
COLOR_AZUL_CEVA = "#002060"
COLOR_FONDO = "#F5F5F5"

def get_base_dir():
    if os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_ROOT"):
        p = os.environ.get("FILES_DIR", os.getcwd())
        if p == "/" or p == "/data":
             return "/data/user/0/com.ceva.logistics/files"
        return p
    return os.path.dirname(os.path.abspath(__file__))

# --- ESTADO GLOBAL ---
class AppState:
    def __init__(self):
        self.usuario = ""
        self.modelo = ""
        self.truck = ""
        self.nro_camion = ""
        self.hu = ""
        self.reporte_id = ""
        self.piezas_teoricas = []
        self.escaneos_ok = []
        self.escaneos_error = []

state = AppState()

def main(page: ft.Page):
    # Importar panda dentro de main para evitar cuelgues al bootear en Android
    try:
        import pandas as pd
    except Exception as e:
        page.add(ft.Text(f"CRITICAL ERROR IMPORTING PANDAS: {e}"))
        page.update()
        return

    page.title = "CEVA Flow"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = COLOR_FONDO

    BASE_DIR = get_base_dir()
    USUARIOS_PATH = os.path.join(BASE_DIR, USUARIOS_NAME)
    MASTER_PATH = os.path.join(BASE_DIR, MASTER_NAME)

    # --- SISTEMA DE LOGS VISUALES ---
    class Logger:
        def __init__(self):
            self.control = ft.ListView(expand=True, spacing=2)
            self.ui = ft.Container(
                content=ft.Column([
                    ft.Text("DEBUG CONSOLE (V28)", size=10, weight="bold", color="white"),
                    self.control
                ]),
                bgcolor="#333333", padding=10, height=120, border_radius=5, margin=5
            )
        def log(self, text):
            msg = f"[{datetime.now().strftime('%H:%M:%S')}] {text}"
            self.control.controls.append(ft.Text(msg, size=10, color="white", font_family="monospace"))
            page.update()
    
    logger = Logger()

    def init_files():
        try:
            logger.log(f"Base: {BASE_DIR}")
            if not os.path.exists(BASE_DIR):
                os.makedirs(BASE_DIR, exist_ok=True)
            
            if os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_ROOT"):
                for fname in [DB_NAME, USUARIOS_NAME, MASTER_NAME]:
                    dest = os.path.join(BASE_DIR, fname)
                    if not os.path.exists(dest):
                        for src in [os.path.join(os.getcwd(), "assets", fname), os.path.join("/app/assets", fname)]:
                            if os.path.exists(src):
                                shutil.copy(src, dest)
                                logger.log(f"Copiado {fname}")
                                break
        except Exception as e: logger.log(f"ERR init: {e}")

    def get_usuarios():
        try:
            if os.path.exists(USUARIOS_PATH):
                df = pd.read_excel(USUARIOS_PATH)
                return df.iloc[:, 0].dropna().tolist()
            return ["Admin", "Op 1", "Op 2"]
        except Exception as e: 
            logger.log(f"ERR usr: {e}")
            return ["Admin (Default)"]

    def get_modelos():
        try:
            if os.path.exists(MASTER_PATH):
                xl = pd.ExcelFile(MASTER_PATH)
                return [s for s in xl.sheet_names if s not in ["BOM", "Hoja1"]]
            return ["Truck 1", "Truck 2"]
        except Exception as e: 
            logger.log(f"ERR mod: {e}")
            return ["Mod 1 (Default)"]

    def load_manifest(modelo):
        try:
            df = pd.read_excel(MASTER_PATH, sheet_name=modelo)
            piezas = []
            for _, row in df.iterrows():
                mat = str(row.get('Materialnumber', ''))[:15]
                medio = str(row.get('Medio de Abastecimiento', ''))
                if mat and mat != 'nan' and mat != '':
                    piezas.append((mat, medio, "", ""))
            return piezas
        except Exception as e:
            logger.log(f"ERR manifest: {e}")
            return []

    def show_login():
        page.clean()
        page.add(logger.ui)
        logger.log("Cargando UI...")
        usuarios = get_usuarios()
        modelos = get_modelos()
        
        dd_user = ft.Dropdown(label="Usuario", options=[ft.dropdown.Option(u) for u in usuarios], width=300)
        dd_model = ft.Dropdown(label="Modelo", options=[ft.dropdown.Option(m) for m in modelos], width=300)

        def login_click(e):
            if dd_user.value and dd_model.value:
                state.usuario = dd_user.value
                state.modelo = dd_model.value
                show_setup()

        page.add(
            ft.Column([
                ft.Image(src="logo_ceva.png", width=120),
                ft.Image(src="foto_camiones.jpg", width=350, border_radius=10),
                ft.Text("Login", weight="bold", size=20),
                dd_user, dd_model,
                ft.ElevatedButton("Ingresar", bgcolor=COLOR_AZUL_CEVA, color="white", on_click=login_click, width=200)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def show_setup():
        page.clean()
        page.add(logger.ui)
        logger.log(f"Cargando {state.modelo}...")
        state.piezas_teoricas = load_manifest(state.modelo)
        
        # Campos solicitados
        txt_semana = ft.TextField(label="Semana (QR)", width=300, bgcolor="white")
        txt_truck = ft.TextField(label="Truck (Cod. barras)", width=300, bgcolor="white")
        txt_secuencia = ft.TextField(label="Nro de Secuencia/Camión", width=300, bgcolor="white")
        txt_hu = ft.TextField(label="HU", width=300, bgcolor="white")

        lbl_box_status = ft.Text("Box no cargado", color="red", size=12)

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("EMB")),
                ft.DataColumn(ft.Text("MAT")),
                ft.DataColumn(ft.Text("MEDIO")),
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(p[3]))),
                    ft.DataCell(ft.Text(str(p[0]))),
                    ft.DataCell(ft.Text(str(p[1]))),
                ]) for p in state.piezas_teoricas[:8]
            ],
            column_spacing=10,
            data_row_min_height=30,
        )

        def start_click(e):
            state.truck = txt_truck.value
            state.nro_camion = txt_secuencia.value
            state.hu = txt_hu.value
            show_validation()

        page.add(
            ft.Column([
                ft.Container(
                    content=ft.Text("DETALLE DE CARGA", color="white", weight="bold"),
                    bgcolor=COLOR_AZUL_CEVA, padding=10, width=page.width
                ),
                ft.Column([
                    txt_semana,
                    txt_truck,
                    txt_secuencia,
                ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                
                ft.Text("EMBALAJE DE ORIGEN", weight="bold", color=COLOR_AZUL_CEVA),
                ft.Row([ft.Text("HU:"), txt_hu], alignment=ft.MainAxisAlignment.CENTER),
                
                ft.Container(
                    content=ft.Column([table], scroll=ft.ScrollMode.ALWAYS),
                    height=180, border=ft.border.all(1, ft.colors.BLACK12), border_radius=5
                ),

                ft.Row([
                    ft.Column([
                        ft.ElevatedButton("Foto BOX", icon=ft.icons.CAMERA_ALT, on_click=lambda _: None),
                        lbl_box_status,
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.ElevatedButton("Foto Lista", icon=ft.icons.CAMERA_ALT),
                ], alignment=ft.MainAxisAlignment.CENTER),

                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text("Piezas Total", size=10, color="white"),
                            ft.Text(str(len(state.piezas_teoricas)), size=20, weight="bold", color="white")
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.ElevatedButton(
                            "Comenzar la verificación", bgcolor="red", color="white",
                            height=50, on_click=start_click
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                    bgcolor=COLOR_AZUL_CEVA, padding=10, border_radius=10
                ),
                ft.IconButton(ft.icons.HOME, on_click=lambda _: show_login())
            ], spacing=10, scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def show_validation():
        page.clean()
        page.add(logger.ui)
        page.add(ft.Text("Escaneo de piezas..."))
        page.add(ft.ElevatedButton("Fin", on_click=lambda _: show_summary()))

    def show_summary():
        page.clean()
        page.add(ft.Text("Resumen final"))
        page.add(ft.ElevatedButton("Volver", on_click=lambda _: show_login()))

    init_files()
    show_login()

ft.app(target=main, assets_dir="assets")
