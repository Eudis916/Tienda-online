import json
import os
from flask import Flask, request
import telebot
from telebot import types

# --- TOKEN EXCLUSIVO DE LA TIENDA ---
TOKEN = '9087964567:AAFvgiOhYZeV_5oMjK7FQCtdTnPxQfntHHs'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- CONFIGURACIÓN DE ADMINISTRADOR ---
# Reemplaza este número con tu ID real de Telegram para las alertas.
ADMIN_ID = 6374498816  # Tu ID detectado en las pruebas anteriores

# Archivos locales para guardar datos de forma persistente
DATA_FILE = 'productos.json'
CLIENTES_FILE = 'clientes.json'


# Funciones para cargar y guardar datos
def cargar_datos(archivo, defecto):
  if os.path.exists(archivo):
    with open(archivo, 'r', encoding='utf-8') as f:
      return json.load(f)
  return defecto


def guardar_datos(archivo, datos):
  with open(archivo, 'w', encoding='utf-8') as f:
    json.dump(datos, f, ensure_ascii=False, indent=4)


# Sesiones temporales para el flujo de clientes
sesiones_usuarios = {}


# --- TECLADO DE ACCESO RÁPIDO PARA CLIENTES ---
def mostrar_teclado_principal(chat_id):
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  btn_catalogo = types.KeyboardButton('📚 Ver Catálogo')
  btn_carrito = types.KeyboardButton('🛒 Ver mi Pedido')
  btn_ayuda = types.KeyboardButton('❓ Ayuda / Contacto')
  markup.add(btn_catalogo, btn_carrito, btn_ayuda)

  bot.send_message(
      chat_id,
      '👇 Usa los botones de abajo para navegar rápidamente por la tienda:',
      reply_markup=markup,
  )


# --- COMANDO /START Y REGISTRO DE CLIENTES ---
@bot.message_handler(commands=['start'])
def enviar_bienvenida(message):
  chat_id = str(message.chat.id)
  clientes = cargar_datos(CLIENTES_FILE, {})

  if chat_id not in sesiones_usuarios:
    sesiones_usuarios[chat_id] = {}

  if chat_id in clientes:
    nombre = clientes[chat_id]['nombre']
    sesiones_usuarios[chat_id]['nombre'] = nombre
    bot.send_message(
        message.chat.id,
        f'¡Hola de nuevo, **{nombre}**! 🛍️',
        parse_mode='Markdown',
    )
    mostrar_teclado_principal(message.chat.id)
  else:
    sesiones_usuarios[chat_id]['esperando_nombre'] = True
    bot.send_message(
        message.chat.id,
        '¡Bienvenido a nuestra tienda! 🛍️\nPara comenzar y registrar tu'
        ' pedido, por favor **escribe tu nombre y apellido real**:',
        parse_mode='Markdown',
    )


@bot.message_handler(
    func=lambda m: not m.text.startswith('/')
    and str(m.chat.id) in sesiones_usuarios
    and sesiones_usuarios[str(m.chat.id)].get('esperando_nombre', False)
)
def guardar_nombre_cliente(message):
  chat_id = str(message.chat.id)
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

  bot.reply_to(
      message, f'¡Mucho gusto, **{nombre_ingresado}**! 🎉 Registro exitoso.'
  )
  mostrar_teclado_principal(message.chat.id)


# --- MANEJO DE BOTONES DEL TECLADO INFERIOR ---
@bot.message_handler(
    func=lambda message: message.text
    in ['📚 Ver Catálogo', '🛒 Ver mi Pedido', '❓ Ayuda / Contacto']
)
def manejar_botones_teclado(message):
  chat_id = str(message.chat.id)
  texto = message.text

  if texto == '📚 Ver Catálogo':
    productos = cargar_datos(
        DATA_FILE,
        {
            'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0},
        },
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    for prod_id, info in productos.items():
      markup.add(
          types.InlineKeyboardButton(
              f"➕ {info['nombre']} - ${info['precio']}",
              callback_data=f'add_{prod_id}',
          )
      )
    markup.add(
        types.InlineKeyboardButton(
            '🛒 Ver Carrito y Total', callback_data='ver_carrito'
        )
    )
    bot.send_message(
        message.chat.id,
        '📦 **Catálogo Disponible:**\nToca un producto para sumarlo:',
        reply_markup=markup,
        parse_mode='Markdown',
    )

  elif texto == '🛒 Ver mi Pedido':
    if chat_id not in sesiones_usuarios or not sesiones_usuarios[chat_id].get(
        'carrito'
    ):
      bot.send_message(message.chat.id, '🛒 Tu carrito está vacío actualmente.')
      return
    bot.send_message(
        message.chat.id,
        'Revisa tus productos seleccionados abriendo el carrito desde el'
        ' catálogo.',
    )

  elif texto == '❓ Ayuda / Contacto':
    bot.send_message(
        message.chat.id,
        '📞 Si tienes dudas con tu pedido o pago, comunícate directamente con'
        ' el administrador de la tienda.',
    )


# --- COMANDOS DE ADMINISTRADOR ---
@bot.message_handler(commands=['clientes'])
def admin_ver_clientes(message):
  if message.from_user.id != ADMIN_ID:
    return

  clientes = cargar_datos(CLIENTES_FILE, {})
  if not clientes:
    bot.reply_to(message, 'No hay clientes registrados todavía.')
    return

  texto = '👥 **Lista de Clientes y Deudas Activas:**\n\n'
  for c_id, info in clientes.items():
    texto += (
        f"👤 **{info['nombre']}**\n   ID: `{c_id}`\n   💰 Deuda Pendiente: **$"
        f"{info['deuda_total']:.2f}**\n\n"
    )

  bot.reply_to(message, texto, parse_mode='Markdown')


@bot.message_handler(commands=['limpiar'])
def admin_limpiar_deuda(message):
  if message.from_user.id != ADMIN_ID:
    return

  try:
    chat_id_cliente = message.text.replace('/limpiar', '').strip()
    clientes = cargar_datos(CLIENTES_FILE, {})

    if chat_id_cliente in clientes:
      clientes[chat_id_cliente]['deuda_total'] = 0.0
      guardar_datos(CLIENTES_FILE, clientes)

      nombre_cli = clientes[chat_id_cliente]['nombre']
      bot.reply_to(
          message,
          f'✅ Deuda saldada con éxito para el cliente: **{nombre_cli}** (ID:'
          f' `{chat_id_cliente}`). Su saldo ahora es de $0.00',
          parse_mode='Markdown',
      )
    else:
      bot.reply_to(
          message,
          '❌ No se encontró ningún cliente con ese ID. Usa el comando'
          ' /clientes para revisar la lista.',
      )
  except Exception as e:
    bot.reply_to(
        message,
        '❌ Formato incorrecto. Usa el formato:\n`/limpiar ID_DEL_CLIENTE`',
        parse_mode='Markdown',
    )


@bot.message_handler(commands=['agregar'])
def admin_agregar_producto(message):
  if message.from_user.id != ADMIN_ID:
    return

  try:
    texto = message.text.replace('/agregar', '').strip()
    nombre, precio = texto.split('|')
    productos = cargar_datos(
        DATA_FILE,
        {
            'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0},
        },
    )
    p_id = nombre.strip().lower().replace(' ', '_')
    productos[p_id] = {'nombre': nombre.strip(), 'precio': float(precio.strip())}
    guardar_datos(DATA_FILE, productos)
    bot.reply_to(
        message,
        f'✅ Producto agregado con éxito:\n📦 {nombre.strip()} - ${precio.strip()}',
    )
  except Exception:
    bot.reply_to(
        message,
        '❌ Formato incorrecto.\nUsa el formato:\n`/agregar Nombre del'
        ' producto | 5.0`',
        parse_mode='Markdown',
    )


@bot.message_handler(commands=['listar'])
def admin_listar_productos(message):
  if message.from_user.id != ADMIN_ID:
    return
  productos = cargar_datos(
      DATA_FILE,
      {
          'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0},
      },
  )
  texto = '📋 **Catálogo Interno (Productos):**\n\n'
  for p_id, info in productos.items():
    texto += f'- `id: {p_id}` -> {info['nombre']} (${info['precio']})\n'
  bot.reply_to(message, texto, parse_mode='Markdown')


# --- GESTIÓN DE BOTONES E INTERACCIÓN ---
@bot.callback_query_handler(func=lambda call: True)
def manejar_botones(call):
  chat_id = str(call.message.chat.id)
  productos = cargar_datos(
      DATA_FILE,
      {
          'producto_1': {'nombre': 'Producto Ejemplo', 'precio': 5.0},
      },
  )

  if chat_id not in sesiones_usuarios:
    sesiones_usuarios[chat_id] = {'carrito': []}
  if 'carrito' not in sesiones_usuarios[chat_id]:
    sesiones_usuarios[chat_id]['carrito'] = []

  if call.data == 'ver_catalogo':
    markup = types.InlineKeyboardMarkup(row_width=1)
    for prod_id, info in productos.items():
      markup.add(
          types.InlineKeyboardButton(
              f"➕ {info['nombre']} - ${info['precio']}",
              callback_data=f'add_{prod_id}',
          )
      )
    markup.add(
        types.InlineKeyboardButton(
            '🛒 Ver Carrito y Total', callback_data='ver_carrito'
        )
    )
    bot.edit_message_text(
        '📦 **Catálogo Disponible:**\nToca un producto para sumarlo:',
        chat_id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown',
    )

  elif call.data.startswith('add_'):
    prod_id = call.data.split('_', 1)[1]
    if prod_id in productos:
      sesiones_usuarios[chat_id]['carrito'].append(prod_id)
      nombre_prod = productos[prod_id]['nombre']
      bot.answer_callback_query(call.id, f'¡Agregado: {nombre_prod}!')

      markup = types.InlineKeyboardMarkup(row_width=1)
      for p_id, info in productos.items():
        markup.add(
            types.InlineKeyboardButton(
                f"➕ {info['nombre']} - ${info['precio']}",
                callback_data=f'add_{p_id}',
            )
        )
      markup.add(
          types.InlineKeyboardButton(
              '🛒 Ver Carrito y Total', callback_data='ver_carrito'
          )
      )
      bot.edit_message_text(
          f'✅ **{nombre_prod}** agregado.\n¿Deseas algo más?',
          chat_id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode='Markdown',
      )

  elif call.data == 'ver_carrito':
    carrito = sesiones_usuarios[chat_id]['carrito']
    if not carrito:
      markup = types.InlineKeyboardMarkup()
      markup.add(
          types.InlineKeyboardButton('Ver Catálogo', callback_data='ver_catalogo')
      )
      bot.edit_message_text(
          '🛒 Tu carrito está vacío.',
          chat_id,
          call.message.message_id,
          reply_markup=markup,
      )
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
        types.InlineKeyboardButton(
            '✅ Confirmar Pedido', callback_data='confirmar_pedido'
        ),
        types.InlineKeyboardButton(
            '🗑️ Vaciar Carrito', callback_data='vaciar_carrito'
        ),
        types.InlineKeyboardButton(
            '➕ Agregar más', callback_data='ver_catalogo'
        ),
    )
    bot.edit_message_text(
        resumen,
        chat_id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown',
    )

  elif call.data == 'vaciar_carrito':
    sesiones_usuarios[chat_id]['carrito'] = []
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('Ver Catálogo', callback_data='ver_catalogo')
    )
    bot.edit_message_text(
        '🗑️ Carrito vaciado.', chat_id, call.message.message_id, reply_markup=markup
    )

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
        '🎉 **¡Pedido registrado con éxito!**\n\nSe ha sumado a tu cuenta.'
        f' Monto de este pedido: **${total:.2f}**\nPronto nos pondremos en'
        ' contacto contigo.',
        chat_id,
        call.message.message_id,
        parse_mode='Markdown',
    )

    alerta = (
        '🚨 **¡NUEVO PEDIDO DE TIENDA!** 🚨\n\n👤 Cliente: **'
        f'{nombre_cliente}**\nID: `{chat_id}`\n\n{detalle}\n💰 Monto de esta'
        f' orden: **${total:.2f}**\n📂 **Deuda Total Acumulada:** $'
        f"{clientes.get(chat_id, {}).get('deuda_total', 0.0):.2f}"
    )
    try:
      bot.send_message(ADMIN_ID, alerta, parse_mode='Markdown')
    except Exception as e:
      print(f'Error al notificar admin: {e}')

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
  bot.set_webhook(
      url=f'https://tienda-online-2kqw.onrender.com/{TOKEN}'
  )
  app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
