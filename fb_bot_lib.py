from urllib.parse import urljoin
from cms_lib import get_all_products, get_photo_by_id, get_category_id_by_name, get_products_by_category_id, get_all_categories
import sys

def split_products_to_batches(products, batch_size):
    for index in range(0, len(products), 8):
        yield products[index: index + batch_size]


def get_menu(cms_token, STATIC_URL):
    categories = get_all_categories(cms_token)['data']
    for index, category in enumerate(categories):
        if category['name'] == 'front_page':
            front_page_category_id = categories.pop(index)['id']
            break

    products = get_products_by_category_id(cms_token, front_page_category_id)['data']
    menu_items = [
        {'title': 'Меню',
        'image_url': urljoin(STATIC_URL, 'logo.jpg'),
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
                "payload":product["id"],
            }]}
        for product in products]
    )
    menu_items.append(
        {'title': 'Не нашли нужную пиццу? Просмотрите наши подборки!',
        'image_url': urljoin(STATIC_URL, 'pizzas2.jpg'),
        'buttons': [{
            "type":"postback",
            "title": category['name'],
            "payload": category['id'],
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