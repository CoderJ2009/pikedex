#Created by CoderJ2009. This software is intended to run on a Raspberry Pi 3 running Raspi OS Lite 32 bits.
import pygame
import random
from gpiozero import Button,PWMLED,LED
import time
import os
import threading
import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
from picamera2 import Picamera2
from adafruit_rgb_display import ili9341
import subprocess
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306  
from luma.core.render import canvas
from google import genai
from dotenv import load_dotenv 
load_dotenv()
#========DECLARACIONES===========
pygame.mixer.init(buffer=4096)

#OLED (Stats Wifi)
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)
prev_ssid = ""
#TFT (MAIN)
cs = digitalio.DigitalInOut(board.CE0)
dc = digitalio.DigitalInOut(board.D25)
rst = digitalio.DigitalInOut(board.D24)
spi = board.SPI()

display = ili9341.ILI9341(
    spi,
    cs=cs,
    dc=dc,
    rst=rst,
    rotation=90,
    baudrate=40000000 
)

led_audio = PWMLED(4)
led_rojo = LED(18)
led_amarillo = LED(15)
led_verde = LED(14)
#Imagenes
cursor_img = Image.open("sprites/cursor.png").convert("RGBA")
cursor_img = cursor_img.resize((24, 24)) 

fondo_menu = Image.open("sprites/bg_menu.png")
fondo_menu = fondo_menu.resize((320,240))
fondo_menu = fondo_menu.convert("RGB")
fondo_info = Image.open("sprites/bg_info.png")
fondo_info = fondo_info.resize((320,240))
fondo_info = fondo_info.convert("RGB")
fondo_img = Image.open("sprites/bg_img.png")
fondo_img = fondo_img.resize((320,240))
fondo_img = fondo_img.convert("RGB")
fondo_loading= Image.open("sprites/bg_loading.png")
fondo_loading = fondo_loading.resize((320,240))
fondo_loading = fondo_loading.convert("RGB")

#Fuentes
font_title  = ImageFont.truetype("fonts/PokemonGb-RAeo.ttf", 14)
font_text   = ImageFont.truetype("fonts/PokemonGb-RAeo.ttf", 11)
font_desc   = ImageFont.truetype("fonts/PokemonGb-RAeo.ttf", 14)
font_menu   = ImageFont.truetype("fonts/PokemonGb-RAeo.ttf", 16)
frame = fondo_loading.copy()
draw  = ImageDraw.Draw(frame)
display.image(frame)
#==========BOTONES===================
boton_down = Button(17,bounce_time=0.05)
boton_up = Button(27,bounce_time=0.05)
boton_right = Button(21,bounce_time=0.05)
boton_left = Button(20,bounce_time=0.05)
boton_buscar = Button(16,bounce_time=0.05)
boton_cancelar = Button(19,bounce_time=0.05)
boton_A = Button(13,bounce_time=0.05)
#==========VALORES Y DATOS===========
datos = []
with open("data/data.csv","r") as file:
    datos = file.readlines()

#============MENU====================
#Layout menu
MODE = "menu"
selected_index = 0
top_index = 0
VISIBLE_COUNT = 7
ITEM_HEIGHT = 30
MARGIN_TOP = 20
TEXT_X = 45
CURSOR_X = 14

names = []
for p in range(len(datos)):
    names.append(f"No{int(datos[p].split(";")[0]) :03d}:{datos[p].split(";")[1].upper()}")
#Render menu
def render_menu():
    led_rojo.on()
    led_amarillo.off()
    led_verde.off()
    frame = fondo_menu.copy()
    draw = ImageDraw.Draw(frame)

    visible_names = names[top_index: top_index + VISIBLE_COUNT]
    for row, text in enumerate(visible_names):
        y = MARGIN_TOP + row * ITEM_HEIGHT
        draw.text((TEXT_X, y), text, font=font_menu, fill=(0, 0, 0))
    
    curs_row = selected_index - top_index
    cursor_y = MARGIN_TOP + curs_row * ITEM_HEIGHT -4
    frame.paste(cursor_img, (CURSOR_X, cursor_y), mask=cursor_img.split()[3])

    display.image(frame)

#=============AUDIO==================
_reproduccion_id = 0
_reproduccion_lock = threading.Lock()

def _simular_senal_led(mi_id):
    """Varía el brillo del LED mientras el audio suena, simulando que es la
    representación física de la señal del altavoz. No analiza el audio real:
    solo cambia brillo y tiempos al azar para dar sensación de reactividad."""
    while pygame.mixer.music.get_busy():
        with _reproduccion_lock:
            if mi_id != _reproduccion_id:
                return  # ha empezado otra pista: esta hebra se retira
        led_audio.value = random.uniform(0.15, 1.0)
        time.sleep(random.uniform(0.04, 0.1))
    led_audio.off()
 
def play_audio(path):
    global _reproduccion_id
    pygame.mixer.music.stop()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
 
    with _reproduccion_lock:
        _reproduccion_id += 1
        mi_id = _reproduccion_id
    threading.Thread(target=_simular_senal_led, args=(mi_id,), daemon=True).start()

#========MODO IMAGEN=================
def show_image_main(path):
    img = Image.open(path).resize((240, 240)).convert("RGBA")
    frame = fondo_img.copy()
    x = (320 - 240) // 2
    y = (240 - 240) // 2
    frame.paste(img, (x, y), mask=img.split()[3])
    display.image(frame)

def render_image(playau = True):
    led_rojo.off()
    led_amarillo.on()
    led_verde.off()
    lista = datos[selected_index].split(";")
    show_image_main("data/"+lista[-2])
    if playau:
        play_audio("data/"+lista[-1].strip())


#===============MODO INFO============
def wrap_text(text, font, max_width, draw):
    """Divide el texto en líneas que caben en max_width píxeles."""
    words  = text.split()
    lines  = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        w = draw.textlength(test, font=font_menu)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

#Layout info 
SCREEN_W, SCREEN_H = 320, 240
IMG_X, IMG_Y   = 8,8          # esquina superior izquierda de la imagen
IMG_SIZE       = 96            # imagen cuadrada 96×96 px
INFO_X         = IMG_X + IMG_SIZE     # columna de textos
INFO_Y_START   = 10
INFO_LINE_H    = 18
DESC_BOX_H     = 100            # altura del cuadro de descripción
DESC_BOX_Y     = SCREEN_H - DESC_BOX_H  # pega al fondo
DESC_PAD       = 6             # padding interior del cuadro
DESC_LINE_H    = 14
#Render info
def render_info():
    led_rojo.off()
    led_amarillo.off()
    led_verde.on()
    frame = fondo_info.copy()
    draw  = ImageDraw.Draw(frame)

    linea = datos[selected_index].split(";")
    numero = int(linea[0])
    nombre = linea[1]
    tipo = linea[2]
    tipo2 = linea[3]
    altura = linea[4]
    peso = linea[5]
    texto = linea[6]
    path = linea[7]
    # ── imagen pequeña (96×96) ───────────────────────────────────────────────
    
    poke_img = (
        Image.open("data/" + path)
                .resize((IMG_SIZE, IMG_SIZE))
                .convert("RGBA")
    )
    frame.paste(poke_img, (0, 0), mask=poke_img.split()[3])
  
    # ── textos al lado de la imagen ──────────────────────────────────────────
    if tipo2 == "": 
        info_lines = [
       	    (f"No {numero :03d}",         font_title, (30, 30, 30)),
       	    (nombre.upper(),                  font_title, (10, 10, 80)),
            (f"Type:   {tipo}",       font_text,  (0, 0, 0)),
            (f"Ht:    {float(altura)/10} m",   font_text,  (0, 0, 0)),
            (f"Wt:   {float(peso)/10} kg",    font_text,  (0, 0, 0)),
         ]
    else:
        info_lines = [
       	    (f"No {numero :03d}",         font_title, (30, 30, 30)),
       	    (nombre.upper(),                  font_title, (10, 10, 80)),
            (f"Types:{tipo}/{tipo2}",       font_text,  (0, 0, 0)),
            (f"Ht:    {float(altura)/10} m",   font_text,  (0, 0, 0)),
            (f"Wt:   {float(peso)/10} kg",    font_text,  (0, 0, 0)),
         ]
    for i, (txt, fnt, color) in enumerate(info_lines):
        y = INFO_Y_START + i * INFO_LINE_H
        draw.text((INFO_X, y), txt, font=fnt, fill=color)

    # ── cuadro de descripción (ancho completo, 4 líneas, pegado abajo) ───────
    box_x1, box_y1 = 0, DESC_BOX_Y
    box_x2, box_y2 = SCREEN_W, SCREEN_H

    # fondo del cuadro semitransparente (overlay blanco)
    overlay = Image.new("RGBA", (SCREEN_W, DESC_BOX_H), (231, 222, 198, 255))
    frame.paste(
        overlay.convert("RGB"),
        (box_x1, box_y1),
        mask=overlay.split()[3]
    )

    # borde superior del cuadro
    draw.line([(box_x1, box_y1), (box_x2, box_y1)], fill=(80, 80, 80), width=2)

    # texto de descripción con word-wrap
    max_text_w = SCREEN_W - DESC_PAD * 2 +50
    lineas = wrap_text(texto, font_desc, max_text_w, draw)
    #lineas = lineas[:4]  # máximo 4 líneas visibles

    for i, linea in enumerate(lineas):
        ty = box_y1 + DESC_PAD + i * DESC_LINE_H
        
        draw.text((box_x1 + DESC_PAD , ty), linea, font=font_desc, fill=(20, 20, 20))

    display.image(frame)

#=========MODO BUSQUEDA=============
mode_init = ""
nombres_parsed = [i[6:] for i in names]
#PALETA
BG_COLOR       = (239, 232,  212)
KEY_COLOR      = (218,  209,  185)
KEY_SEL_COLOR  = (198, 181,  140)
KEY_TXT_NORMAL = (255, 255, 255)
KEY_TXT_SEL    = (30,  30,  30)
KEY_SPECIAL    = KEY_COLOR
KEY_SPE_SEL    = KEY_SEL_COLOR
BORDER_COLOR   = (20,  20,  20)
INPUT_BG       = (255, 255, 255)
INPUT_BORDER   = (40, 100,  40)
INPUT_TXT      = (10,  60,  10)

# TECLADO

KEYS = [
    [("A",0,1),("B",1,1),("C",2,1),("D",3,1),("E",4,1),("F",5,1),("G",6,1)],
    [("H",0,1),("I",1,1),("J",2,1),("K",3,1),("L",4,1),("M",5,1),("N",6,1)],
    [("O",0,1),("P",1,1),("Q",2,1),("R",3,1),("S",4,1),("T",5,1),("U",6,1)],
    [("V",0,1),("W",1,1),("X",2,1),("Y",3,1),("Z",4,1),("ERASE",5,2)]
]
ROWS = len(KEYS)

# Geometría
KEY_W   = 40    # ancho de 1 celda
KEY_H   = 30
KEY_PAD = 3
KB_X    = 8
KB_Y    = 85

INPUT_X   = 8
INPUT_Y   = 8
INPUT_W   = SCREEN_W - 16
INPUT_H   = 40
MAX_CHARS = 16

#ESTADO
cursor_row = 0
cursor_col = 0
input_text = ""
message = 0
_lock      = threading.Lock()

def current_key_entry():
    """Devuelve la tupla (label, col_start, span) de la tecla bajo el cursor."""
    row = KEYS[cursor_row]
    if cursor_col < len(row):
        return row[cursor_col]
    return None

def current_label():
    entry = current_key_entry()
    return entry[0] if entry else None

def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius,
                            fill=fill, outline=outline, width=width)

#Render info
def render_src():
    led_rojo.on()
    led_amarillo.on()
    led_verde.on()
    frame = Image.new("RGB", (SCREEN_W, SCREEN_H), BG_COLOR)
    draw  = ImageDraw.Draw(frame)

    #campo de texto
    draw_rounded_rect(draw,
                      (INPUT_X, INPUT_Y,
                       INPUT_X + INPUT_W, INPUT_Y + INPUT_H),
                      radius=6, fill=INPUT_BG,
                      outline=INPUT_BORDER, width=2)

    display_text = input_text + "_" 
    draw.text((INPUT_X + 8, INPUT_Y + 14), display_text,
              font=font_title, fill=INPUT_TXT)

    #etiqueta 
    draw.text((KB_X, KB_Y - 18), "SEARCH POKÉMON",
              font=font_text, fill=(0, 0, 0))

    #teclas 
    for r, row in enumerate(KEYS):
        for ci, (label, col_start, span) in enumerate(row):
            kx = KB_X + col_start * (KEY_W + KEY_PAD)
            ky = KB_Y + r * (KEY_H + KEY_PAD)
            kw = span * KEY_W + (span - 1) * KEY_PAD  # ancho real en px

            selected = (r == cursor_row and ci == cursor_col)
            special  = label == "ERASE"

            if selected:
                fill_c   = KEY_SPE_SEL if special else KEY_SEL_COLOR
                txt_c    = KEY_TXT_SEL
                border_c = BORDER_COLOR
            else:
                fill_c   = KEY_SPECIAL if special else KEY_COLOR
                txt_c    = KEY_TXT_NORMAL
                border_c = (0, 0, 0)

            draw_rounded_rect(draw,
                              (kx, ky, kx + kw - 1, ky + KEY_H - 1),
                              radius=4, fill=fill_c,
                              outline=border_c, width=1)

            tw = draw.textlength(label, font=font_text)
            tx = kx + (kw - tw) // 2
            ty = ky + (KEY_H - 12) // 2
            draw.text((tx, ty), label, font=font_text, fill=txt_c)
    display.image(frame)


#MOVIMIENTO

def move_cursor(dr, dc_):
    global cursor_row, cursor_col
    with _lock:
        if dc_ != 0:
            # Horizontal: circular dentro de la fila actual
            row_len = len(KEYS[cursor_row])
            cursor_col = (cursor_col + dc_) % row_len
        else:
            # Vertical: mantener columna lógica o acercar al borde
            new_r = (cursor_row + dr) % ROWS
            new_len = len(KEYS[new_r])
            cursor_col = min(cursor_col, new_len - 1)
            cursor_row = new_r
    render_src()


#SELECCIONAR LETRA (botón A)


def select_key():
    global input_text, message
    label = current_label()
    if label is None:
        return
    with _lock:
        if label == "ERASE":
            input_text = ""
        else:
            if len(input_text) < MAX_CHARS:
                input_text += label
            
    render_src()

#  ENVIAR TEXTO (botón ACEPTAR) 

def send_text():
    global message , MODE , input_text,selected_index,top_index
    # Puede llamarse con o sin _lock tomado; aquí lo tomamos si no está tomado
    if input_text.strip():
        message  = input_text.strip()
        if message in nombres_parsed:
            selected_index = nombres_parsed.index(message)
            top_index = selected_index - 6
        
    input_text = ""
    MODE = mode_init
    mode()



def btn_aceptar():
    with _lock:
        send_text()


#BORRAR ÚLTIMA LETRA (botón CANCELAR) 

def delete_last():
    global input_text , MODE
    with _lock:
        if input_text:
            input_text = input_text[:-1]
            
    render_src()

#==========================MODO CAMARA=====================================
# ── Cámara ───────────────────────────────────────────────────────────────
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (320, 240), "format": "BGR888"}
)
picam2.configure(config)

congelada       = False
frame_congelado = None
pausar_cam       = False

def congelar():
    global congelada, frame_congelado,MODE,selected_index,top_index, pausar_cam

    if frame_congelado is None:
        print("FRAME CONGELADO IS NONE")
        return

    if not congelada:
        pausar_cam = True       # ← detener el loop primero
        time.sleep(0.05)        # ← esperar a que el loop termine su frame actual
        congelada = True

        # Guardar imagen temporal
        frame_congelado.save("/tmp/imagen.jpg")
        print("Imagen guardada en /tmp/imagen.jpg")
        img = frame_congelado.copy()

        # 1. Pegar barra negra primero
        barra = Image.new("RGB", (320, 40), (0, 0, 0))
        img.paste(barra, (0, 200))

        # 2. Dibujar texto encima de la barra
        draw  = ImageDraw.Draw(img)
        if ssid == "DISCONNECTED":
	   
           texto = "NO CONNECTION"
           tw    = int(draw.textlength(texto, font=font_menu))
           tx    = (320 - tw) // 2
           draw.text((tx, 210), texto, font=font_menu, fill=(255, 0,0))
           display.image(img)
           time.sleep(2)
           MODE = "menu"
           congelada = False
           pausar_cam = False
           frame_congelado = None
           picam2.stop()
           render_menu()
           return
        


        texto = "BUSCANDO..."
        tw    = int(draw.textlength(texto, font=font_menu))
        tx    = (320 - tw) // 2
        draw.text((tx, 210), texto, font=font_menu, fill=(255, 255, 255))

        display.image(img)
        pokemon = identificar_pokemon("/tmp/imagen.jpg")
        if pokemon is None:
            MODE = "menu"
            congelada = False
            pausar_cam = False
            frame_congelado = None
            picam2.stop()
            render_menu()
            return
        
        print(pokemon)
        inlist = pokemon in nombres_parsed
        selected_index = nombres_parsed.index(pokemon) if inlist else selected_index
        if inlist:
            top_index = selected_index - 6 if selected_index > 6 else 1
            MODE = "image"
            congelada = False
            pausar_cam = False
            frame_congelado = None
            picam2.stop()
            render_image()
        else:
            MODE = "menu"
            congelada = False
            pausar_cam = False
            frame_congelado = None
            picam2.stop()
            render_menu()
    else:
        congelada = False

def identificar_pokemon(ruta_imagen,key_index=0):
    keys = [
        os.getenv("API_KEY_1"),
        os.getenv("API_KEY_2")
    ]
    for intento in range (len(keys)):
    # 1. Inicializar el cliente (toma la API key de la variable de entorno automáticamente)
        client = genai.Client(
            api_key=keys[key_index]
        )

    # 2. Abrir la imagen usando Pillow
        try:
            imagen = Image.open(ruta_imagen)
        except FileNotFoundError:
            print(f"Error: No se encontró la imagen en '{ruta_imagen}'")
            return

    # 3. Definir el prompt para la IA
        prompt = "¿Qué Pokémon es este? Dime SOLO su nombre en MAYUSCULAS. SI NO ES UN POKEMON, devuelve DITTO como respuesta"

        print("Analizando la imagen con Gemini...")
        print(key_index)
        try:
        # 4. Llamar al modelo (usamos gemini-2.5-flash que es rápido y excelente con imágenes)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[imagen, prompt]
            )
            return response.text
        except Exception as e:
            print(f"ERROR en API [{key_index}]: {type(e).__name__}-{e}")
            if key_index + 1 != len(keys):
                key_index +=1

    return None

   





#===============OLED===============
def get_network_id():
    result = subprocess.run(
        ["iwgetid", "-r"],
        capture_output=True, text=True, timeout=5
    )
    ssid = result.stdout.strip()
    return ssid if ssid else "DISCONNECTED"
#=======FUNCIONALIDAD BOTONES========
def up():
    global selected_index, top_index

    if MODE !="search" and MODE != "cam":
        if selected_index == 0: return
        
        selected_index -=1 
        if selected_index < top_index:
            top_index -= 1  # el cursor llegó al borde visible: scroll hacia arriba
    
    mode(-1,0)
    

def down():
    
    global selected_index, top_index
    if MODE !="search" and MODE!="cam":
        if selected_index ==len(names)-1 : return
        
        selected_index += 1 
        if selected_index - top_index >= VISIBLE_COUNT:
            top_index += 1  # el cursor llegó al borde visible: scroll hacia abajo
    mode(1,0)

def right():
    global MODE
    if MODE== "menu":
        MODE="image"
        render_image()
    elif MODE == "image":
        render_info()
        MODE = "info"
    elif MODE== "search":
        move_cursor( 0, 1)

def left():
    global MODE
    if MODE== "image":
        MODE="menu"
        render_menu()
    elif MODE == "info":
        MODE= "image"
        render_image(False)
    elif MODE== "search":
        move_cursor(0, -1)

def aceptar():
    global MODE
    if MODE=="info" or MODE=="image":
        play_audio("data/"+datos[selected_index].split(";")[-1].strip())
    elif MODE=="menu":
        MODE="image"
        render_image()
    elif MODE=="search":
        select_key()
    elif MODE == "cam":
        print("congelar")
        congelar()

def cancelar():
    global MODE , mode_init,frame_congelado,pausar_cam
    if MODE=="image" or MODE == "info":
        left()
    elif MODE=="search":
        delete_last()
    elif MODE == "menu":
        global congelada, frame_congelado
        congelada       = False
        frame_congelado = None
        mode_init = MODE
        led_verde.off()
        led_amarillo.off()
        led_rojo.off()
        MODE = "cam"
        frame = fondo_loading.copy()
        draw  = ImageDraw.Draw(frame)
        picam2.start()

def buscar():
    global MODE , mode_init
    if MODE != "search"and MODE!="cam":
        mode_init = MODE
        MODE="search"
        render_src()
    elif MODE!= "cam":
        btn_aceptar()
#======ASIGNACION BOTONES=============
boton_down.when_pressed = down
boton_up.when_pressed = up
boton_right.when_pressed = right
boton_left.when_pressed = left
boton_A.when_pressed = aceptar
boton_cancelar.when_pressed = cancelar
boton_buscar.when_pressed = buscar

#=============MODOS===================
def mode(src_1=0 , src_2=0):
    match MODE:
        case "menu":
            render_menu()
        case "image":
            render_image()
        case "info":
            render_info()
        case "search":
            move_cursor(src_1,src_2)
        case _ :
            print("MODO desconocido")

#===========EJECUCION=================
render_menu() #ARRANQUE
while True:
    try:
        if MODE=="cam":

            if not congelada and not pausar_cam:
                frame           = picam2.capture_array()
                img             = Image.fromarray(frame)
                frame_congelado = img.copy()
                display.image(img)
                time.sleep(0.02)
            else:
                led_rojo.on()
                led_amarillo.off()
                time.sleep(0.2)
                led_rojo.off()
                led_amarillo.on()
                time.sleep(0.1)
                led_amarillo.off()
                led_verde.on()
                time.sleep(0.2)
                led_verde.off()
                led_amarillo.on()
                time.sleep(0.1)
        ssid = get_network_id()
        if ssid != prev_ssid:
            with canvas(device) as draw:
                draw.text((0, 1), "Wi-Fi:",fill="white",font=font_title)

                if len(ssid) > 18:
                    ssid_ls = ssid.split("-") if "-" in ssid else ssid.split()
                    ssid_cut = ssid.removesuffix(ssid_ls[-1])
                    draw.text((0, 16),ssid_cut ,fill="white",font=ImageFont.load_default(14))
                    draw.text((0,30),ssid_ls[-1],fill="white",font=ImageFont.load_default(14))
                else:
                    draw.text((0, 16), ssid,fill="white",font=ImageFont.load_default(14))
            prev_ssid = ssid
    except KeyboardInterrupt:
        print("Cerrando programa limpiamente")
        led_audio.close()
        led_rojo.close()
        led_amarillo.close()
        led_verde.close()
        boton_down.close()
        boton_up.close()
        boton_right.close()
        boton_left.close()
        boton_buscar.close()
        boton_cancelar.close()
        boton_A.close()
        # Detener cámara si está activa
        try:
            picam2.stop()
        except:
            pass
        # Detener audio
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        break

