import requests
from functools import partial

import redis
from email_validate import validate
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, \
                         Filters, CallbackQueryHandler
from geopy import distance
from cms_lib import CmsAuthentication, get_all_products, get_product_by_id, \
                 get_photo_by_id, add_product_to_cart, get_cart_items, \
                 get_cart, remove_product_from_cart, get_or_create_customer, get_all_entries, save_customer_coords, get_address
                 


def split_products_to_batches(products, batch_size):
    for index in range(0, len(products), 8):
        yield products[index: index + batch_size]



def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lat, lon


def get_menu_keyboard(cms_token: str, batch_size):
    products = list(split_products_to_batches(get_all_products(cms_token)['data'], 8))
    if batch_size <= 0:
        products_batch = products[0]
    elif batch_size >= len(products):
        products_batch = products[-1]
    else:
        products_batch = products[batch_size]
    keyboard = [
        [InlineKeyboardButton(product['name'], callback_data=product['id'])]
        for product in products_batch
    ]
    keyboard.append([
        InlineKeyboardButton('Пред', callback_data=f"batch {batch_size-1}"),
        InlineKeyboardButton('След', callback_data=f"batch {batch_size+1}")]
    )
    keyboard.append(
        [InlineKeyboardButton('Корзина', callback_data='cart')]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


# def get_menu_keyboard(cms_token: str):
#     keyboard = []
#     products = get_all_products(cms_token)
#     keyboard = [
#         [InlineKeyboardButton(product['name'], callback_data=product['id'])]
#         for product in products['data']
#     ]
#     keyboard.append(
#         [InlineKeyboardButton('Корзина', callback_data='cart')]
#     )
#     reply_markup = InlineKeyboardMarkup(keyboard)
#     return reply_markup


def send_user_cart(update, context, cms_token: str):
    query = update.callback_query
    keyboard = []
    text = ''
    cart_items = get_cart_items(cms_token, update.effective_chat.id)
    product_template = '{}\r\n{}\r\n{} пицц в корзине на сумму {}\r\n\r\n'
    for product in cart_items['data']:
        text += product_template.format(
            product['name'],
            product['description'],
            product['quantity'],
            product['meta']['display_price']['with_tax']['value']['formatted']
        )
        keyboard.append(
            [InlineKeyboardButton(
                f" Удалить {product['name']}",
                callback_data=product['id']),
            ]
        )
    cart_info = get_cart(cms_token, update.effective_chat.id)['data']
    text += f"К оплате: {cart_info['meta']['display_price']['with_tax']['formatted']}"

    keyboard.append(
        [InlineKeyboardButton('В меню', callback_data='menu')]
    )
    keyboard.append(
        [InlineKeyboardButton('Оплатить', callback_data='payment')]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup
    )
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=query.message.message_id
    )
    return 'HANDLE_CART'


def waiting_email(update, context, cms_token):
    is_valid_email = validate(
        update.message.text,
        check_blacklist=False,
        check_dns=False,
        check_smtp=False
    )
    if is_valid_email:
        customer_info, created = get_or_create_customer(
            cms_token,
            str(update.effective_chat.id),
            update.message.text
        )
        text = 'Спасибо что купили рыбу'
        if not created:
            text += '. Рады что вам понравилось'
        update.message.reply_text(
            text=text,
        )
        return 'START'

    update.message.reply_text(
        text='Введённый email некорректен. Попробуйте ещё раз',
    )
    return 'WAITING_EMAIL'


def start(update, context, cms_token, batch=0):
    greeting = 'Хочешь пиццы?'
    reply_markup = get_menu_keyboard(cms_token, batch)
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=greeting,
        reply_markup=reply_markup
    )
    if update.callback_query:
        context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.callback_query.message.message_id
        )
    return 'HANDLE_MENU'


def handle_cart(update, context, cms_token):
    query = update.callback_query
    query.answer()
    if query.data == 'menu':
        return start(update, context, cms_token)

    elif query.data == 'payment':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Пришлите ваш адрес или геолокацию',
        )
        return 'HANDLE_WAITING'

    else:
        product_id = query.data
        remove_product_from_cart(
            cms_token,
            update.effective_chat.id,
            product_id
        )
        return send_user_cart(update, context, cms_token)


def handle_menu(update, context, cms_token):
    query = update.callback_query
    query.answer()
    if query.data == 'cart':
        return send_user_cart(update, context, cms_token)

    elif 'batch' in query.data:
        batch= int(query.data.split()[-1])
        return start(update, context, cms_token, batch=batch)

    keyboard = [
        [
            InlineKeyboardButton('Добавить в корзину', callback_data=query.data),
        ],
        [
            InlineKeyboardButton('Назад', callback_data='back_to_menu')
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    product_info = get_product_by_id(cms_token, query.data)['data']
    photo = get_photo_by_id(
        cms_token,
        product_info['relationships']['main_image']['data']['id']
    )
    response_to_user = '{}\r\nСтоимость: {} рублей\r\n {}'.format(
        product_info['name'],
        product_info['price'][0]['amount'],
        product_info['description']
    )
    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=photo,
        caption=response_to_user,
        reply_markup=reply_markup
    )
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=query.message.message_id
    )
    return 'HANDLE_DESCRIPTION'


def handle_description(update, context, cms_token):
    query = update.callback_query
    if query.data == 'back_to_menu':
        query.answer()
        return start(update, context, cms_token)
    elif query.data == 'cart':
        query.answer()
        return send_user_cart(update, context, cms_token)
    else:
        product_id = query.data
        add_product_to_cart(
            cms_token,
            update.effective_chat.id,
            product_id,
            1
        )
        query.answer('Товар добавлен в корзину')
    return 'HANDLE_DESCRIPTION'


def get_delivery_keyboard(nearest_pizzeria, address_entry_id):
    keyboard = [
        [InlineKeyboardButton('Самовывоз', callback_data='pickup')]
    ]
    if nearest_pizzeria['distance'] <= 20:
        keyboard.append(
            [InlineKeyboardButton('Доставка', callback_data=f"delivery {nearest_pizzeria['delivery-chat-id']} {address_entry_id}")]
        )
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


def calculate_delivery(update, context, cms_token, current_pos):
    pizzerias = get_all_entries(cms_token)['data']
    for pizzeria in pizzerias:
        pizzeria_distance = distance.distance(current_pos, (pizzeria['latitude'], pizzeria['longitude']))
        pizzeria['distance'] = pizzeria_distance

    nearest_pizzeria = min(pizzerias, key= lambda x: x['distance'])
    if nearest_pizzeria['distance'] <= 0.5:
        text = 'Можете забрать сами'
    elif nearest_pizzeria['distance'] <= 5:
        text = 'Доставка 100 рублей'
    elif nearest_pizzeria['distance'] <= 20:
        text = 'Доставка 300 рублей'
    else:
        text = 'Самовывоз'

    address_entry_id = save_customer_coords(cms_token, current_pos, update.effective_chat.id)['data']['id']
    reply_markup = get_delivery_keyboard(nearest_pizzeria, address_entry_id)
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup
    )
    return 'HANDLE_ORDER'

    

def handle_waiting(update, context, cms_token, ya_api_key):
    if update.message:
        address = update.message.text
        current_pos = fetch_coordinates(ya_api_key, address)
    elif update.edited_message:
        message = update.edited_message
        current_pos = (message.location.latitude, message.location.longitude)
    if not current_pos:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Не нашел такого',
        )
        return 'HANDLE_WAITING'
    return calculate_delivery(update, context, cms_token, current_pos)

def callback_alarm(context):
    context.bot.send_message(
        chat_id=context.job.context,
        text='''
            Приятного аппетита! *место для рекламы*
            *сообщение что делать если пицца не пришла*'''
    )


def handle_order(update, context, cms_token):
    query = update.callback_query
    query.answer()
    if 'pickup' in query.data:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Будем ждать',
        )
    elif 'delivery' in query.data:
        _, delivery_chat, address_id = query.data.split()
        coords = get_address(cms_token, address_id)['data']
        context.bot.send_location(
            chat_id=delivery_chat,
            latitude = coords['latitude'],
            longitude = coords['longitude']
        )
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Ваш заказ принят в обработку!',
        )
        context.job_queue.run_once(callback_alarm, 6, context=update.effective_chat.id)
    return 'START'
        

def handle_users_reply(update, context, redis_db, cms_auth, ya_api_token=''):
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = redis_db.get(chat_id)

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'WAITING_EMAIL': waiting_email,
        'HANDLE_WAITING': handle_waiting,
        'HANDLE_ORDER': handle_order
    }
    state_handler = states_functions[user_state]
    cms_token = cms_auth.get_access_token()
    if user_state == 'HANDLE_WAITING':
        next_state = state_handler(update, context, cms_token, ya_api_token)
    elif user_state == 'HANDLE_ORDER':
        next_state = state_handler(update, context, cms_token)
    else:
        next_state = state_handler(update, context, cms_token)
    redis_db.set(chat_id, next_state)


def main():
    env = Env()
    env.read_env()
    redis_db = redis.StrictRedis(
        host=env.str('REDIS_HOST'),
        port=env.int('REDIS_PORT'),
        password=env.str('REDIS_PASSWORD'),
        charset="utf-8",
        decode_responses=True
    )
    client_id = env.str('ELASTIC_PATH_CLIENT_ID')
    client_secret = env.str('ELASTIC_PATH_CLIENT_SECRET')
    ya_api_token = env.str('YANDEX_API_TOKEN')
    cms_auth = CmsAuthentication(client_id, client_secret)
    updater = Updater(env.str('TG_BOT_TOKEN'))
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(
        partial(handle_users_reply, redis_db=redis_db, cms_auth=cms_auth), pass_job_queue=True)
    )
    dispatcher.add_handler(CommandHandler(
        'start',
        partial(handle_users_reply, redis_db=redis_db, cms_auth=cms_auth))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.text,
        partial(handle_users_reply, redis_db=redis_db, cms_auth=cms_auth, ya_api_token=ya_api_token))
    )

    updater.start_polling()


if __name__ == '__main__':
    main()
