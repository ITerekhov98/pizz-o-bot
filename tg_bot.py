from functools import partial

import redis
from telegram import LabeledPrice
from environs import Env
from geopy import distance
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, \
                         Filters, CallbackQueryHandler, PreCheckoutQueryHandler

from cms_lib import CmsAuthentication, get_product_by_id, \
                 get_photo_by_id, add_product_to_cart, get_cart_items, \
                 get_cart, remove_product_from_cart, get_all_entries, \
                 save_customer_coords, get_customer_address, clear_cart

from tg_bot_lib import fetch_coordinates, get_menu_keyboard, get_delivery_keyboard


def send_user_cart(update, context, cms_token: str):
    query = update.callback_query
    keyboard = []
    text = ''
    cart_items = get_cart_items(cms_token, update.effective_chat.id)
    product_template = '{}\r\n{}\r\n{} пицц в корзине на сумму {}\r\n\r\n'
    for product in cart_items['data']:
        amount = float(
            product['meta']['display_price']['with_tax']['value']['formatted']
        ) * 100
        text += product_template.format(
            product['name'],
            product['description'],
            product['quantity'],
            amount
        )
        keyboard.append(
            [InlineKeyboardButton(
                f" Удалить {product['name']}",
                callback_data=product['id']), ]
        )
    cart_info = get_cart(cms_token, update.effective_chat.id)['data']
    total_amount = float(
        cart_info['meta']['display_price']['with_tax']['formatted']
    ) * 100
    text += f"К оплате: {total_amount}"

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
        batch = int(query.data.split()[-1])
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


def calculate_delivery(update, context, cms_token, current_pos, redis_db):
    pizzerias = get_all_entries(cms_token)['data']
    for pizzeria in pizzerias:
        pizzeria_distance = distance.distance(
            current_pos,
            (pizzeria['latitude'], pizzeria['longitude'])
        ).km
        pizzeria['distance'] = pizzeria_distance

    nearest_pizzeria = min(pizzerias, key=lambda x: x['distance'])
    if nearest_pizzeria['distance'] <= 0.5:
        delivery_price = 0
        distance_in_meters = (nearest_pizzeria['distance'] * 1000)
        text = f"""Ближайшая пиццерия всего в {distance_in_meters:.4f} метрах от вас! 
        Заберёте сами, или вам принести? Это бесплатно"""
    elif nearest_pizzeria['distance'] <= 5:
        delivery_price = 100
        text = f'Доставка  к вам будет стоить {delivery_price} рублей. Везём или заберёте сами?'
    elif nearest_pizzeria['distance'] <= 20:
        delivery_price = 300
        text = f'Доставка  к вам будет стоить {delivery_price} рублей. Везём или заберёте сами?'
    else:
        delivery_price = 0
        text = f"""Ближайшая пиццерия находится в {nearest_pizzeria['distance']:.4f} километрах от вас. 
        К сожалению, так далеко мы не сможем доставить.Заберёте сами?"""

    order_amount = get_cart(
        cms_token,
        update.effective_chat.id
    )['data']['meta']['display_price']['with_tax']['amount']
    order_amount += delivery_price
    address_entry_id = save_customer_coords(
        cms_token,
        current_pos,
        update.effective_chat.id
    )['data']['id']
    redis_db.set(
        f"delivery {update.effective_chat.id}",
        f"{address_entry_id} {nearest_pizzeria['delivery-chat-id']}"
    )
    reply_markup = get_delivery_keyboard(nearest_pizzeria, order_amount)
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup
    )
    return 'HANDLE_PAYMENT'


def handle_payment(update, context, cms_token, redis_db, payment_token):
    chat_id = update.effective_chat.id
    query = update.callback_query
    query.answer()
    shipping_method, price = query.data.split()
    shipping_details = redis_db.get(f'delivery {chat_id}')
    redis_db.set(f'delivery {chat_id}', f'{shipping_details} {shipping_method}')

    title = "Платёж за пиццку"
    description = "Платёж за пиццку"
    payload = "Custom-Payload"
    start_parameter = "test-payment"
    currency = "RUB"
    prices = [LabeledPrice("Test", int(price) * 100)]

    context.bot.sendInvoice(
        chat_id,
        title,
        description,
        payload,
        payment_token,
        start_parameter,
        currency,
        prices
    )
    return 'WAITING_PAYMENT'


def precheckout_callback(update, context):
    query = update.pre_checkout_query
    # check the payload, is this from your bot?
    if query.invoice_payload != 'Custom-Payload':
        # answer False pre_checkout_query
        context.bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=False,
            error_message="Something went wrong..."
        )
    else:
        context.bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=True
        )


def handle_waiting(update, context, cms_token, ya_api_key, redis_db):
    if update.message.location:
        current_pos = (update.message.location.latitude, update.message.location.longitude)
    else:
        address = update.message.text
        current_pos = fetch_coordinates(ya_api_key, address)
    if not current_pos:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Не нашел такого',
        )
        return 'HANDLE_WAITING'
    return calculate_delivery(update, context, cms_token, current_pos, redis_db)


def callback_alarm(context):
    context.bot.send_message(
        chat_id=context.job.context,
        text='''
        Приятного аппетита! *место для рекламы*
        *сообщение что делать если пицца не пришла*'''
    )


def successful_payment_callback(update, context, cms_token, redis_db, feedback_delay):
    chat_id = update.effective_chat.id
    shipping_details = redis_db.get(f'delivery {chat_id}')
    address_entry_id, pizzeria_chat, shipping_method = shipping_details.split()

    if shipping_method == 'pickup':
        context.bot.send_message(
            chat_id=chat_id,
            text='Будем ждать',
        )
    elif shipping_method == 'delivery':
        coords = get_customer_address(cms_token, address_entry_id)['data']
        context.bot.send_location(
            chat_id=pizzeria_chat,
            latitude=coords['latitude'],
            longitude=coords['longitude']
        )
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Ваш заказ принят в обработку!',
        )
        context.job_queue.run_once(callback_alarm, feedback_delay, context=chat_id)
    clear_cart(cms_token, chat_id)
    redis_db.set(chat_id, 'START')
    return


def handle_users_reply(update, context, redis_db, cms_auth, ya_api_token='', payment_token=''):
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    elif update.edited_message:
        user_reply = update.edited_message
        chat_id=update.effective_chat.id,
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
        'HANDLE_WAITING': handle_waiting,
        'HANDLE_PAYMENT': handle_payment
    }
    state_handler = states_functions[user_state]
    cms_token = cms_auth.get_access_token()
    if user_state == 'HANDLE_WAITING':
        next_state = state_handler(
            update,
            context,
            cms_token,
            ya_api_token,
            redis_db
        )
    elif user_state == 'HANDLE_PAYMENT':
        next_state = state_handler(
            update,
            context,
            cms_token,
            redis_db,
            payment_token
        )
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
    payment_token = env.str('TG_PAYMENT_TOKEN')
    feedback_delay=env.int('FEEDBACK_DELAY', 3600)
    cms_auth = CmsAuthentication(client_id, client_secret)
    updater = Updater(env.str('TG_BOT_TOKEN'))
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(
        partial(
            handle_users_reply,
            redis_db=redis_db,
            cms_auth=cms_auth,
            payment_token=payment_token
        ),
        pass_job_queue=True)
    )
    dispatcher.add_handler(CommandHandler(
        'start',
        partial(handle_users_reply, redis_db=redis_db, cms_auth=cms_auth))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.text,
        partial(
            handle_users_reply,
            redis_db=redis_db,
            cms_auth=cms_auth,
            ya_api_token=ya_api_token
        ))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.location,
        partial(
            handle_users_reply,
            redis_db=redis_db,
            cms_auth=cms_auth,
            ya_api_token=ya_api_token,
        ))
    )
    dispatcher.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dispatcher.add_handler(
        MessageHandler(
            Filters.successful_payment,
            partial(
                successful_payment_callback,
                redis_db=redis_db,
                cms_token=cms_auth.get_access_token(),
                feedback_delay=feedback_delay
            )
        )
    )
    updater.start_polling()


if __name__ == '__main__':
    main()
