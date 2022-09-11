import json

import requests
from urllib.parse import urljoin
from dataclasses import dataclass

from auxiliaries_tools.cms_lib import (
    get_photo_by_id,
    get_cart,
    get_products_by_category_id,
    get_all_categories,
    get_cart_items
)


MAX_ITEMS_COUNT_IN_MESSAGE = 10

@dataclass
class ResponseObject:
    sender_id: str
    recipient_id: str
    message_text: str = ''
    postback_payload: str = ''


def update_menu(cms_token, static_url, db):
    categories = get_all_categories(cms_token)['data']
    for category in categories:
        category_name = category['name']
        category_id = category['id']
        other_categories = [
            product for product in categories if product['id'] != category_id
        ]
        menu = json.dumps(
            get_menu(cms_token, static_url, category_id, other_categories)
        )
        if category_name == 'front_page':
            db.set(f'menu_{category_name}', menu)
        else:
            db.set(f'menu_{category_id}', menu)


def get_menu(cms_token, static_url, category_id, categories):

    products = get_products_by_category_id(cms_token, category_id)['data']

    menu_items = [{
        'title': 'Меню',
        'image_url': urljoin(static_url, 'logo.jpg'),
        'subtitle': 'Выбираем пиццку',
        'buttons': [
            {
                "type": "postback",
                "title": "Корзина",
                "payload": "cart",
            },
            {
                "type": "postback",
                "title": "Акции",
                "payload": "promotions",
            },
            {
                "type": "postback",
                "title": "Оформить заказ",
                "payload": "order",
            },
            ]}]
    menu_items.extend([
        {"title": f"{product['name']} ({product['price'][0]['amount']} Р)",
            "image_url": get_photo_by_id(
                cms_token, product['relationships']['main_image']['data']['id']
            ),
            "subtitle": product['description'],
            "buttons": [{
                "type": "postback",
                "title": "Добавить в корзину",
                "payload": f"add_{product['id']}",
            }]}
        for product in products]
    )
    if len(menu_items) >= MAX_ITEMS_COUNT_IN_MESSAGE:
        menu_items = menu_items[:MAX_ITEMS_COUNT_IN_MESSAGE-1]
    menu_items.append({
        'title': 'Не нашли нужную пиццу? Просмотрите наши подборки!',
        'image_url': urljoin(static_url, 'pizzas2.jpg'),
        'buttons': [
            {
                "type": "postback",
                "title": category['name'],
                "payload": f'category_{category["id"]}',
            }
            for category in categories]
        }
    )
    menu = {
        'attachment': {
            'type': 'template',
            'payload': {
                'template_type': 'generic',
                'elements': menu_items
            }
        }
    }
    return menu


def get_user_cart(cms_token, static_url, user_id):
    cart_info = get_cart(cms_token, user_id)['data']
    total_amount = float(
        cart_info['meta']['display_price']['with_tax']['formatted']
    ) * 100
    title = f"К оплате: {total_amount}"
    cart_items = get_cart_items(cms_token, user_id)['data']

    menu_items = [{
        'title': title,
        'image_url': urljoin(static_url, 'cart.jpg'),
        'buttons': [
            {
                "type": "postback",
                "title": "Самовывоз",
                "payload": "pickup",
            },
            {
                "type": "postback",
                "title": "Доставка",
                "payload": "delivery",
            },
            {
                "type": "postback",
                "title": "Меню",
                "payload": "menu",
            },
        ]}]
    menu_items.extend(
        [{
            "title": f"{product['name']} ({product['quantity']} шт "
                     f"на {product['meta']['display_price']['with_tax']['value']['amount']} р)",
            "image_url": product['image']['href'],
            "subtitle": product['description'],
            "buttons": [
                {
                    "type": "postback",
                    "title": "Добавить ещё одну",
                    "payload": f"add_{product['product_id']}",
                },
                {
                    "type": "postback",
                    "title": "Убрать из корзины",
                    "payload": f"remove_{product['id']}",
                },
            ]} for product in cart_items]
    )
    menu = {
        'attachment': {
            'type': 'template',
            'payload': {
                'template_type': 'generic',
                'elements': menu_items
            }
        }
    }
    return menu


def send_response(fb_token, recipient, message):
    params = {"access_token": fb_token}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient
        },
        "message": message
    }
    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()
