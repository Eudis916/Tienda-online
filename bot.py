import json
import os
from flask import Flask, request
import telebot
from telebot import types

# --- TOKEN EXCLUSIVO DE LA TIENDA ---
TOKEN = '9087964567:AAFvgiOhYZeV_5oMjK7FQCtdTnPxQfntHHs'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- CONFIGURACIÓN DE ADMINISTRADORES Y SEGURIDAD ---
# Puedes agregar más administradores en el futuro escribiendo su ID de Telegram y contraseña aquí
ADMINS_AUTORIZADOS = {
    6374498816: {"nombre": "Moisés", "clave": "2010"}
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

# --- TECLADO DE ADMINISTRADOR (SECRETO) ---
def mostrar_teclado_admin(chat_id):
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  btn_clientes = types.KeyboardButton('👥 Ver Clientes y Deudas')
  btn_listar = types.KeyboardButton('📋 Listar Productos')
  btn_salir = types.KeyboardButton('🚪 Salir del Panel Admin')
  markup.add(btn_clientes, btn_listar, btn_salir)

  bot.send_message(
      chat_id,
      '🔓 **¡Acceso concedido al Panel de Administrador!**\nSelecciona una opción o escribe `/agregar Nombre | Precio` y `/limpiar ID`:',
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

# --- CONTROL DE TEXTO, REGISTROS Y CLAVE ADMIN ---
@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def manejar_textos_generales(message):
  chat_id = str(message.chat.id)
  user_id = message.from_user.id
  
  if chat_id not in sesiones_usuarios:
    sesiones_usuarios[chat_id] = {}

  # 1. Si está esperando el nombre de registro
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

  # 2. Si está ingresando la clave de Administrador (Doble seguridad: ID + Contraseña)
  if sesiones_usuarios[chat_id].get('esperando_clave', False):
    clave_ingresada = message.text.strip()
    sesiones_usuarios[chat_id]['esperando_clave'] = False

    if user_id in ADMINS_AUTORIZADOS and clave_ingresada == ADMINS_AUTORIZADOS[user_id]["clave"]:
      sesiones_usuarios[chat_id]['es_admin'] = True
      mostrar_teclado_admin(chat_id)
    else:
      bot.reply_to(message, '❌ Acceso denegado. No estás autorizado o la clave es incorrecta.')
      mostrar_teclado_principal(message.chat.id)
    return

  # 3. Manejo de botones del menú de clientes o admin
  texto = message.text
  if texto == '📚 Ver Catálogo':
    productos = cargar_datos(DATA_FILE, {'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0}})
    markup = types.InlineKeyboardMarkup(row_width=1)
    for prod_id, info in productos.items():
      markup.add(types.InlineKeyboardButton(f"➕ {info['nombre']} - ${info['precio']}", callback_data=f'add_{prod_id}'))
    markup.add(types.InlineKeyboardButton('🛒 Ver Carrito y Total', callback_data='ver_carrito'))
    bot.send_message(message.chat.id, '📦 **Catálogo Disponible:**\nToca un producto para sumarlo:', reply_markup=markup, parse_mode='Markdown')

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
    clientes = cargar_datos(CLIENTES_FILE, {})
    if not clientes:
      bot.reply_to(message, 'No hay clientes registrados todavía.')
      return
    texto_cli = '👥 **Lista de Clientes y Deudas Activas:**\n\n'
    for c_id, info in clientes.items():
      texto_cli += f"👤 **{info['nombre']}**\n   ID: `{c_id}`\n   💰 Deuda: **${info['deuda_total']:.2f}**\n\n"
    bot.reply_to(message, texto_cli, parse_mode='Markdown')

  elif texto == '📋 Listar Productos':
    if not sesiones_usuarios[chat_id].get('es_admin', False) or user_id not in ADMINS_AUTORIZADOS:
      return
    productos = cargar_datos(DATA_FILE, {'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0}})
    texto_prod = '📋 **Catálogo Interno (Productos):**\n\n'
    for p_id, info in productos.items():
      texto_prod += f"- `id: {p_id}` -> {info['nombre']} (${info['precio']})\n"
    bot.reply_to(message, texto_prod, parse_mode='Markdown')


# --- COMANDOS DE ADMINISTRADOR POR TEXTO ---
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
    nombre, precio = texto.split('|')
    productos = cargar_datos(DATA_FILE, {'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0}})
    p_id = nombre.strip().lower().replace(' ', '_')
    productos[p_id] = {'nombre': nombre.strip(), 'precio': float(precio.strip())}
    guardar_datos(DATA_FILE, productos)
    bot.reply_to(message, f'✅ Producto agregado:\n📦 {nombre.strip()} - ${precio.strip()}')
  except Exception:
    bot.reply_to(message, '❌ Usa el formato:\n`/agregar Nombre | 5.0`', parse_mode='Markdown')


# --- GESTIÓN DE BOTONES INTERNOS (CARRITO Y CATÁLOGO) ---
@bot.callback_query_handler(func=lambda call: True)
def manejar_botones(call):
  chat_id = str(call.message.chat.id)
  productos = cargar_datos(DATA_FILE, {'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0}})

  if chat_id not in sesiones_usuarios:
    sesiones_usuarios[chat_id] = {'carrito': []}
  if 'carrito' not in sesiones_usuarios[chat_id]:
    sesiones_usuarios[chat_id]['carrito'] = []

  if call.data == 'ver_catalogo':
    markup = types.InlineKeyboardMarkup(row_width=1)
    for prod_id, info in productos.items():
      markup.add(types.InlineKeyboardButton(f"➕ {info['nombre']} - ${info['precio']}", callback_data=f'add_{prod_id}'))
    markup.add(types.InlineKeyboardButton('🛒 Ver Carrito y Total', callback_data='ver_carrito'))
    bot.edit_message_text('📦 **Catálogo Disponible:**\nToca un producto para sumarlo:', chat_id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

  elif call.data.startswith('add_'):
    prod_id = call.data.split('_', 1)[1]
    if prod_id in productos:
      sesiones_usuarios[chat_id]['carrito'].append(prod_id)
      nombre_prod = productos[prod_id]['nombre']
      bot.answer_callback_query(call.id, f'¡Agregado: {nombre_prod}!')
      
      markup = types.InlineKeyboardMarkup(row_width=1)
      for p_id, info in productos.items():
        markup.add(types.InlineKeyboardButton(f"➕ {info['nombre']} - ${info['precio']}", callback_data=f'add_{p_id}'))
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

    resumen = '🛒 **Tu Pedido Actual:**\n\n'
    total = 0.0
    for prod_id, cant in conteo.items():
      if prod_id in productos:
        nom = productos[prod_id]['nombre']
        precio = productos[prod_id]['precio']
        sub = precio * cant
        total += sub
        resumen += f'- {cant}x {nom} (${precio} c/u) = ${sub:.2f}\n'

    resumen += f'\n💰 **Monto Total: ${total:.2f}**'
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
    total = 0.0
    for prod_id, cant in conteo.items():
      if prod_id in productos:
        nom = productos[prod_id]['nombre']
        sub = productos[prod_id]['precio'] * cant
        total += sub
        detalle += f'- {cant}x {nom} (${sub:.2f})\n'

    if chat_id in clientes:
      clientes[chat_id]['deuda_total'] += total
      clientes[chat_id]['historial_compras'].append(detalle)
      guardar_datos(CLIENTES_FILE, clientes)

    bot.edit_message_text(
        '🎉 **¡Pedido registrado con éxito!**\n\nSe ha sumado a tu cuenta. Monto de este pedido: **'
        f'${total:.2f}**\nPronto nos pondremos en contacto contigo.',
        chat_id, call.message.message_id, parse_mode='Markdown'
    )

    # Notificar a todos los administradores registrados
    for admin_id_num in ADMINS_AUTORIZADOS.keys():
      alerta = (
          '🚨 **¡NUEVO PEDIDO DE TIENDA!** 🚨\n\n👤 Cliente: **'
          f'{nombre_cliente}**\nID: `{chat_id}`\n\n{detalle}\n💰 Monto de esta orden: **${total:.2f}**\n📂 **Deuda Total Acumulada:** $'
          f"{clientes.get(chat_id, {}).get('deuda_total', 0.0):.2f}"
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
