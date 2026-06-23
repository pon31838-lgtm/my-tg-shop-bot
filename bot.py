import telebot
from telebot import types
import sqlite3
import os
from datetime import datetime

TOKEN = '8611662764:AAEpBr-k6YRZFryzx_qpjgYF8s75I-Gfmz0'  # Замени на токен от @BotFather
ADMIN_ID = 6446656281 # Твой Telegram ID (узнай у @userinfobot)

bot = telebot.TeleBot(TOKEN)

# Создание базы данных
def init_db():
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    
    # Таблица товаров
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  price INTEGER,
                  currency TEXT,
                  photo_id TEXT,
                  description TEXT)''')
    
    # Таблица заказов
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  product_id INTEGER,
                  game_nick TEXT,
                  status TEXT,
                  screenshot_id TEXT,
                  date TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# Главное меню
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('📦 Каталог'))
    markup.add(types.KeyboardButton('❓ Как купить?'))
    return markup

# Админ-меню
def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('➕ Добавить товар'))
    markup.add(types.KeyboardButton('📋 Список товаров'))
    markup.add(types.KeyboardButton('📨 Рассылка'))
    markup.add(types.KeyboardButton('📊 Заказы'))
    markup.add(types.KeyboardButton('⬅️ Выйти из админки'))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, '👑 Админ-панель', reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, 
                        '👋 Добро пожаловать в магазин!\n'
                        'Выберите действие:',
                        reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == '📦 Каталог')
def catalog(message):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute('SELECT * FROM products')
    products = c.fetchall()
    conn.close()
    
    if not products:
        bot.send_message(message.chat.id, '😔 Каталог пока пуст')
        return
    
    # Показываем первый товар
    show_product(message.chat.id, 0)

def show_product(chat_id, index):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute('SELECT * FROM products')
    products = c.fetchall()
    conn.close()
    
    if not products:
        return
    
    if index < 0:
        index = len(products) - 1
    elif index >= len(products):
        index = 0
    
    product = products[index]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    nav_buttons = []
    
    if len(products) > 1:
        nav_buttons.append(types.InlineKeyboardButton('⬅️', callback_data=f'nav_{index-1}'))
        nav_buttons.append(types.InlineKeyboardButton('➡️', callback_data=f'nav_{index+1}'))
        markup.add(*nav_buttons)
    
    currency_symbol = '⭐' if product[3] == 'stars' else '💎'
    markup.add(types.InlineKeyboardButton(f'Купить за {product[2]} {currency_symbol}', 
                                         callback_data=f'buy_{product[0]}'))
    
    caption = f'📦 {product[1]}\n💰 Цена: {product[2]} {currency_symbol}\n📝 {product[4] or ""}'
    
    if product[4]:
        bot.send_photo(chat_id, product[4], caption=caption, reply_markup=markup)
    else:
        bot.send_message(chat_id, caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('nav_'))
def navigate_catalog(call):
    index = int(call.data.split('_')[1])
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_product(call.message.chat.id, index)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_product(call):
    product_id = int(call.data.split('_')[1])
    
    msg = bot.send_message(call.message.chat.id, '🎮 Введите ваш никнейм в игре:')
    bot.register_next_step_handler(msg, process_nick, product_id)

def process_nick(message, product_id):
    nick = message.text
    
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute('SELECT * FROM products WHERE id=?', (product_id,))
    product = c.fetchone()
    
    if product[3] == 'rub':
        payment_info = (
            f'💎 Оплата игровыми рублями:\n\n'
            f'1️⃣ Добавьте в друзья бота: supp2562829\n'
            f'2️⃣ Отправьте ему {product[2]} игровых рублей\n'
            f'3️⃣ После оплаты нажмите "Проверить оплату"'
        )
    else:
        payment_info = (
            f'⭐ Оплата Telegram Stars:\n\n'
            f'1️⃣ Отправьте {product[2]} звезд пользователю @support252627\n'
            f'2️⃣ После оплаты нажмите "Проверить оплату"'
        )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('✅ Проверить оплату', 
                                         callback_data=f'check_{product_id}_{nick}'))
    
    bot.send_message(message.chat.id, payment_info, reply_markup=markup)
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_payment(call):
    _, product_id, nick = call.data.split('_')
    
    msg = bot.send_message(call.message.chat.id, '📸 Отправьте скриншот оплаты:')
    bot.register_next_step_handler(msg, process_screenshot, product_id, nick)

def process_screenshot(message, product_id, nick):
    if message.photo:
        screenshot_id = message.photo[-1].file_id
        
        conn = sqlite3.connect('shop.db')
        c = conn.cursor()
        c.execute('INSERT INTO orders (user_id, product_id, game_nick, status, screenshot_id, date) VALUES (?, ?, ?, ?, ?, ?)',
                 (message.from_user.id, product_id, nick, 'pending', screenshot_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        order_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Отправляем админу
        admin_markup = types.InlineKeyboardMarkup(row_width=2)
        admin_markup.add(
            types.InlineKeyboardButton('✅ Принять', callback_data=f'accept_{order_id}'),
            types.InlineKeyboardButton('❌ Отклонить', callback_data=f'reject_{order_id}')
        )
        
        bot.send_photo(ADMIN_ID, screenshot_id,
                      caption=f'🛍 Новый заказ #{order_id}\n'
                             f'Товар ID: {product_id}\n'
                             f'Ник: {nick}\n'
                             f'Пользователь: @{message.from_user.username}',
                      reply_markup=admin_markup)
        
        bot.send_message(message.chat.id, '✅ Заказ отправлен на проверку!')
    else:
        bot.send_message(message.chat.id, '❌ Отправьте скриншот!')

@bot.callback_query_handler(func=lambda call: call.data.startswith(('accept_', 'reject_')))
def process_order(call):
    action, order_id = call.data.split('_')
    
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE id=?', (order_id,))
    order = c.fetchone()
    
    if action == 'accept':
        c.execute('UPDATE orders SET status="accepted" WHERE id=?', (order_id,))
        conn.commit()
        
        bot.send_message(order[1], 
                        '✅ Оплата подтверждена!\n'
                        '🤖 Подойдите к боту возле банкоматов\n'
                        'и проследуйте за ним для получения товара')
        
        # Кнопка "Выдано" для админа
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('✅ Выдано', callback_data=f'delivered_{order_id}'))
        
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=markup)
    else:
        c.execute('UPDATE orders SET status="rejected" WHERE id=?', (order_id,))
        conn.commit()
        
        bot.send_message(order[1], '❌ Заказ отклонен')
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=None)
    
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('delivered_'))
def delivered_order(call):
    order_id = call.data.split('_')[1]
    
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE id=?', (order_id,))
    order = c.fetchone()
    c.execute('UPDATE orders SET status="delivered" WHERE id=?', (order_id,))
    conn.commit()
    conn.close()
    
    bot.send_message(order[1], 
                    '🎉 Товар выдан! Пожалуйста, оставьте отзыв с отметкой бота @your_bot')
    
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                  reply_markup=None)

@bot.message_handler(func=lambda message: message.text == '❓ Как купить?')
def how_to_buy(message):
    text = (
        '📖 <b>Как совершить покупку:</b>\n\n'
        '1️⃣ Выберите товар в каталоге\n'
        '2️⃣ Нажмите кнопку "Купить"\n'
        '3️⃣ Введите ваш игровой никнейм\n'
        '4️⃣ Следуйте инструкциям по оплате\n'
        '5️⃣ Отправьте скриншот оплаты\n'
        '6️⃣ Дождитесь подтверждения\n'
        '7️⃣ Получите товар у бота возле банкоматов\n\n'
        '<i>По всем вопросам: @support252627</i>'
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')

# Админские функции
@bot.message_handler(func=lambda message: message.text == '➕ Добавить товар' and message.from_user.id == ADMIN_ID)
def add_product_start(message):
    msg = bot.send_message(message.chat.id, '📝 Введите название товара:')
    bot.register_next_step_handler(msg, process_name)

def process_name(message):
    product_data = {'name': message.text}
    msg = bot.send_message(message.chat.id, '💰 Введите цену:')
    bot.register_next_step_handler(msg, process_price, product_data)

def process_price(message, product_data):
    try:
        product_data['price'] = int(message.text)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('💎 Рубли', callback_data='curr_rub'),
            types.InlineKeyboardButton('⭐ Stars', callback_data='curr_stars')
        )
        msg = bot.send_message(message.chat.id, '💳 Выберите валюту:', reply_markup=markup)
        bot.register_next_step_handler(msg, process_currency, product_data)
    except ValueError:
        bot.send_message(message.chat.id, '❌ Введите число!')

def process_currency(message, product_data):
    # Этот хендлер не будет вызван для callback, обновим логику
    pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('curr_'))
def process_currency_callback(call):
    product_data = {'currency': call.data.split('_')[1]}
    msg = bot.send_message(call.message.chat.id, '📸 Отправьте фото товара:')
    bot.register_next_step_handler(msg, process_photo, product_data)

def process_photo(message, product_data):
    if message.photo:
        product_data['photo_id'] = message.photo[-1].file_id
        msg = bot.send_message(message.chat.id, '📝 Введите описание (или пропустите):')
        bot.register_next_step_handler(msg, process_description, product_data)
    else:
        bot.send_message(message.chat.id, '❌ Отправьте фото!')

def process_description(message, product_data):
    description = message.text if message.text != 'пропустить' else ''
    
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute('INSERT INTO products (name, price, currency, photo_id, description) VALUES (?, ?, ?, ?, ?)',
             (product_data['name'], product_data['price'], product_data['currency'], 
              product_data['photo_id'], description))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, '✅ Товар добавлен!', reply_markup=admin_menu())

@bot.message_handler(func=lambda message: message.text == '📨 Рассылка' and message.from_user.id == ADMIN_ID)
def broadcast_start(message):
    msg = bot.send_message(message.chat.id, '📨 Введите сообщение для рассылки:')
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(message):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    
    # Получаем всех уникальных пользователей из заказов
    c.execute('SELECT DISTINCT user_id FROM orders')
    users = c.fetchall()
    conn.close()
    
    for user in users:
        try:
            bot.send_message(user[0], message.text)
        except:
            pass
    
    bot.send_message(message.chat.id, '✅ Рассылка завершена!', reply_markup=admin_menu())

@bot.message_handler(func=lambda message: message.text == '📊 Заказы' and message.from_user.id == ADMIN_ID)
def view_orders(message):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute('SELECT * FROM orders ORDER BY date DESC LIMIT 10')
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        bot.send_message(message.chat.id, '📊 Нет заказов')
        return
    
    text = '📊 Последние заказы:\n\n'
    for order in orders:
        status_emoji = {
            'pending': '⏳',
            'accepted': '✅',
            'rejected': '❌',
            'delivered': '🎉'
        }
        text += f'{status_emoji.get(order[4], "")} #{order[0]} | {order[2]} | {order[5]}\n'
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == '⬅️ Выйти из админки' and message.from_user.id == ADMIN_ID)
def exit_admin(message):
    bot.send_message(message.chat.id, '👋 Вы вышли из админ-панели', reply_markup=main_menu())

# Запуск бота
if __name__ == '__main__':
    print('Бот запущен!')
    bot.polling(none_stop=True)
