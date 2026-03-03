import flet as ft
import sqlite3
import pandas as pd
import os
import shutil
import unicodedata
import subprocess
import webbrowser 
import urllib.parse
import requests # <--- LIBRERÍA DE DESCARGA
from datetime import datetime

# --- CONFIGURACIÓN ---
COLOR_AZUL_CEVA = "#002060"
COLOR_ROJO_CEVA = "#C00000"
COLOR_VERDE_OK = "#28a745"
COLOR_FONDO = "#FFFFFF"

# --- TU ENLACE DE GITHUB REAL ---
URL_DB_NUBE = "https://raw.githubusercontent.com/ginoceva/DB-Logistica-VW/main/datos_logistica.db"

# --- RUTAS MODIFICADAS PARA ANDROID Y PC ---
# Detectamos si estamos en un entorno Android
try:
    IS_ANDROID = os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_ROOT")
except:
    IS_ANDROID = False

if IS_ANDROID:
    # En Android, usamos la carpeta interna de usuario (writable)
    BASE_DIR = os.path.expanduser("~")
else:
    # En PC, usamos la carpeta del script actual
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Nombres de archivo (que ahora viven inicialmente en 'assets')
DB_NAME = 'datos_logistica.db'
USUARIOS_NAME = 'Usuarios.xlsx'
REPORTE_NAME = 'Reporte_Escaneos.xlsx'

# Rutas finales de trabajo
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
USUARIOS_PATH = os.path.join(BASE_DIR, USUARIOS_NAME)
REPORTE_PATH = os.path.join(BASE_DIR, REPORTE_NAME)

def main(page: ft.Page):
    # --- INICIALIZACIÓN DE ARCHIVOS (ANDROID) ---
    if IS_ANDROID:
        # Lista de archivos que deben copiarse desde assets a la carpeta de usuario
        files_to_copy = [DB_NAME, USUARIOS_NAME]
        
        for fname in files_to_copy:
            dest_path = os.path.join(BASE_DIR, fname)
            # Solo copiamos si no existe (para no borrar datos nuevos en reinicios)
            if not os.path.exists(dest_path):
                try:
                    # En el APK compilado, 'assets' está en la ruta relativa actual
                    src_path = os.path.join("assets", fname)
                    shutil.copy(src_path, dest_path)
                    print(f"Copiado inicial: {fname}")
                except Exception as e:
                    print(f"Error copiando {fname}: {e}")
                    # Si falla la copia local, intentamos crear vacíos o depender de la descarga nube

    # Configuración Inicial
    page.title = "CEVA Logistics"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 380
    page.window_height = 800
    page.bgcolor = COLOR_FONDO
    page.scroll = "adaptive"

    # --- ESTADO GLOBAL ---
    state = {
        "usuario": "",
        "modelo": "",
        "box_calculado": "",
        "semana_full": "",
        "nro_camion": "",
        "camion_patente": "",
        "piezas_teoricas": [],
        "piezas_escaneadas": [],
        "faltantes": [],
        "codigo_unico": "",
        "carro_esperado_actual": "",
        "carro_esperado_actual_norm": "",
        "carro_esperado_display": "",
        "ruta_foto_box": None,
        "ruta_foto_lista": None
    }

    # ==========================================
    # HERRAMIENTAS GLOBALES
    # ==========================================
    
    def on_dialog_result(e):
        if e.files:
            path = e.files[0].path
            if page.data == "BOX":
                state["ruta_foto_box"] = path
                page.snack_bar = ft.SnackBar(ft.Text("Foto BOX cargada"))
            elif page.data == "LISTA":
                state["ruta_foto_lista"] = path
                page.snack_bar = ft.SnackBar(ft.Text("Foto LISTA cargada"))
            
            page.snack_bar.open = True
            if page.route == "/listado":
                mostrar_listado()
            else:
                page.update()

    file_picker = ft.FilePicker()
    file_picker.on_result = on_dialog_result
    page.overlay.append(file_picker)
    page.data = "" 

    def limpiar_pantalla():
        page.clean()
        # No borramos el overlay para no romper el FilePicker

    # ==========================================
    # FUNCIONES AUXILIARES
    # ==========================================
    def normalizar_texto(texto):
        if not texto: return ""
        texto = str(texto).upper()
        texto = unicodedata.normalize('NFKD', texto)
        texto_sin_tildes = "".join([c for c in texto if not unicodedata.combining(c)])
        return texto_sin_tildes.replace(" ", "").strip()

    def guardar_registro_excel(datos):
        try:
            df_nuevo = pd.DataFrame([datos])
            if os.path.exists(REPORTE_PATH):
                df_existente = pd.read_excel(REPORTE_PATH)
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
                df_final.to_excel(REPORTE_PATH, index=False)
            else:
                df_nuevo.to_excel(REPORTE_PATH, index=False)
            print("✅ Registro guardado")
        except Exception as e:
            print(f"❌ Error Excel: {e}")

    def abrir_carpeta_reportes():
        if IS_ANDROID:
            page.snack_bar = ft.SnackBar(ft.Text(f"Reporte guardado en: {BASE_DIR}"))
            page.snack_bar.open = True
            page.update()
            return

        try:
            if os.name == 'nt': os.startfile(BASE_DIR)
            else: subprocess.call(['xdg-open', BASE_DIR])
        except: pass

    # --- FUNCIÓN DE ACTUALIZACIÓN (NUEVA) ---
    def descargar_actualizacion(btn_actualizar, progress_ring):
        try:
            # UI: Mostrar cargando
            btn_actualizar.visible = False
            progress_ring.visible = True
            page.update()

            print(f"Descargando desde: {URL_DB_NUBE}")
            response = requests.get(URL_DB_NUBE, timeout=10) # 10 seg timeout
            
            if response.status_code == 200:
                # Sobreescribir la base de datos local
                with open(DB_PATH, 'wb') as f:
                    f.write(response.content)
                
                page.snack_bar = ft.SnackBar(ft.Text("✅ DATOS ACTUALIZADOS CORRECTAMENTE"))
                page.snack_bar.bgcolor = "green"
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error al descargar: {response.status_code}"))
                page.snack_bar.bgcolor = "red"

        except Exception as e:
            page.snack_bar = ft.SnackBar(ft.Text(f"Error de conexión: {e}"))
            page.snack_bar.bgcolor = "red"
        
        # UI: Restaurar
        page.snack_bar.open = True
        btn_actualizar.visible = True
        progress_ring.visible = False
        
        # Recargar para ver cambios
        mostrar_login()

    # --- ENVÍO DE CORREO ---
    def generar_correo_manual(destinatario_final):
        try:
            hay_faltantes = len(state["faltantes"]) > 0
            titulo_estado = "CON FALTANTES" if hay_faltantes else "OK"
            
            asunto = f"Reporte {titulo_estado}: BOX {state['box_calculado']} - {state['modelo']}"
            
            cuerpo = f"""Hola,
            
Adjunto reporte de verificacion.

USUARIO: {state['usuario']}
MODELO: {state['modelo']}
BOX: {state['box_calculado']}
ESTADO: {titulo_estado}

FALTANTES: {', '.join(state['faltantes']) if hay_faltantes else 'Ninguno'}

(Por favor adjuntar Excel y Fotos manualmente desde la carpeta abierta)
            """
            
            asunto_cod = urllib.parse.quote(asunto)
            cuerpo_cod = urllib.parse.quote(cuerpo)
            mailto_link = f"mailto:{destinatario_final}?subject={asunto_cod}&body={cuerpo_cod}"
            
            webbrowser.open(mailto_link)
            abrir_carpeta_reportes()
            return True, "Se abrió el correo y la carpeta."

        except Exception as e:
            return False, f"Error: {e}"

    def obtener_usuarios():
        try:
            if not os.path.exists(USUARIOS_PATH): return ["Usuario Local"]
            df = pd.read_excel(USUARIOS_PATH, header=0)
            return df.iloc[:, 0].dropna().astype(str).tolist()
        except: return ["Usuario Local"]

    def obtener_modelos():
        try:
            if not os.path.exists(DB_PATH): return []
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT ModeloCamion FROM piezas ORDER BY ModeloCamion")
            res = [row[0] for row in cursor.fetchall()]
            conn.close()
            return res
        except: return []

    # ==========================================
    # 1. LOGIN
    # ==========================================
    def mostrar_login():
        limpiar_pantalla()
        page.route = "/login"
        
        img_logo = ft.Image(src="assets/logo_ceva.png", width=150, error_content=ft.Text("Logo"))
        img_camiones = ft.Image(src="assets/foto_camiones.jpg", width=400, height=180, fit="cover", error_content=ft.Container(bgcolor="grey", height=180))
        img_vw = ft.Image(src="assets/logo_vw.png", width=70, error_content=ft.Text("VW"))

        dd_usuario = ft.Dropdown(label="Usuario", options=[ft.dropdown.Option(u) for u in obtener_usuarios()], border_color=COLOR_AZUL_CEVA, width=300, value=state["usuario"])
        dd_modelo = ft.Dropdown(label="Modelo", options=[ft.dropdown.Option(m) for m in obtener_modelos()], border_color=COLOR_AZUL_CEVA, width=300, value=state["modelo"])

        def ir_listado(e):
            if not dd_usuario.value or not dd_modelo.value:
                page.snack_bar = ft.SnackBar(ft.Text("Complete los campos"))
                page.snack_bar.open = True
                page.update()
                return
            state["usuario"] = dd_usuario.value
            state["modelo"] = dd_modelo.value
            mostrar_listado()

        btn_ingresar = ft.ElevatedButton("Ingresar", bgcolor=COLOR_AZUL_CEVA, color="white", width=200, height=50, on_click=ir_listado)

        # BOTÓN ACTUALIZAR
        progress_ring = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False, color=COLOR_AZUL_CEVA)
        btn_actualizar = ft.TextButton(
            "🔄 ACTUALIZAR LISTADO DE PIEZAS", 
            icon_color=COLOR_AZUL_CEVA,
            on_click=lambda e: descargar_actualizacion(btn_actualizar, progress_ring)
        )

        page.add(ft.Column([
            ft.Container(content=img_logo, alignment=ft.Alignment(0,0), padding=10),
            img_camiones,
            ft.Container(content=img_vw, alignment=ft.Alignment(0,0), padding=10),
            ft.Text("Camiones y Buses", weight="bold", size=16, color=COLOR_AZUL_CEVA),
            dd_usuario, dd_modelo,
            ft.Container(height=20),
            btn_ingresar,
            ft.Divider(),
            ft.Container(
                content=ft.Column([
                    ft.Text("Gestión de Datos", size=12, color="grey"),
                    btn_actualizar,
                    progress_ring
                ], horizontal_alignment="center"),
                alignment=ft.Alignment(0,0)
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    # ==========================================
    # 2. LISTADO
    # ==========================================
    def mostrar_listado():
        limpiar_pantalla()
        page.route = "/listado"

        def tomar_foto_box(e):
            page.data = "BOX"
            file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)

        def tomar_foto_lista(e):
            page.data = "LISTA"
            file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)

        txt_semana = ft.TextField(label="Semana (QR)", height=45, text_size=14, autofocus=True, value=state["semana_full"])
        txt_truck = ft.TextField(label="Truck", height=45, text_size=14, value=state["camion_patente"])
        txt_nro = ft.TextField(label="Nro Camión", height=45, text_size=14, value=state["nro_camion"])
        txt_box_display = ft.TextField(label="BOX DETECTADO", read_only=True, bgcolor=ft.Colors.GREY_100, value=state["box_calculado"])
        
        color_borde_box = "green" if state["box_calculado"] else COLOR_AZUL_CEVA
        txt_box_display.border_color = color_borde_box

        cant_txt = "0"
        if state["piezas_teoricas"]:
            cant_txt = str(len(state["piezas_teoricas"]))
        
        lbl_cant = ft.Text(cant_txt, size=30, weight="bold", color="white")

        def check_box(e):
            if txt_semana.value and len(txt_semana.value) >= 3:
                box = normalizar_texto(txt_semana.value[:3]) 
                txt_box_display.value = box
                state["box_calculado"] = box
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    cur.execute("SELECT BOX, Material, Medio FROM piezas WHERE ModeloCamion = ? AND BOX = ?", (state["modelo"], box))
                    datos = cur.fetchall()
                    conn.close()
                    state["piezas_teoricas"] = datos
                    lbl_cant.value = str(len(datos))
                    txt_box_display.border_color = "green" if datos else "red"
                except: lbl_cant.value = "Err"
                page.update()

        txt_semana.on_change = check_box

        def ir_val(e):
            if not state["piezas_teoricas"]:
                page.snack_bar = ft.SnackBar(ft.Text("Box sin piezas o no cargado"))
                page.snack_bar.open = True
                page.update()
                return
            state["semana_full"] = txt_semana.value
            state["camion_patente"] = txt_truck.value
            state["nro_camion"] = txt_nro.value
            state["codigo_unico"] = f"BOX-{state['box_calculado']}-{datetime.now().strftime('%Y%m%d%H%M')}"
            mostrar_validacion()

        color_btn_box = COLOR_VERDE_OK if state["ruta_foto_box"] else "white"
        color_txt_box = "white" if state["ruta_foto_box"] else "black"
        color_btn_lista = COLOR_VERDE_OK if state["ruta_foto_lista"] else "white"
        color_txt_lista = "white" if state["ruta_foto_lista"] else "black"

        btn_fotos = ft.Row([
            ft.ElevatedButton("Foto BOX", icon="camera_alt", bgcolor=color_btn_box, color=color_txt_box, on_click=tomar_foto_box),
            ft.ElevatedButton("Foto Lista", icon="camera_alt", bgcolor=color_btn_lista, color=color_txt_lista, on_click=tomar_foto_lista)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        btn_go = ft.ElevatedButton("Comenzar verificación", bgcolor=COLOR_ROJO_CEVA, color="white", width=300, height=60, on_click=ir_val)

        page.add(ft.Container(padding=20, content=ft.Column([
            ft.Container(content=ft.Column([
                ft.Text("Tipo de Camión", color="white"),
                ft.Text(state["modelo"], color="white", weight="bold", size=18)
            ], horizontal_alignment="center"), bgcolor=COLOR_AZUL_CEVA, padding=10, alignment=ft.Alignment(0,0)),
            txt_semana, txt_box_display, txt_truck, txt_nro,
            ft.Divider(), 
            btn_fotos, 
            ft.Container(height=10),
            ft.Row([
                ft.Container(content=ft.Row([ft.Text("Piezas:", color="white"), lbl_cant]), bgcolor=COLOR_AZUL_CEVA, padding=10, border_radius=5),
                btn_go
            ], alignment="spaceBetween")
        ])))

    # ==========================================
    # 3. VALIDACIÓN
    # ==========================================
    def mostrar_validacion():
        limpiar_pantalla()
        page.route = "/validacion"

        txt_pieza = ft.TextField(label="Escanear Pieza", bgcolor="white", border_color=COLOR_AZUL_CEVA, expand=True, autofocus=True, text_size=16)
        btn_reset_pieza = ft.ElevatedButton("X", bgcolor="#C00000", color="white", width=50)

        lbl_destino = ft.Text("ESCANEAR PIEZA PARA COMENZAR", color="white", weight="bold", size=16, text_align="center")
        cont_destino = ft.Container(content=lbl_destino, bgcolor=COLOR_AZUL_CEVA, width=400, padding=15, alignment=ft.Alignment(0,0), border_radius=5)
        
        txt_carro = ft.TextField(label="Escanear QR de medio", bgcolor="white", border_color=COLOR_AZUL_CEVA, expand=True, text_size=16, disabled=True)
        btn_reset_carro = ft.ElevatedButton("X", bgcolor="#C00000", color="white", width=50)

        lbl_res = ft.Text("", weight="bold", size=18)

        def al_escanear_pieza(e):
            pieza_in = normalizar_texto(txt_pieza.value)
            if not pieza_in: return 

            found = False
            medio_esperado = "NO LISTADO"
            
            for p in state["piezas_teoricas"]:
                if normalizar_texto(p[1]) == pieza_in:
                    medio_esperado = str(p[2]).strip()
                    found = True
                    break
            
            if found:
                state["carro_esperado_actual_norm"] = normalizar_texto(medio_esperado)
                state["carro_esperado_display"] = medio_esperado.upper()
                lbl_destino.value = f"COLOCAR EN:\n{medio_esperado.upper()}"
                cont_destino.bgcolor = "green"
            else:
                state["carro_esperado_actual_norm"] = "NOLISTADO"
                lbl_destino.value = "⚠️ PIEZA NO LISTADA ⚠️"
                cont_destino.bgcolor = "orange"
                
            txt_carro.disabled = False
            txt_pieza.disabled = True 
            page.update()
            try: txt_carro.focus()
            except: pass

        def al_escanear_carro(e):
            carro_in = normalizar_texto(txt_carro.value)
            pieza_in = txt_pieza.value.strip().upper()
            
            esperado_norm = state.get("carro_esperado_actual_norm", "")
            esperado_display = state.get("carro_esperado_display", esperado_norm)
            
            resultado = ""
            
            if esperado_norm == "NOLISTADO":
                resultado = "NO LISTADO"
                state["faltantes"].append(pieza_in)
                lbl_res.value = "REGISTRADO: NO LISTADO"
                lbl_res.color = "orange"
            elif esperado_norm == carro_in:
                resultado = "OK"
                state["piezas_escaneadas"].append(pieza_in)
                lbl_res.value = "CORRECTO (OK)"
                lbl_res.color = "green"
            else:
                lbl_res.value = f"ERROR - ESPERADO: {esperado_display}"
                lbl_res.color = "red"
                txt_carro.value = "" 
                try: txt_carro.focus()
                except: pass
                page.update()
                return 

            guardar_registro_excel({
                "Timer": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "Fecha": datetime.now().strftime("%d/%m/%Y"),
                "Tipo de Camion": state["modelo"],
                "Medio de origen": state["box_calculado"],
                "Codigo escaneado": pieza_in,
                "Codigo de medio buscado": esperado_display,
                "codigo de medio escaneado": txt_carro.value,
                "Resultado": resultado,
                "Usuario": state["usuario"],
                "CodigoUnico": state["codigo_unico"]
            })

            txt_pieza.value = ""
            txt_carro.value = ""
            txt_pieza.disabled = False
            txt_carro.disabled = True 
            lbl_destino.value = "Escanear siguiente pieza"
            cont_destino.bgcolor = COLOR_AZUL_CEVA
            page.update()
            try: txt_pieza.focus()
            except: pass

        def reset_ciclo(e):
            txt_pieza.value = ""
            txt_carro.value = ""
            txt_pieza.disabled = False
            txt_carro.disabled = True
            lbl_destino.value = "Escanear Pieza para comenzar"
            cont_destino.bgcolor = COLOR_AZUL_CEVA
            lbl_res.value = ""
            page.update()
            try: txt_pieza.focus()
            except: pass

        def borrar_carro(e):
            txt_carro.value = ""
            try: txt_carro.focus()
            except: pass
            page.update()

        txt_pieza.on_submit = al_escanear_pieza
        txt_carro.on_submit = al_escanear_carro
        btn_reset_pieza.on_click = reset_ciclo
        btn_reset_carro.on_click = borrar_carro

        btn_resumen = ft.ElevatedButton("Resumen", bgcolor=COLOR_AZUL_CEVA, color="white", on_click=lambda e: mostrar_resumen())
        btn_back = ft.ElevatedButton("Volver", bgcolor="grey", color="white", on_click=lambda e: mostrar_listado())

        page.add(ft.Container(padding=20, content=ft.Column([
            ft.Container(content=ft.Column([
                ft.Text("Tipo de Camión", color="white"),
                ft.Text(state["modelo"], color="white", weight="bold", size=16),
                ft.Text(f"BOX: {state['box_calculado']}", color="white")
            ], horizontal_alignment="center"), bgcolor=COLOR_AZUL_CEVA, padding=10, alignment=ft.Alignment(0,0)),
            
            ft.Text("1. Escanear Pieza", color=COLOR_AZUL_CEVA, weight="bold"),
            ft.Row([txt_pieza, btn_reset_pieza], vertical_alignment="center"),
            ft.Container(height=10),
            cont_destino, 
            ft.Container(height=10),
            ft.Text("2. Escanear Carro", color=COLOR_AZUL_CEVA, weight="bold"),
            ft.Row([txt_carro, btn_reset_carro], vertical_alignment="center"),
            ft.Container(height=10),
            ft.Row([lbl_res], alignment="center"),
            ft.Divider(),
            ft.Row([btn_back, btn_resumen], alignment="spaceBetween")
        ], scroll="auto")))

    # ==========================================
    # 4. RESUMEN
    # ==========================================
    def mostrar_resumen():
        limpiar_pantalla()
        page.route = "/resumen"
        
        tot_teo = len(state["piezas_teoricas"])
        tot_esc = len(state["piezas_escaneadas"])
        
        teoricas_norm = [normalizar_texto(p[1]) for p in state["piezas_teoricas"]]
        escaneadas_norm = [normalizar_texto(p) for p in state["piezas_escaneadas"]]
        
        pendientes_mostrar = []
        for i, teo in enumerate(teoricas_norm):
            if teo not in escaneadas_norm:
                pendientes_mostrar.append(state["piezas_teoricas"][i][1])

        col_faltantes = ft.Column(scroll="auto", height=350)
        for f in pendientes_mostrar: col_faltantes.controls.append(ft.Text(f"Falta: {f}", size=14, color="red"))

        def limpiar_y_salir():
            state["box_calculado"] = ""
            state["semana_full"] = ""
            state["nro_camion"] = ""
            state["camion_patente"] = ""
            state["piezas_teoricas"] = []
            state["piezas_escaneadas"] = []
            state["faltantes"] = []
            state["ruta_foto_box"] = None
            state["ruta_foto_lista"] = None
            mostrar_listado()

        def enviar_mail_click(e):
            destinatario = "gino.vico@cevalogistics.com"
            ok, msg = generar_correo_manual(destinatario)
            page.snack_bar = ft.SnackBar(ft.Text(msg))
            page.snack_bar.open = True
            page.update()
            if ok:
                limpiar_y_salir()

        def cerrar_ok(e):
            guardar_registro_excel({
                "Timer": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "Resultado": "PROCESO FINALIZADO",
                "Usuario": state["usuario"],
                "CodigoUnico": state["codigo_unico"]
            })
            page.snack_bar = ft.SnackBar(ft.Text("Finalizado Correctamente"))
            page.snack_bar.open = True
            page.update()
            limpiar_y_salir()

        btn_enviar = ft.ElevatedButton("Preparar Correo", bgcolor="#4472C4", color="white", width=150, height=50, on_click=enviar_mail_click)
        btn_ok = ft.ElevatedButton("VERIFICAR OK", bgcolor=COLOR_AZUL_CEVA, color="white", width=150, height=50, on_click=cerrar_ok)
        btn_back = ft.ElevatedButton("Volver", on_click=lambda e: mostrar_validacion())

        page.add(ft.Container(padding=20, content=ft.Column([
            ft.Text(state["modelo"], size=20, weight="bold"),
            ft.Row([ft.Text("Teóricas:"), ft.Text(str(tot_teo), weight="bold")]),
            ft.Row([ft.Text("Escaneadas:"), ft.Text(str(tot_esc), weight="bold")]),
            ft.Divider(),
            ft.Text("FALTANTES:", weight="bold"),
            ft.Container(content=col_faltantes, border=ft.border.all(1, "grey"), border_radius=5, padding=5),
            ft.Divider(),
            ft.Row([btn_enviar, btn_ok], alignment="spaceBetween"),
            ft.Container(height=10),
            btn_back
        ])))

    mostrar_login()

ft.app(target=main, assets_dir="assets")