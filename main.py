import flet as ft
import pandas as pd
import sqlite3
import os
import shutil
from datetime import datetime
import requests

# --- CONFIGURACIÓN ---
# Update: Triggering license fix (Build #24)
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

BASE_DIR = get_base_dir()
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
USUARIOS_PATH = os.path.join(BASE_DIR, USUARIOS_NAME)
MASTER_PATH = os.path.join(BASE_DIR, MASTER_NAME)

# --- ESTADO GLOBAL ---
class AppState:
    def __init__(self):
        self.usuario = ""
        self.modelo = ""
        self.truck = ""
        self.nro_camion = ""
        self.hu = ""
        self.reporte_id = ""
        self.piezas_teoricas = [] # List of tuples (Material, Medio, Modulo, Embalaje)
        self.escaneos_ok = []
        self.escaneos_error = []
        self.ruta_foto_box = ""
        self.ruta_foto_lista = ""

state = AppState()

def main(page: ft.Page):
    page.title = "CEVA Flow"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = COLOR_FONDO

    # --- SISTEMA DE LOGS VISUALES ---
    class Logger:
        def __init__(self):
            self.lines = []
            self.control = ft.ListView(expand=True, spacing=2)
            self.ui = ft.Container(
                content=ft.Column([
                    ft.Text("DEBUG CONSOLE", size=10, weight="bold", color="white"),
                    self.control
                ]),
                bgcolor="#333333",
                padding=10,
                height=150,
                border_radius=5,
                margin=5,
                visible=True
            )
        def log(self, text):
            msg = f"[{datetime.now().strftime('%H:%M:%S')}] {text}"
            print(msg)
            self.control.controls.append(ft.Text(msg, size=10, color="white", font_family="monospace"))
            page.update()
    
    logger = Logger()

    # --- INICIALIZACIÓN DE ARCHIVOS ---
    def init_files():
        try:
            logger.log(f"Iniciando init. BASE_DIR: {BASE_DIR}")
            if not os.path.exists(BASE_DIR):
                os.makedirs(BASE_DIR, exist_ok=True)
                logger.log("Creado BASE_DIR")
                
            if os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_ROOT"):
                logger.log("Entorno Android")
                for fname in [DB_NAME, USUARIOS_NAME, MASTER_NAME]:
                    dest = os.path.join(BASE_DIR, fname)
                    if not os.path.exists(dest):
                        posibles = [
                            os.path.join(os.getcwd(), "assets", fname),
                            os.path.join(os.path.dirname(__file__), "assets", fname),
                            os.path.join("/app/assets", fname)
                        ]
                        for src in posibles:
                            if os.path.exists(src):
                                shutil.copy(src, dest)
                                logger.log(f"Copiado {fname}")
                                break
                    else:
                        logger.log(f"Existía {fname}")
        except Exception as e:
            logger.log(f"EXCEP init_files: {e}")

    # --- LÓGICA DE DATOS ---
    def get_usuarios():
        try:
            if os.path.exists(USUARIOS_PATH):
                logger.log(f"Cargando usuarios de {USUARIOS_PATH}")
                df = pd.read_excel(USUARIOS_PATH)
                return df.iloc[:, 0].dropna().tolist()
            logger.log("No existe Usuarios.xlsx, usando default")
            return ["Admin", "Operador 1", "Operador 2"]
        except Exception as e: 
            logger.log(f"ERR usuarios: {e}")
            return ["Admin (Error Excel)"]

    def get_modelos():
        try:
            if os.path.exists(MASTER_PATH):
                logger.log(f"Cargando modelos de {MASTER_PATH}")
                xl = pd.ExcelFile(MASTER_PATH)
                return [s for s in xl.sheet_names if s not in ["BOM", "Hoja1"]]
            logger.log("No existe Master Excel, usando default")
            return ["9.180 TBXSS1", "11.180 - TBETS1", "15190OD"]
        except Exception as e: 
            logger.log(f"ERR modelos: {e}")
            return ["Default (Error Excel)"]

    def load_manifest(modelo):
        try:
            if os.path.exists(MASTER_PATH):
                df = pd.read_excel(MASTER_PATH, sheet_name=modelo)
                piezas = []
                for _, row in df.iterrows():
                    mat = str(row.get('Materialnumber', ''))[:15]
                    medio = str(row.get('Medio de Abastecimiento', ''))
                    mod = str(row.get('Módulo de abastecimiento', ''))
                    emb = str(row.get('EMBALAJE PROVEEDOR', ''))
                    if mat and mat != 'nan' and mat != '':
                        piezas.append((mat, medio, mod, emb))
                return piezas
            return []
        except Exception as e:
            logger.log(f"Error manifest: {e}")
            return []

    # --- PANTALLAS ---

    def show_login():
        try:
            page.clean()
            page.add(logger.ui)
            
            logger.log("Cargando datos iniciales...")
            usuarios = get_usuarios()
            modelos = get_modelos()
            logger.log("Datos listos")

            dd_user = ft.Dropdown(
                label="Usuario",
                options=[ft.dropdown.Option(u) for u in usuarios],
                width=300, border_color=COLOR_AZUL_CEVA,
                prefix_icon=ft.icons.PERSON_OUTLINE
            )
            dd_model = ft.Dropdown(
                label="Modelo",
                options=[ft.dropdown.Option(m) for m in modelos],
                width=300, border_color=COLOR_AZUL_CEVA,
                prefix_icon=ft.icons.TRUCK_FIELD_OUTLINED
            )

            def login_click(e):
                if dd_user.value and dd_model.value:
                    state.usuario = dd_user.value
                    state.modelo = dd_model.value
                    show_setup()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("Complete los datos"))
                    page.snack_bar.open = True
                    page.update()

            page.add(
                ft.Column([
                    ft.Container(height=10),
                    ft.Image(src="logo_ceva.png", width=120),
                    ft.Image(src="foto_camiones.jpg", width=350, border_radius=10),
                    ft.Image(src="logo_vw.png", width=80),
                    ft.Text("Seleccione su usuario", weight="bold", color=COLOR_AZUL_CEVA, size=16),
                    dd_user,
                    ft.Container(height=5),
                    dd_model,
                    ft.Container(height=10),
                    ft.ElevatedButton(
                        content=ft.Text("Ingresar", size=18, weight="bold", color="white"),
                        bgcolor=COLOR_AZUL_CEVA,
                        width=250, height=50,
                        on_click=login_click,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO)
            )
        except Exception as ex:
            logger.log(f"CRASH show_login: {ex}")

    def show_setup():
        try:
            page.clean()
            page.add(logger.ui)
            logger.log(f"Cargando manifest para {state.modelo}...")
            state.piezas_teoricas = load_manifest(state.modelo)
            logger.log(f"Manifest: {len(state.piezas_teoricas)} piezas")
            
            txt_semana = ft.TextField(label="Semana (QR)", width=200, bgcolor="white", border_radius=5)
            txt_truck = ft.TextField(label="Truck (Cod. barras)", width=200, bgcolor="white", border_radius=5)
            txt_camion = ft.TextField(label="Nro de Camión", width=200, bgcolor="white", border_radius=5)
            txt_hu = ft.TextField(label="HU", width=200, bgcolor="white", border_radius=5)

            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("EMB")),
                    ft.DataColumn(ft.Text("MAT")),
                    ft.DataColumn(ft.Text("MEDIO")),
                ],
                rows=[
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(p[3])[:10])),
                        ft.DataCell(ft.Text(str(p[0])[:10])),
                        ft.DataCell(ft.Text(str(p[1])[:10])),
                    ]) for p in state.piezas_teoricas[:10]
                ],
                column_spacing=10,
                heading_row_color=ft.colors.with_opacity(0.1, COLOR_AZUL_CEVA),
                data_row_min_height=35,
            )

            def start_click(e):
                state.truck = txt_truck.value
                state.nro_camion = txt_camion.value
                state.hu = txt_hu.value
                state.reporte_id = f"REP-{datetime.now().strftime('%y%m%d%H%M')}"
                show_validation()

            page.add(
                ft.Column([
                    ft.Container(
                        content=ft.Text(f"Tipo de Camión: {state.modelo}", color="white", weight="bold"),
                        bgcolor=COLOR_AZUL_CEVA, padding=10, width=400
                    ),
                    ft.Column([
                        ft.Row([ft.Text("Semana (QR)"), txt_semana], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Truck (Cod. barras)"), txt_truck], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Nro de Camion"), txt_camion], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text("EMBALAJE DE ORIGEN", weight="bold", size=12, color=COLOR_AZUL_CEVA),
                        ft.Row([ft.Text("HU"), txt_hu], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=5),
                    ft.Container(
                        content=ft.Column([table], scroll=ft.ScrollMode.ALWAYS),
                        height=150, border=ft.border.all(1, ft.colors.BLACK12), border_radius=5
                    ),
                    ft.Row([
                        ft.ElevatedButton("Foto BOX", icon=ft.icons.CAMERA_ALT, height=40),
                        ft.ElevatedButton("Foto Lista", icon=ft.icons.CAMERA_ALT, height=40),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([
                        ft.Text(f"Total: {len(state.piezas_teoricas)}", weight="bold"),
                        ft.ElevatedButton(
                            "Comenzar", bgcolor="red", color="white",
                            height=45, width=150, on_click=start_click
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                    ft.IconButton(ft.icons.HOME_OUTLINED, on_click=lambda _: show_login())
                ], spacing=2, scroll=ft.ScrollMode.AUTO)
            )
        except Exception as ex:
            logger.log(f"CRASH show_setup: {ex}")

    def show_validation():
        try:
            page.clean()
            page.add(logger.ui)
            
            txt_pieza = ft.TextField(label="Pieza", width=200, autofocus=True)
            banner_instruccion = ft.Container(
                content=ft.Text("ESCANEE PIEZA", color="white", weight="bold", size=16),
                bgcolor="gray", padding=15, width=350, alignment=ft.alignment.center, border_radius=5
            )

            def scan_pieza(e):
                codigo = txt_pieza.value
                match = next((p for p in state.piezas_teoricas if p[0] == codigo), None)
                if match:
                    banner_instruccion.content.value = f"Colocar en: {match[1]}"
                    banner_instruccion.bgcolor = "red"
                    page.update()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("No encontrada"))
                    page.snack_bar.open = True
                    page.update()

            page.add(
                ft.Column([
                    ft.Row([ft.Image(src="logo_ceva.png", width=80), ft.Text(state.modelo, weight="bold")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(content=ft.Text("Verificador", color="white"), bgcolor=COLOR_AZUL_CEVA, width=350, padding=8),
                    ft.Row([txt_pieza, ft.ElevatedButton("LEER", on_click=scan_pieza)], alignment=ft.MainAxisAlignment.CENTER),
                    banner_instruccion,
                    ft.ElevatedButton("Finalizar", bgcolor=COLOR_AZUL_CEVA, color="white", width=300, on_click=lambda _: show_summary()),
                    ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: show_setup())
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
            )
        except Exception as ex:
            logger.log(f"CRASH show_validation: {ex}")

    def show_summary():
        try:
            page.clean()
            page.add(logger.ui)
            page.add(
                ft.Column([
                    ft.Image(src="logo_ceva.png", width=120),
                    ft.Text("Resumen Final", size=20, weight="bold"),
                    ft.Text(f"Piezas: {len(state.piezas_teoricas)}"),
                    ft.ElevatedButton("VERIFICAR OK", bgcolor=COLOR_AZUL_CEVA, color="white", width=200, on_click=lambda _: show_login()),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, padding=20)
            )
        except Exception as ex:
            logger.log(f"CRASH show_summary: {ex}")

    init_files()
ft.app(target=main, assets_dir="assets")
