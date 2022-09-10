from urllib.parse import urljoin
from cms_lib import get_photo_by_id, get_cart, get_products_by_category_id, get_all_categories, get_cart_items
from dataclasses import dataclass


MAX_ITEMS_COUNT_IN_MESSAGE = 10

@dataclass
class ResponseObject:
    sender_id: str
    recipient_id: str
    message_text: str = ''
    postback_payload: str = ''


def get_menu(cms_token, static_url, category_id):
    categories = get_all_categories(cms_token)['data']

    for index, category in enumerate(categories):
        if category['name'] == 'front_page':
            front_page_id = categories.pop(index)['id']
            if not category_id:
                category_id = front_page_id
            break
    products = get_products_by_category_id(cms_token, category_id)['data']

    menu_items = [
        {'title': 'Меню',
        'image_url': urljoin(static_url, 'logo.jpg'),
         'subtitle': 'Выбираем пиццку',
         'buttons': [
                {
                "type":"postback",
                "title":"Корзина",
                "payload":"cart",
            },
                {
                "type":"postback",
                "title":"Акции",
                "payload":"promotions",
            },
                {
                "type":"postback",
                "title":"Оформить заказ",
                "payload":"order",
            },
            ]
        }
    ]
    menu_items.extend([
        {"title": f"{product['name']} ({product['price'][0]['amount']} Р)",
            "image_url": get_photo_by_id(
                cms_token, product['relationships']['main_image']['data']['id']
            ),
            "subtitle": product['description'],
            "buttons": [{
                "type":"postback",
                "title":"Добавить в корзину",
                "payload":f"add_{product['id']}",
            }]}
        for product in products]
    )
    if len(menu_items) >= MAX_ITEMS_COUNT_IN_MESSAGE:
        menu_items = menu_items[:MAX_ITEMS_COUNT_IN_MESSAGE-1]
    menu_items.append(
        {'title': 'Не нашли нужную пиццу? Просмотрите наши подборки!',
        'image_url': urljoin(static_url, 'pizzas2.jpg'),
        'buttons': [{
            "type":"postback",
            "title": category['name'],
            "payload": f'category_{category["id"]}',
            } for category in categories]
        }
    )
    menu = {
        'attachment': {
            'type':'template',
            'payload':{
                'template_type':'generic',
                'elements': menu_items
            }
        }
    }
    return menu

def get_user_cart(cms_token, static_url, user_id):
    text = ''
    cart_info = get_cart(cms_token, user_id)['data']
    total_amount = float(
        cart_info['meta']['display_price']['with_tax']['formatted']
    ) * 100
    text += f"К оплате: {total_amount}"

    menu_items = [
            {'title': text,
            'image_url': urljoin(static_url, 'cart.jpg'),
            'buttons': [
                    {
                    "type":"postback",
                    "title":"Самовывоз",
                    "payload":"pickup",
                },
                    {
                    "type":"postback",
                    "title":"Доставка",
                    "payload":"delivery",
                },
                    {
                    "type":"postback",
                    "title":"Меню",
                    "payload":"menu",
                },
                ]
            }
        ]
    menu = {
        'attachment': {
            'type':'template',
            'payload':{
                'template_type':'generic',
                'elements': menu_items
            }
        }
    }
    return menu
