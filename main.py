import flet as ft
import pandas as pd
import sqlite3
import os
import shutil
from datetime import datetime
import requests

# --- CONFIGURACIÓN ---
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
    page.window_width = 400
    page.window_height = 800

    # --- SISTEMA DE LOGS ---
    class Logger:
        def log(self, text):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
    logger = Logger()

    # --- INICIALIZACIÓN DE ARCHIVOS ---
    def init_files():
        if not os.path.exists(BASE_DIR):
            os.makedirs(BASE_DIR, exist_ok=True)
            
        if os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_ROOT"):
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
                            break

    init_files()

    # --- LÓGICA DE DATOS ---
    def get_usuarios():
        try:
            if os.path.exists(USUARIOS_PATH):
                df = pd.read_excel(USUARIOS_PATH)
                return df.iloc[:, 0].dropna().tolist()
            return ["Admin", "Operador 1", "Operador 2"]
        except: return ["Error al cargar usuarios"]

    def get_modelos():
        try:
            if os.path.exists(MASTER_PATH):
                xl = pd.ExcelFile(MASTER_PATH)
                return [s for s in xl.sheet_names if s not in ["BOM", "Hoja1"]]
            return ["9.180 TBXSS1", "11.180 - TBETS1", "15190OD"]
        except: return ["Error al cargar modelos"]

    def load_manifest(modelo):
        try:
            if os.path.exists(MASTER_PATH):
                df = pd.read_excel(MASTER_PATH, sheet_name=modelo)
                piezas = []
                # Ajustamos mapeo a las imágenes enviadas
                # Columnas probables: 'Materialnumber', 'Medio de Abastecimiento', 'Módulo de abastecimiento', 'EMBALAJE PROVEEDOR'
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
            logger.log(f"Error cargando manifest: {e}")
            return []

    # --- PANTALLAS ---

    def show_login():
        page.clean()
        usuarios = get_usuarios()
        modelos = get_modelos()

        dd_user = ft.Dropdown(
            label="Seleccione su usuario",
            options=[ft.dropdown.Option(u) for u in usuarios],
            width=300,
            border_color=COLOR_AZUL_CEVA,
            prefix_icon=ft.icons.PERSON_OUTLINE
        )
        dd_model = ft.Dropdown(
            label="Modelo",
            options=[ft.dropdown.Option(m) for m in modelos],
            width=300,
            border_color=COLOR_AZUL_CEVA,
            prefix_icon=ft.icons.TRUCK_FIELD_OUTLINED
        )

        def login_click(e):
            if dd_user.value and dd_model.value:
                state.usuario = dd_user.value
                state.modelo = dd_model.value
                show_setup()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Por favor complete los datos"))
                page.snack_bar.open = True
                page.update()

        page.add(
            ft.Column([
                ft.Container(height=20),
                ft.Image(src="logo_ceva.png", width=150),
                ft.Image(src="foto_camiones.jpg", width=380, border_radius=10),
                ft.Container(height=10),
                ft.Image(src="logo_vw.png", width=100),
                ft.Text("Seleccione su usuario", weight="bold", color=COLOR_AZUL_CEVA, size=18),
                dd_user,
                ft.Container(height=10),
                dd_model,
                ft.Container(height=30),
                ft.ElevatedButton(
                    content=ft.Text("Ingresar", size=20, weight="bold", color="white"),
                    bgcolor=COLOR_AZUL_CEVA,
                    width=250,
                    height=60,
                    on_click=login_click,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def show_setup():
        page.clean()
        state.piezas_teoricas = load_manifest(state.modelo)
        
        txt_semana = ft.TextField(label="Semana (QR)", width=200, bgcolor="white", border_radius=5)
        txt_truck = ft.TextField(label="Truck (Cod. barras)", width=200, bgcolor="white", border_radius=5)
        txt_camion = ft.TextField(label="Nro de Camión", width=200, bgcolor="white", border_radius=5)
        txt_hu = ft.TextField(label="HU", width=200, bgcolor="white", border_radius=5)

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("EMBALAJ..")),
                ft.DataColumn(ft.Text("Material..")),
                ft.DataColumn(ft.Text("Medio de..")),
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(p[3]))),
                    ft.DataCell(ft.Text(str(p[0]))),
                    ft.DataCell(ft.Text(str(p[1]))),
                ]) for p in state.piezas_teoricas[:10]
            ],
            column_spacing=15,
            heading_row_color=ft.colors.with_opacity(0.1, COLOR_AZUL_CEVA),
            data_row_min_height=40,
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
                    bgcolor=COLOR_AZUL_CEVA,
                    padding=10,
                    width=400
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Text("Semana (QR)"), txt_semana], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Truck (Cod. barras)"), txt_truck], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Nro de Camion"), txt_camion], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text("EMBALAJE DE ORIGEN", weight="bold", size=14, color=COLOR_AZUL_CEVA),
                        ft.Row([ft.Text("HU"), txt_hu], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ]),
                    padding=15
                ),
                ft.Container(
                    content=ft.Column([table], scroll=ft.ScrollMode.ALWAYS),
                    height=200,
                    border=ft.border.all(1, ft.colors.BLACK12),
                    border_radius=5,
                    margin=5
                ),
                ft.Row([
                    ft.ElevatedButton("Foto BOX", icon=ft.icons.CAMERA_ALT, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5))),
                    ft.ElevatedButton("Foto Lista", icon=ft.icons.CAMERA_ALT, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5))),
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([
                    ft.Container(
                       content=ft.Column([
                           ft.Text("Cantidad de piezas a Verificar", color="white", size=10),
                           ft.Text(str(len(state.piezas_teoricas)), color="white", size=20, weight="bold")
                       ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                       bgcolor=COLOR_AZUL_CEVA,
                       padding=10,
                       border_radius=5,
                       width=150
                    ),
                    ft.ElevatedButton(
                        "Comenzar la verificación",
                        bgcolor="red",
                        color="white",
                        height=50,
                        width=200,
                        on_click=start_click,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5))
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ft.IconButton(ft.icons.HOME_OUTLINED, on_click=lambda _: show_login())
            ], spacing=5, scroll=ft.ScrollMode.AUTO)
        )

    def show_validation():
        page.clean()
        
        txt_pieza = ft.TextField(label="Pieza", width=250, autofocus=True)
        txt_medio = ft.TextField(label="Medio", width=250)
        
        banner_instruccion = ft.Container(
            content=ft.Text("ESCANEE PIEZA", color="white", weight="bold", size=18),
            bgcolor="gray",
            padding=15,
            width=380,
            alignment=ft.alignment.center,
            border_radius=5
        )

        def scan_pieza(e):
            codigo = txt_pieza.value
            match = next((p for p in state.piezas_teoricas if p[0] == codigo), None)
            if match:
                banner_instruccion.content.value = f"Colocar en: {match[1]}"
                banner_instruccion.bgcolor = "red"
                page.update()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Pieza no encontrada"))
                page.snack_bar.open = True
                page.update()

        page.add(
            ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Image(src="logo_ceva.png", width=100),
                        ft.Text(f"Tipo: {state.modelo}", color=COLOR_AZUL_CEVA, weight="bold")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=10, bgcolor="white"
                ),
                ft.Container(content=ft.Text("Verificador de piezas", color="white", weight="bold"), bgcolor=COLOR_AZUL_CEVA, width=400, padding=10),
                ft.Container(height=10),
                ft.Row([txt_pieza, ft.ElevatedButton("LEER", on_click=scan_pieza, bgcolor=COLOR_AZUL_CEVA, color="white")], alignment=ft.MainAxisAlignment.CENTER),
                ft.ElevatedButton("+ Fotos", color="white", bgcolor="red", width=150),
                ft.Text("Instrucción de colocado:", weight="bold", color=COLOR_AZUL_CEVA),
                banner_instruccion,
                ft.Row([txt_medio, ft.ElevatedButton("LEER", bgcolor=COLOR_AZUL_CEVA, color="white")], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([ft.Text("Resultado:"), ft.Icon(ft.icons.CHECK_CIRCLE, color="green")], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=20),
                ft.ElevatedButton(
                    "Resumen de lo escaneado",
                    bgcolor=COLOR_AZUL_CEVA,
                    color="white",
                    width=350,
                    height=50,
                    on_click=lambda _: show_summary(),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5))
                ),
                ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: show_setup())
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def show_summary():
        page.clean()
        total_t = len(state.piezas_teoricas)
        
        page.add(
            ft.Column([
                ft.Container(height=20),
                ft.Image(src="logo_ceva.png", width=150),
                ft.Container(height=30),
                ft.Row([ft.Text("Piezas Teóricas", size=22, weight="bold"), ft.Container(ft.Text(str(total_t), color="white", size=20, weight="bold"), bgcolor=COLOR_AZUL_CEVA, padding=15, border_radius=5)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([ft.Text("Piezas Escaneadas", size=22, weight="bold"), ft.Container(ft.Text("0", color="white", size=20, weight="bold"), bgcolor=COLOR_AZUL_CEVA, padding=15, border_radius=5)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=20),
                ft.Text("RESULTADO", weight="bold", size=28, color=COLOR_AZUL_CEVA),
                ft.Container(height=150),
                ft.Text(f"Hora de Finalización: {datetime.now().strftime('%d %B %Y %H:%M')}", size=14),
                ft.Row([
                    ft.ElevatedButton("Enviar Correo", icon=ft.icons.EMAIL, width=160, height=50),
                    ft.ElevatedButton("VERIFICAR OK", bgcolor=COLOR_AZUL_CEVA, color="white", width=160, height=50)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: show_validation())
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, padding=20)
        )

    show_login()

ft.app(target=main, assets_dir="assets")
