import json
import os
import requests
from flask import Flask, request
import telebot
from telebot import types

# --- TOKEN EXCLUSIVO DE LA TIENDA ---
TOKEN = '9087964567:AAFvgiOhYZeV_5oMjK7FQCtdTnPxQfntHHs'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- CONFIGURACIÓN DE ADMINISTRADORES ---
ADMINS_AUTORIZADOS = {
    6374498816: {"nombre": "Eudis", "clave": "1234"}
}

# Archivos locales para guardar datos de forma persistente
DATA_FILE = 'productos.json'
CLIENTES_FILE = 'clientes.json'

def cargar_datos(archivo, defecto):
  if os.path.exists(archivo):
    with open(archivo, 'r', encoding='utf-8') as f:
      return json.load(f)
  return defecto

def guardar_datos(archivo, datos):
  with open(archivo, 'w', encoding='utf-8') as f:
    json.dump(datos, f, ensure_ascii=False, indent=4)

sesiones_usuarios = {}

# --- FUNCIÓN PARA CONSULTAR LA TASA EN LÍNEA ---
def obtener_tasa_bcv():
  try:
    respuesta = requests.get("https://pydolarve.org/api/v1/dollar?monitor=bcv", timeout=5)
    if respuesta.status_code == 200:
      datos = respuesta.json()
      return float(datos.get("price", 36.5))
  except Exception as e:
    print(f"Error al consultar la tasa en línea: {e}")
  return 36.5

# --- TECLADO PRINCIPAL PARA CLIENTES ---
def mostrar_teclado_principal(chat_id):
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  btn_catalogo = types.KeyboardButton('📚 Ver Catálogo')
  btn_carrito = types.KeyboardButton('🛒 Ver mi Pedido')
  btn_ayuda = types.KeyboardButton('❓ Ayuda / Contacto')
  btn_admin = types.KeyboardButton('🔑 Panel Admin')
  markup.add(btn_catalogo, btn_carrito, btn_ayuda, btn_admin)

  bot.send_message(
      chat_id,
      '🛍️ **Menú Principal**\nUsa los botones de abajo para navegar:',
      reply_markup=markup,
      parse_mode='Markdown'
  )

# --- TECLADO DE ADMINISTRADOR ---
def mostrar_teclado_admin(chat_id):
  tasa_actual = obtener_tasa_bcv()
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  btn_clientes = types.KeyboardButton('👥 Ver Clientes y Deudas')
  btn_listar = types.KeyboardButton('📋 Listar Productos')
  btn_salir = types.KeyboardButton('🚪 Salir del Panel Admin')
  markup.add(btn_clientes, btn_listar, btn_salir)

  bot.send_message(
      chat_id,
      f'🔓 **Panel Admin Activo**\n💱 Tasa BCV en línea: `{tasa_actual} Bs/$`\n\nUsa `/agregar Nombre | PrecioEnBolivares`:',
      reply_markup=markup,
      parse_mode='Markdown'
  )

# --- COMANDO /START ---
@bot.message_handler(commands=['start'])
def enviar_bienvenida(message):
  chat_id = str(message.chat.id)
  clientes = cargar_datos(CLIENTES_FILE, {})

  if chat_id not in sesiones_usuarios:
    sesiones_usuarios[chat_id] = {}

  sesiones_usuarios[chat_id]['esperando_clave'] = False

  if chat_id in clientes:
    nombre = clientes[chat_id]['nombre']
    sesiones_usuarios[chat_id]['nombre'] = nombre
    bot.send_message(message.chat.id, f'¡Hola de nuevo, **{nombre}**! 🛍️', parse_mode='Markdown')
    mostrar_teclado_principal(message.chat.id)
  else:
    sesiones_usuarios[chat_id]['esperando_nombre'] = True
    bot.send_message(
        message.chat.id,
        '¡Bienvenido a nuestra tienda! 🛍️\nPara comenzar y registrar tu pedido, por favor **escribe tu nombre y apellido real**:',
        parse_mode='Markdown',
    )

# --- CONTROL DE TEXTO Y MENÚS ---
@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def manejar_textos_generales(message):
  chat_id = str(message.chat.id)
  user_id = message.from_user.id
  
  if chat_id not in sesiones_usuarios:
    sesiones_usuarios[chat_id] = {}

  if sesiones_usuarios[chat_id].get('esperando_nombre', False):
    nombre_ingresado = message.text.strip()
    if len(nombre_ingresado) < 2:
      bot.reply_to(message, 'Por favor, escribe un nombre válido.')
      return

    clientes = cargar_datos(CLIENTES_FILE, {})
    clientes[chat_id] = {
        'nombre': nombre_ingresado,
        'username': message.from_user.username or 'Sin alias',
        'deuda_total': 0.0,
        'historial_compras': [],
    }
    guardar_datos(CLIENTES_FILE, clientes)

    sesiones_usuarios[chat_id]['esperando_nombre'] = False
    sesiones_usuarios[chat_id]['nombre'] = nombre_ingresado

    bot.reply_to(message, f'¡Mucho gusto, **{nombre_ingresado}**! 🎉 Registro exitoso.')
    mostrar_teclado_principal(message.chat.id)
    return

  if sesiones_usuarios[chat_id].get('esperando_clave', False):
    clave_ingresada = message.text.strip()
    sesiones_usuarios[chat_id]['esperando_clave'] = False

    if user_id in ADMINS_AUTORIZADOS and clave_ingresada == ADMINS_AUTORIZADOS[user_id]["clave"]:
      sesiones_usuarios[chat_id]['es_admin'] = True
      mostrar_teclado_admin(chat_id)
    else:
      bot.reply_to(message, '❌ Acceso denegado. Clave incorrecta.')
      mostrar_teclado_principal(message.chat.id)
    return

  texto = message.text
  if texto == '📚 Ver Catálogo':
    tasa_bcv = obtener_tasa_bcv()
    productos = cargar_datos(DATA_FILE, {'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0}})
    markup = types.InlineKeyboardMarkup(row_width=1)
    for prod_id, info in productos.items():
      precio_dolar = info['precio']
      precio_bs = precio_dolar * tasa_bcv
      texto_boton = f"➕ {info['nombre']} — ${precio_dolar:.2f} ({precio_bs:,.2f} Bs)"
      markup.add(types.InlineKeyboardButton(texto_boton, callback_data=f'add_{prod_id}'))
    markup.add(types.InlineKeyboardButton('🛒 Ver Carrito y Total', callback_data='ver_carrito'))
    
    bot.send_message(message.chat.id, f"📦 **Catálogo Disponible** (Tasa en línea: {tasa_bcv} Bs/$):\nToca un producto para sumarlo:", reply_markup=markup, parse_mode='Markdown')

  elif texto == '🛒 Ver mi Pedido':
    if chat_id not in sesiones_usuarios or not sesiones_usuarios[chat_id].get('carrito'):
      bot.send_message(message.chat.id, '🛒 Tu carrito está vacío actualmente.')
      return
    bot.send_message(message.chat.id, 'Revisa tus productos seleccionados abriendo el carrito desde el catálogo.')

  elif texto == '❓ Ayuda / Contacto':
    bot.send_message(message.chat.id, '📞 Si tienes dudas con tu pedido o pagos, comunícate directamente con el administrador.')

  elif texto == '🔑 Panel Admin':
    if user_id not in ADMINS_AUTORIZADOS:
      bot.send_message(message.chat.id, '❌ No tienes permisos de administrador.')
      return
    sesiones_usuarios[chat_id]['esperando_clave'] = True
    bot.send_message(message.chat.id, '🔒 Ingresa la **clave secreta** de administrador:', parse_mode='Markdown')

  elif texto == '🚪 Salir del Panel Admin':
    sesiones_usuarios[chat_id]['es_admin'] = False
    bot.send_message(message.chat.id, '🔒 Has salido del panel de administrador.')
    mostrar_teclado_principal(message.chat.id)

  elif texto == '👥 Ver Clientes y Deudas':
    if not sesiones_usuarios[chat_id].get('es_admin', False) or user_id not in ADMINS_AUTORIZADOS:
      return
    tasa_bcv = obtener_tasa_bcv()
    clientes = cargar_datos(CLIENTES_FILE, {})
    if not clientes:
      bot.reply_to(message, 'No hay clientes registrados todavía.')
      return
    texto_cli = f'👥 **Lista de Clientes y Deudas** (Tasa: {tasa_bcv} Bs/$):\n\n'
    for c_id, info in clientes.items():
      deuda_d = info['deuda_total']
      deuda_b = deuda_d * tasa_bcv
      texto_cli += f"👤 **{info['nombre']}**\n   ID: `{c_id}`\n   💰 Deuda: **${deuda_d:.2f}** *({deuda_b:,.2f} Bs)*\n\n"
    bot.reply_to(message, texto_cli, parse_mode='Markdown')

  elif texto == '📋 Listar Productos':
    if not sesiones_usuarios[chat_id].get('es_admin', False) or user_id not in ADMINS_AUTORIZADOS:
      return
    tasa_bcv = obtener_tasa_bcv()
    productos = cargar_datos(DATA_FILE, {'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0}})
    texto_prod = f'📋 **Catálogo Interno** (Tasa: {tasa_bcv} Bs/$):\n\n'
    for p_id, info in productos.items():
      p_d = info['precio']
      p_b = p_d * tasa_bcv
      texto_prod += f"- `id: {p_id}` -> {info['nombre']} (${p_d:.2f} / {p_b:,.2f} Bs)\n"
    bot.reply_to(message, texto_prod, parse_mode='Markdown')


# --- COMANDOS ADMINISTRADOR ---
@bot.message_handler(commands=['limpiar'])
def admin_limpiar_deuda(message):
  if message.from_user.id not in ADMINS_AUTORIZADOS:
    return
  try:
    chat_id_cliente = message.text.replace('/limpiar', '').strip()
    clientes = cargar_datos(CLIENTES_FILE, {})
    if chat_id_cliente in clientes:
      clientes[chat_id_cliente]['deuda_total'] = 0.0
      guardar_datos(CLIENTES_FILE, clientes)
      nombre_cli = clientes[chat_id_cliente]['nombre']
      bot.reply_to(message, f'✅ Deuda saldada para: **{nombre_cli}** (ID: `{chat_id_cliente}`). Saldo en $0.00', parse_mode='Markdown')
    else:
      bot.reply_to(message, '❌ No se encontró ningún cliente con ese ID.')
  except Exception:
    bot.reply_to(message, '❌ Usa el formato: `/limpiar ID_DEL_CLIENTE`', parse_mode='Markdown')

@bot.message_handler(commands=['agregar'])
def admin_agregar_producto(message):
  if message.from_user.id not in ADMINS_AUTORIZADOS:
    return
  try:
    texto = message.text.replace('/agregar', '').strip()
    nombre, precio_bs_ingresado = texto.split('|')
    
    tasa_bcv = obtener_tasa_bcv()
    precio_bs = float(precio_bs_ingresado.strip())
    
    # 💱 Convierte automáticamente los bolívares ingresados a dólares para guardarlos
    precio_dolares = precio_bs / tasa_bcv

    productos = cargar_datos(DATA_FILE, {'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0}})
    p_id = nombre.strip().lower().replace(' ', '_')
    
    productos[p_id] = {'nombre': nombre.strip(), 'precio': round(precio_dolares, 2)}
    guardar_datos(DATA_FILE, productos)
    
    bot.reply_to(message, f'✅ Producto agregado en Bolívares:\n📦 {nombre.strip()} - {precio_bs:,.2f} Bs (~${precio_dolares:.2f} USD)')
  except Exception:
    bot.reply_to(message, '❌ Usa el formato correcto en Bolívares:\n`/agregar Harina | 150.0`', parse_mode='Markdown')


# --- GESTIÓN DE BOTONES (CARRITO Y RECIBO EN TEXTO) ---
@bot.callback_query_handler(func=lambda call: True)
def manejar_botones(call):
  chat_id = str(call.message.chat.id)
  tasa_bcv = obtener_tasa_bcv()
  productos = cargar_datos(DATA_FILE, {'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0}})

  if chat_id not in sesiones_usuarios:
    sesiones_usuarios[chat_id] = {'carrito': []}
  if 'carrito' not in sesiones_usuarios[chat_id]:
    sesiones_usuarios[chat_id]['carrito'] = []

  if call.data == 'ver_catalogo':
    markup = types.InlineKeyboardMarkup(row_width=1)
    for prod_id, info in productos.items():
      p_d = info['precio']
      p_b = p_d * tasa_bcv
      markup.add(types.InlineKeyboardButton(f"➕ {info['nombre']} — ${p_d:.2f} ({p_b:,.2f} Bs)", callback_data=f'add_{prod_id}'))
    markup.add(types.InlineKeyboardButton('🛒 Ver Carrito y Total', callback_data='ver_carrito'))
    bot.edit_message_text(f'📦 **Catálogo Disponible** (Tasa en línea: {tasa_bcv} Bs/$):\nToca un producto para sumarlo:', chat_id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

  elif call.data.startswith('add_'):
    prod_id = call.data.split('_', 1)[1]
    if prod_id in productos:
      sesiones_usuarios[chat_id]['carrito'].append(prod_id)
      nombre_prod = productos[prod_id]['nombre']
      bot.answer_callback_query(call.id, f'¡Agregado: {nombre_prod}!')
      
      markup = types.InlineKeyboardMarkup(row_width=1)
      for p_id, info in productos.items():
        p_d = info['precio']
        p_b = p_d * tasa_bcv
        markup.add(types.InlineKeyboardButton(f"➕ {info['nombre']} — ${p_d:.2f} ({p_b:,.2f} Bs)", callback_data=f'add_{p_id}'))
      markup.add(types.InlineKeyboardButton('🛒 Ver Carrito y Total', callback_data='ver_carrito'))
      bot.edit_message_text(f'✅ **{nombre_prod}** agregado.\n¿Deseas algo más?', chat_id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

  elif call.data == 'ver_carrito':
    carrito = sesiones_usuarios[chat_id]['carrito']
    if not carrito:
      markup = types.InlineKeyboardMarkup()
      markup.add(types.InlineKeyboardButton('Ver Catálogo', callback_data='ver_catalogo'))
      bot.edit_message_text('🛒 Tu carrito está vacío.', chat_id, call.message.message_id, reply_markup=markup)
      return

    conteo = {}
    for prod_id in carrito:
      conteo[prod_id] = conteo.get(prod_id, 0) + 1

    resumen = f'🛒 **Tu Pedido Actual** (Tasa: {tasa_bcv} Bs/$):\n\n'
    total_dolares = 0.0
    for prod_id, cant in conteo.items():
      if prod_id in productos:
        nom = productos[prod_id]['nombre']
        precio_d = productos[prod_id]['precio']
        sub_d = precio_d * cant
        sub_b = sub_d * tasa_bcv
        total_dolares += sub_d
        resumen += f'- {cant}x {nom} (${precio_d:.2f} c/u) = **${sub_d:.2f}** *({sub_b:,.2f} Bs)*\n'

    total_bolivares = total_dolares * tasa_bcv
    resumen += f'\n💰 **Total USD: ${total_dolares:.2f}**\n🇻🇪 **Total Bolívares: {total_bolivares:,.2f} Bs**'
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Confirmar Pedido', callback_data='confirmar_pedido'),
        types.InlineKeyboardButton('🗑️ Vaciar Carrito', callback_data='vaciar_carrito'),
        types.InlineKeyboardButton('➕ Agregar más', callback_data='ver_catalogo'),
    )
    bot.edit_message_text(resumen, chat_id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

  elif call.data == 'vaciar_carrito':
    sesiones_usuarios[chat_id]['carrito'] = []
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('Ver Catálogo', callback_data='ver_catalogo'))
    bot.edit_message_text('🗑️ Carrito vaciado.', chat_id, call.message.message_id, reply_markup=markup)

  elif call.data == 'confirmar_pedido':
    carrito = sesiones_usuarios[chat_id]['carrito']
    if not carrito:
      bot.answer_callback_query(call.id, 'El carrito está vacío.')
      return

    clientes = cargar_datos(CLIENTES_FILE, {})
    nombre_cliente = clientes.get(chat_id, {}).get('nombre', 'Cliente')

    conteo = {}
    for prod_id in carrito:
      conteo[prod_id] = conteo.get(prod_id, 0) + 1

    detalle = ''
    total_dolares = 0.0
    for prod_id, cant in conteo.items():
      if prod_id in productos:
        nom = productos[prod_id]['nombre']
        sub_d = productos[prod_id]['precio'] * cant
        sub_b = sub_d * tasa_bcv
        total_dolares += sub_d
        detalle += f'- {cant}x {nom} (${sub_d:.2f} / {sub_b:,.2f} Bs)\n'

    total_bolivares = total_dolares * tasa_bcv

    if chat_id in clientes:
      clientes[chat_id]['deuda_total'] += total_dolares
      guardar_datos(CLIENTES_FILE, clientes)

    # Mensaje de recibo detallado por texto para el cliente
    recibo_texto = (
        '🎉 **¡PEDIDO CONFIRMADO CON ÉXITO!** 🎉\n\n'
        f'👤 Cliente: {nombre_cliente}\n'
        f'💱 Tasa BCV aplicada: {tasa_bcv} Bs/$\n\n'
        f'📦 **Detalle:**\n{detalle}\n'
        f'💵 **Total a Pagar:**\n'
        f'• **${total_dolares:.2f} USD**\n'
        f'• **{total_bolivares:,.2f} Bs**\n\n'
        'Se ha sumado a tu cuenta. ¡Gracias por tu compra!'
    )
    bot.edit_message_text(recibo_texto, chat_id, call.message.message_id, parse_mode='Markdown')

    # Notificación al administrador
    for admin_id_num in ADMINS_AUTORIZADOS.keys():
      deuda_cli_d = clientes.get(chat_id, {}).get('deuda_total', 0.0)
      deuda_cli_b = deuda_cli_d * tasa_bcv
      
      alerta = (
          '🚨 **¡NUEVO PEDIDO DE TIENDA!** 🚨\n\n'
          f'👤 Cliente: **{nombre_cliente}**\nID: `{chat_id}`\n\n'
          f'{detalle}\n'
          f'💰 **Orden:** ${total_dolares:.2f} USD *({total_bolivares:,.2f} Bs)*\n'
          f'📂 **Deuda Total Acumulada:** ${deuda_cli_d:.2f} *({deuda_cli_b:,.2f} Bs)*'
      )
      try:
        bot.send_message(admin_id_num, alerta, parse_mode='Markdown')
      except Exception as e:
        print(f'Error al notificar admin {admin_id_num}: {e}')

    sesiones_usuarios[chat_id]['carrito'] = []


# --- CONFIGURACIÓN WEBHOOK FLASK ---
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
  json_str = request.get_data().decode('UTF-8')
  update = telebot.types.Update.de_json(json_str)
  bot.process_new_updates([update])
  return '!', 200

@app.route('/')
def index():
  return 'Bot de Tienda y Deudas Independiente Activo', 200

if __name__ == '__main__':
  bot.remove_webhook()
  bot.set_webhook(url=f'https://tienda-online-2kqw.onrender.com/{TOKEN}')
  app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
