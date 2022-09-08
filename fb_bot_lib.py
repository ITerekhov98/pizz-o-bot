from urllib.parse import urljoin
from cms_lib import get_all_products, get_photo_by_id


def split_products_to_batches(products, batch_size):
    for index in range(0, len(products), 8):
        yield products[index: index + batch_size]


def get_menu(cms_token, STATIC_URL):
    products = list(split_products_to_batches(get_all_products(cms_token)['data'], 5))[0]
    menu_items = [
        {'title': 'Меню',
        'image_url': urljoin(STATIC_URL, 'logo.jpg'),
         'subtitle': 'Выбираем пиццку' 
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