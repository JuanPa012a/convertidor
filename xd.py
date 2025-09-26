import tkinter as tk
import threading
from tkinter import ttk, messagebox, filedialog
import yt_dlp
import os, json, sys
import subprocess
import shutil
from datetime import datetime
import rarfile
import tempfile
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('convertidor_errors.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ArchivoDescargado:
    """Clase para almacenar información de archivos descargados"""
    
    def __init__(self, nombre, formato, ubicacion, fecha_descarga=None):
        self.nombre = nombre
        self.formato = formato
        self.ubicacion = ubicacion
        self.fecha_descarga = fecha_descarga or datetime.now()
    
    def __str__(self):
        return f"{self.nombre} ({self.formato})"
    
    def ruta_completa(self):
        """Retorna la ruta completa del archivo"""
        return os.path.join(self.ubicacion, f"{self.nombre}.{self.formato}")
    
    def existe_archivo(self):
        """Verifica si el archivo existe en el sistema"""
        return os.path.exists(self.ruta_completa())
    
    def obtener_tamaño(self):
        """Retorna el tamaño del archivo en bytes"""
        if self.existe_archivo():
            return os.path.getsize(self.ruta_completa())
        return 0
    
    def obtener_fecha_creacion(self):
        """Retorna la fecha de creación del archivo"""
        if self.existe_archivo():
            return datetime.fromtimestamp(os.path.getctime(self.ruta_completa()))
        return None


# Lista interna con objetos ArchivoDescargado
archivos_descargados = []
# Lista para URLs ya descargadas (para evitar duplicados)

CONFIG_FILE = "config.json"
SIZE_TEXT = 14

def cargar_config():
    """Carga la configuración desde config.json, si existe. Si no existe, lo crea automáticamente."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Si no existe el archivo, crear configuración por defecto y guardarla
    config_default = {"carpeta_descargas": os.path.expanduser("~/Downloads"),
                      "font_size": SIZE_TEXT
                }
    guardar_config(config_default)
    return config_default

def guardar_config(config):
    """Guarda la configuración en config.json"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

config = cargar_config()


def seleccionar_carpeta():
    """Abre un diálogo para seleccionar carpeta de descargas."""
    carpeta = filedialog.askdirectory(title="Selecciona carpeta de descargas")
    if carpeta:
        config["carpeta_descargas"] = carpeta
        guardar_config(config)
        messagebox.showinfo("Carpeta seleccionada", f"Los archivos se guardarán en:\n{carpeta}")
        lbl_carpeta.config(text=f"Carpeta actual: {config['carpeta_descargas']}")
        cargar_archivos()
def descargar(url, formato):
    logger.info(f"Iniciando descarga: URL={url}, Formato={formato}")
    try:
        carpeta = config["carpeta_descargas"]  # siempre obtiene la última guardada
        
        # Verificar que la carpeta de descargas existe
        if not os.path.exists(carpeta):
            error_msg = f"La carpeta de descargas no existe: {carpeta}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
            download_btn.config(state='active')
            return
            
        if getattr(sys, 'frozen', False):  # Si está en .exe
            base_path = sys._MEIPASS
        else:  # Si está en Python normal
            base_path = os.path.abspath(".")

        try:
            rarfile.UNRAR_TOOL = os.path.join(base_path, "bin", "unrar.exe")  # Usa unrar.exe local
             
            # Ruta del .rar que contiene ffmpeg y otros
            rar_path = os.path.join(base_path, "bin", "bin.rar")
            # Ruta de descompresión
            ffmpeg_extract_path = os.path.join(tempfile.gettempdir(), "ffmpeg_bin")
            # Copiar SOLO bin.rar
            # Queremos que termine en ffmpeg_bin/bin/bin.rar
            rar_dest_dir = os.path.join(ffmpeg_extract_path, "bin")
            os.makedirs(rar_dest_dir, exist_ok=True)

            rar_dest = os.path.join(rar_dest_dir, "bin.rar")
            if not os.path.exists(rar_dest):
                shutil.copy2(rar_path, rar_dest)

            
            ffmpeg_path = os.path.join(ffmpeg_extract_path, "bin")
            
            # Verificar que ffmpeg.exe exista
            ffmpeg_exe = os.path.join(ffmpeg_path, "ffmpeg.exe")

            # Extraer solo si no existe
            if not os.path.exists(ffmpeg_exe):
                with rarfile.RarFile(rar_path) as rf:
                    logger.info(f"Archivos en el RAR: {rf.namelist()}")
                    rf.extractall(ffmpeg_extract_path)


            if not os.path.exists(ffmpeg_exe):
                messagebox.showerror("Error", f"No se encontró ffmpeg.exe en {ffmpeg_exe}")
                download_btn.config(state='active')
                return
                
        except rarfile.BadRarFile:
            error_msg = "El archivo bin.rar está corrupto o no se puede leer"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
            download_btn.config(state='active')
            return
        except FileNotFoundError as e:
            error_msg = f"No se encontró un archivo necesario: {e}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
            download_btn.config(state='active')
            return
        except Exception as e:
            error_msg = f"Error al configurar ffmpeg: {e}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
            download_btn.config(state='active')
            return

         # --- Detectar navegador principal (puedes cambiar "chrome" por "edge" o "firefox") ---
        navegador = "cookies.txt"

        # Opciones base
        opciones = {
            "outtmpl": os.path.join(carpeta, "%(title)s.%(ext)s"),
            "cookiefile": navegador,  # 👈 Usa cookies del navegador
            "ffmpeg_location": ffmpeg_path,
            "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    },
            "progress_hooks": [progreso_hook]
        }

        # Ajustar según formato
        if formato == "mp4":
            opciones.update({
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4"
            })
        else:  # mp3
            opciones.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            })

        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=True) 
                archivo_descargado = ydl.prepare_filename(info) 
                
                if formato == "mp3":
                    archivo_descargado = os.path.splitext(archivo_descargado)[0] + ".mp3"
                
                # Crear objeto ArchivoDescargado
                nombre_archivo = os.path.splitext(os.path.basename(archivo_descargado))[0]
                archivo_obj = ArchivoDescargado(
                    nombre=nombre_archivo,
                    formato=formato,
                    ubicacion=carpeta
                )
                
                messagebox.showinfo("Éxito", f"Descarga completa en {opciones['outtmpl']}")
                progress['value'] = 0
                agregar_archivo_descargado(archivo_obj)
                download_btn.config(state='active')
                url_entry.delete(0, tk.END)
                
        except yt_dlp.DownloadError as e:
            error_msg = f"Error al descargar el video: {e}"
            logger.error(f"DownloadError: {error_msg}")
            messagebox.showerror("Error de descarga", error_msg)
            download_btn.config(state='active')
            progress['value'] = 0
            label_progreso.config(text="❌ Error en la descarga")
            
        except yt_dlp.ExtractorError as e:
            error_msg = f"Error al extraer información del video: {e}"
            logger.error(f"ExtractorError: {error_msg}")
            messagebox.showerror("Error de extracción", error_msg)
            download_btn.config(state='active')
            progress['value'] = 0
            label_progreso.config(text="❌ Error al extraer información")
            
        except yt_dlp.PostProcessingError as e:
            error_msg = f"Error al procesar el archivo: {e}"
            logger.error(f"PostProcessingError: {error_msg}")
            messagebox.showerror("Error de procesamiento", error_msg)
            download_btn.config(state='active')
            progress['value'] = 0
            label_progreso.config(text="❌ Error al procesar archivo")
            
        except Exception as e:
            error_msg = f"Error inesperado durante la descarga: {e}"
            logger.error(f"Unexpected error: {error_msg}")
            messagebox.showerror("Error inesperado", error_msg)
            download_btn.config(state='active')
            progress['value'] = 0
            label_progreso.config(text="❌ Error inesperado")
            
    except Exception as e:
        error_msg = f"Error crítico en la aplicación: {e}"
        logger.critical(error_msg)
        messagebox.showerror("Error crítico", error_msg)
        download_btn.config(state='active')
        progress['value'] = 0
        label_progreso.config(text="❌ Error crítico")
    
def limpiar_url_youtube(url):
    # Parsear la URL
    parsed_url = urlparse(url)

    # Extraer los parámetros de la query
    query_params = parse_qs(parsed_url.query)

    # Mantener solo el parámetro 'v' (que indica el video)
    params_filtrados = {}
    if 'v' in query_params:
        params_filtrados['v'] = query_params['v']

    # Reconstruir la query limpia
    query_limpia = urlencode(params_filtrados, doseq=True)

    # Reconstruir la URL final sin los parámetros no deseados
    url_limpia = urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        query_limpia,
        parsed_url.fragment
    ))

    return url_limpia
def iniciar_descarga():
    logger.info("Función iniciar_descarga() llamada")
    try:
        url = limpiar_url_youtube(url_entry.get())
        print(url)
        formato = formato_var.get()
        
        if not url:
            logger.warning("URL vacía ingresada por el usuario")
            messagebox.showerror("Error", "Debes ingresar una URL")
            return

        # Validar formato de URL básico
        if not url.startswith(('http://', 'https://')):
            logger.warning(f"URL con formato inválido: {url}")
            messagebox.showerror("Error", "La URL debe comenzar con http:// o https://")
            return
            
        # Verificar que la URL no esté vacía después de limpiar
        if not url.strip():
            logger.warning("URL vacía después de limpiar")
            messagebox.showerror("Error", "La URL ingresada no es válida")
            return

        # if url in urls_descargadas:
        #     messagebox.showerror("Error", "Ya descargaste esa canción!")
        #     url_entry.delete(0, tk.END)
        #     return
        
        # Verificar que el botón no esté ya deshabilitado (evitar múltiples descargas)
        if download_btn['state'] == 'disabled':
            logger.warning("Intento de iniciar descarga mientras ya hay una en progreso")
            messagebox.showwarning("Advertencia", "Ya hay una descarga en progreso")
            return
            
        logger.info(f"Iniciando hilo de descarga para URL: {url}")
        download_btn.config(state='disabled')
        label_progreso.config(text="🔄 Iniciando descarga...")
        progress['value'] = 0
        
        hilo = threading.Thread(target=descargar, args=(url, formato), daemon=True)
        hilo.start()
        
    except Exception as e:
        error_msg = f"Error al iniciar la descarga: {e}"
        logger.error(error_msg)
        messagebox.showerror("Error", error_msg)
        download_btn.config(state='active')
        label_progreso.config(text="❌ Error al iniciar descarga")
def agregar_archivo(archivo_obj):
    """Agrega archivo descargado al Listbox usando objeto ArchivoDescargado"""
    # Verificar si ya existe un archivo con el mismo nombre y formato
    existe = any(a.nombre == archivo_obj.nombre and a.formato == archivo_obj.formato 
                for a in archivos_descargados)
    
    if not existe:
        archivos_descargados.append(archivo_obj)
        lista.insert(tk.END, str(archivo_obj))  # muestra nombre y formato en la UI

def agregar_archivo_descargado(archivo_obj):
    """Agrega archivo descargado al Listbox usando objeto ArchivoDescargado"""
    # Verificar si ya existe un archivo con el mismo nombre y formato
    existe = any(a.nombre == archivo_obj.nombre and a.formato == archivo_obj.formato 
                for a in archivos_descargados)
    
    if not existe:
        archivos_descargados.insert(0,archivo_obj)
        lista.insert(0, str(archivo_obj))  # muestra nombre y formato en la UI

def cargar_archivos():
    """Carga los archivos de la carpeta de descargas en la lista, ordenados por fecha de creación (más reciente primero)"""
    archivos_descargados.clear()
   # Limpiar también las URLs
    lista.delete(0, tk.END)  # limpia lista anterior
    
    if not os.path.exists(config["carpeta_descargas"] ):
        messagebox.showerror("Error", f"No existe la carpeta: {config['carpeta_descargas']}")
        return
    
    # Lista para almacenar objetos ArchivoDescargado con su información de fecha
    archivos_con_fecha = []
    
    for archivo in os.listdir(config["carpeta_descargas"] ):
        ruta_completa = os.path.join(config["carpeta_descargas"] , archivo)
        if os.path.isfile(ruta_completa) and archivo.lower().endswith((".mp3", ".mp4")):  # solo archivos, no carpetas
            # Extraer nombre y formato del archivo
            nombre_archivo = os.path.splitext(archivo)[0]
            formato_archivo = os.path.splitext(archivo)[1][1:].lower()  # quita el punto
            
            # Crear objeto ArchivoDescargado
            archivo_obj = ArchivoDescargado(
                nombre=nombre_archivo,
                formato=formato_archivo,
                ubicacion=config["carpeta_descargas"]
            )
            
            # Obtener la fecha de creación del archivo
            fecha_creacion = os.path.getctime(ruta_completa)
            archivos_con_fecha.append((archivo_obj, fecha_creacion))
    
    # Ordenar por fecha de creación (más reciente primero)
    archivos_con_fecha.sort(key=lambda x: x[1], reverse=True)
    label_size.config(text= f"Cantidad de archivos: {len(archivos_con_fecha)}")
    
    # Agregar archivos ordenados a la lista
    for archivo_obj, _ in archivos_con_fecha:
        agregar_archivo(archivo_obj)

def abrir_archivo(event):
    """Abre la ubicación del archivo con doble clic y lo selecciona en el explorador."""
    seleccion = lista.curselection()
    if not seleccion:
        return
    
    index = seleccion[0]
    archivo_obj = archivos_descargados[index]

    try:
        ruta_completa = os.path.normpath(archivo_obj.ruta_completa()) 

        # Verificar existencia
        if not archivo_obj.existe_archivo():
            messagebox.showerror("Error", f"El archivo no existe:\n{ruta_completa}")
            return

        # Intentar abrir con /select,
        subprocess.run(f'explorer /select,"{ruta_completa}"', shell=True)

    except subprocess.CalledProcessError:
        # Si falla, abrir solo la carpeta
        try:
            carpeta = os.path.dirname(ruta_completa)
            os.startfile(carpeta)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")

    except Exception as e:
        messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}")

def progreso_hook(d):
    try:
        if d['status'] == 'downloading':
            porcentaje = d.get('_percent_str', '0.0%')
            velocidad = d.get('_speed_str', '0.0KiB/s')
            eta = d.get('_eta_str', 'N/A')

            # Actualizar progressbar
            try:
                percent_float = float(d['_percent_str'].replace('%', '').strip())
                progress['value'] = percent_float
                root.update_idletasks()
            except (ValueError, KeyError, AttributeError) as e:
                # Si hay error al convertir el porcentaje, usar 0
                progress['value'] = 0
                print(f"Error al procesar porcentaje: {e}")

            # También podrías mostrar en consola o en la UI
            texto = f"{porcentaje} | {velocidad} | ETA: {eta}"
            label_progreso.config(text=texto)

        elif d['status'] == 'finished':
            progress['value'] = 100
            root.update_idletasks()
            label_progreso.config(text="✅ Descarga completa")
            
        elif d['status'] == 'error':
            # Manejar errores específicos del hook
            error_msg = d.get('error', 'Error desconocido en la descarga')
            label_progreso.config(text=f"❌ Error: {error_msg}")
            progress['value'] = 0
            download_btn.config(state='active')
            
    except KeyError as e:
        # Si falta alguna clave en el diccionario d
        error_msg = f"Error en progreso_hook - clave faltante: {e}"
        logger.warning(error_msg)
        print(error_msg)
        label_progreso.config(text="⚠️ Error en el progreso de descarga")
        
    except Exception as e:
        # Cualquier otro error en el hook
        error_msg = f"Error inesperado en progreso_hook: {e}"
        logger.error(error_msg)
        print(error_msg)
        label_progreso.config(text="⚠️ Error inesperado en el progreso")

def mostrar_menu(event):
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Copiar", command=lambda: copiar(url_entry))
    menu.add_command(label="Pegar", command=lambda: pegar(url_entry))
    menu.tk_popup(event.x_root, event.y_root)

def copiar(widget):
    try:
        seleccionado = widget.selection_get()
        root.clipboard_clear()
        root.clipboard_append(seleccionado)
    except tk.TclError:
        pass  # no hay texto seleccionado

def pegar(widget):
    try:
        texto = root.clipboard_get()
        widget.insert(tk.INSERT, texto)
    except tk.TclError:
        pass  # portapapeles vacío       


# --- UI ---
root = tk.Tk()
root.title("YouTube Downloader 🎧")
root.state('zoomed')
root.resizable(True, True)
label_progreso = tk.Label(root, text="Esperando descarga...", font=("Arial", SIZE_TEXT))
label_progreso.pack(pady=5, fill="both", expand= True)
progress = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress.pack(pady=10, fill= "both", expand= True)
# Título
title_label = tk.Label(root, text="Convertidor YouTube - DJ Alcapone (Romaña) - Alcanito (Pablito)", font=("Arial", SIZE_TEXT, "bold"))
title_label.pack(pady=10, fill= "both", expand= True)



# Entrada URL
frame_url = tk.Frame(root)
frame_url.pack(pady=5, fill= "both", expand= True)
tk.Label(frame_url, text="URL del video:", font=("Arial", config["font_size"])).pack(expand=True, padx=5)
url_entry = tk.Entry(frame_url, width=50, font=("Arial",config["font_size"]))
url_entry.pack(expand=True, pady=10)
url_entry.bind("<Button-3>", mostrar_menu)  # 👈 botón derecho en Windows/Linux
url_entry.bind("<Button-2>", mostrar_menu)

# Formatos
formato_var = tk.StringVar(value="mp3")
frame_format = tk.Frame(root)
frame_format.pack(pady=10)
tk.Label(frame_format, text="Formato:", font=("Arial", config["font_size"])).pack(side=tk.LEFT, padx=5)
ttk.Radiobutton(frame_format, text="MP3", variable=formato_var, value="mp3").pack(side=tk.LEFT, padx=5)
ttk.Radiobutton(frame_format, text="MP4", variable=formato_var, value="mp4").pack(side=tk.LEFT, padx=5)

# Botón descargar
download_btn = tk.Button(root, text="⬇ Descargar", font=("Arial", config["font_size"]), bg="#1DB954", fg="white", command=iniciar_descarga)
download_btn.pack(pady=20)

# Botón para cambiar carpeta
btn_carpeta = tk.Button(root, text="Cambiar carpeta de descargas", command=seleccionar_carpeta)
btn_carpeta.pack(pady=10)

# Etiqueta que muestra la carpeta actual
lbl_carpeta = tk.Label(root, text=f"Carpeta actual: {config['carpeta_descargas']}", wraplength=400, justify="left")
lbl_carpeta.pack(pady=5)

# Estado
status_label = tk.Label(root, text="Listo para descargar.", fg="gray")
status_label.pack(pady=5)


label_size = tk.Label(root, text= "Cantidad de archivos: ", font=("Arial", config["font_size"]))
label_size.pack(pady=5)

# Listbox para mostrar descargas
lista = tk.Listbox(root, width=400, height=12, font=("Arial", config["font_size"]))
lista.pack(pady=20)

# Vincular doble clic
lista.bind("<Double-1>", abrir_archivo)
cargar_archivos()


root.mainloop()