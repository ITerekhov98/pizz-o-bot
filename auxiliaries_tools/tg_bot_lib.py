import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from auxiliaries_tools.cms_lib import get_all_products
                 

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


def get_delivery_keyboard(nearest_pizzeria, order_amount):
    keyboard = [
        [InlineKeyboardButton('Самовывоз', callback_data=f'pickup {order_amount}')]
    ]
    if nearest_pizzeria['distance'] <= 20:
        keyboard.append(
            [InlineKeyboardButton('Доставка', callback_data=f"delivery {order_amount}")]
        )
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup