from functools import partial

import redis
from email_validate import validate
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, \
                         Filters, CallbackQueryHandler

from cms_lib import CmsAuthentication, get_all_products, get_product_by_id, \
                 get_photo_by_id, add_product_to_cart, get_cart_items, \
                 get_cart, remove_product_from_cart, get_or_create_customer


def split_products_to_batches(products, batch_size):
    for index in range(0, len(products), 8):
        yield products[index: index + batch_size]


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
            text='Введите, пожалуйста ваш email, с вами свяжутся рыбные специалисты',
        )
        return 'WAITING_EMAIL'

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


def handle_users_reply(update, context, redis_db, cms_auth):
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
        'WAITING_EMAIL': waiting_email
    }
    state_handler = states_functions[user_state]
    cms_token = cms_auth.get_access_token()
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
    cms_auth = CmsAuthentication(client_id, client_secret)
    updater = Updater(env.str('TG_BOT_TOKEN'))
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(
        partial(handle_users_reply, redis_db=redis_db, cms_auth=cms_auth))
    )
    dispatcher.add_handler(CommandHandler(
        'start',
        partial(handle_users_reply, redis_db=redis_db, cms_auth=cms_auth))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.text,
        partial(handle_users_reply, redis_db=redis_db, cms_auth=cms_auth))
    )

    updater.start_polling()


if __name__ == '__main__':
    main()
