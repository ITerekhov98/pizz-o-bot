import re
import time
import json
from urllib import response
import requests


class CmsAuthentication:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_expiration = 0
        self._token = ''

    def get_access_token(self):
        if self.token_expiration - time.time() >= 60:
            return self._token
        url = 'https://api.moltin.com/oauth/access_token'
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        token_details = response.json()
        self.token_expiration = token_details['expires']
        self._token = token_details['access_token']
        return self._token


def create_product(token: str, product_details):
    url = 'https://api.moltin.com/v2/products'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    json_data = {
        'data': {
            'type': 'product',
            'name': product_details['name'],
            'slug': f"product-item-{product_details['id']}",
            'sku': str(product_details['id']),
            'description': product_details['description'],
            'manage_stock': False,
            'price': [
                {
                    'amount': product_details['price'],
                    'currency': 'RUB',
                    'includes_tax': True,
                },
            ],
            'status': 'live',
            'commodity_type': 'physical',
        },
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()

    return response.json()

def create_image(token, product_details):
    url = 'https://api.moltin.com/v2/files'
    headers = {
        'Authorization': f'Bearer {token}',    
    }
    files = {
        'file_location': (None, product_details['product_image']['url']),
    }
    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()

    return response.json()


def link_picture_with_product(token, product_id, image_id):
    url = f'https://api.moltin.com/v2/products/{product_id}/relationships/main-image'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    json_data = {
        'data': {
            'type': 'main_image',
            'id': image_id,
        },
    }
    response = requests.post(url ,headers=headers, json=json_data)
    response.raise_for_status()

    return response.json()

def delete_product(token, product_id):
    url = f"https://api.moltin.com/v2/products/{product_id}"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.delete(url, headers=headers)
    response.raise_for_status()

    return 


def get_all_products(token):
    url = f"https://api.moltin.com/v2/products"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.json()


def create_products_from_json(token, path_to_json):
    with open(path_to_json, 'r') as f:
        menu_items = json.loads(f.read())
    
    for item in menu_items:
        created_product_details = create_product(token, item)
        loaded_image_details = create_image(token, item)
        result = link_picture_with_product(token, created_product_details['data']['id'], loaded_image_details['data']['id'])
    
    return get_all_products(token)

def create_flow(token, flow_details):
    url = 'https://api.moltin.com/v2/flows'    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    json_data = {
        'data': {
            'type': 'flow',
            'name': flow_details['name'],
            'slug': flow_details['slug'],
            'description': flow_details['description'],
            'enabled': True,
        },
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()

    return response.json()

def create_field_for_flow(token, field_details, flow_id):
    url = 'https://api.moltin.com/v2/fields'
    headers = {
        'Authorization': f'Bearer {token}'
    }  
    json_data = {
        'data': {
            'type': 'field',
            'name': field_details['name'],
            'slug': field_details['slug'],
            'field_type': field_details['type'],
            'description': field_details['description'],
            'required': False,
            'enabled': True,
            'relationships': {
                'flow': {
                    'data': {
                        'type': 'flow',
                        'id': flow_id,
                    },
                },
            },
        },
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()

    return response.json()


def create_entry_for_flow(token, entry_details, flow_slug):
    url = f"https://api.moltin.com/v2/flows/{flow_slug}/entries"
    headers = {
        'Authorization': f'Bearer {token}'
    } 
    json_data = {
        'data': {
            "type": "entry",
            'longitude': float(entry_details['coordinates']['lon']), 
            'latitude': float(entry_details['coordinates']['lat']),
            'alias': entry_details['alias'],
            'address': entry_details['address']['full']
        }
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()

    return response.json()


def create_entries_from_json(token, path_to_json, flow_slug):
    with open(path_to_json, 'r') as f:
        entries = json.loads(f.read())

    resulted_batch = []
    for entry in entries:
        created_entry = create_entry_for_flow(token, entry, flow_slug)
        resulted_batch.append(created_entry['data'])
    return resulted_batch


def get_cart_items(token: str, user_id: str):
    url = f'https://api.moltin.com/v2/carts/{user_id}/items'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_cart(token: str, user_id: str):
    url = f'https://api.moltin.com/v2/carts/{user_id}'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_product_by_id(token: str, product_id: str):
    url = f'https://api.moltin.com/v2/products/{product_id}'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_photo_by_id(token: str, photo_id: str):
    url = f'https://api.moltin.com/v2/files/{photo_id}'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()['data']['link']['href']


def remove_product_from_cart(token: str, user_id: str, product_id: str):
    url = f'https://api.moltin.com/v2/carts/{user_id}/items/{product_id}'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return


def get_or_create_customer(token: str, user_id: str, user_email: str):
    url = 'https://api.moltin.com/v2/customers'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    params = {
        'filter': f'eq(email,{user_email})'
    }
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    customer_info = response.json()
    if customer_info['data']:
        return customer_info, False

    json_data = {
        'data': {
            'type': 'customer',
            'name': user_id,
            'email': user_email
        }
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()
    return response.json(), True


def add_product_to_cart(token: str, user_id: str, product_id: str, quantity: int):
    url = f'https://api.moltin.com/v2/carts/{user_id}/items'
    headers = {
        'Authorization': f'Bearer {token}',
        'X-MOLTIN-CURRENCY': 'RUB',
    }
    json_data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': quantity
        }
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()
    return response.json()


def get_all_entries(token, flow_slug='pizza-shop'):
    url = f'https://api.moltin.com/v2/flows/{flow_slug}/entries'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()   

def save_customer_coords(token, coords, customer_id):
    lat, lon = map(float, coords)
    url = "https://api.moltin.com/v2/flows/customer-address/entries"
    headers = {
        'Authorization': f'Bearer {token}'
    } 
    json_data = {
        'data': {
            "type": "entry",
            'longitude': lon, 
            'latitude': lat,
            'customer-id': str(customer_id)
        }
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()

    return response.json()

def get_address(token, entry_id):
    url = f"https://api.moltin.com/v2/flows/customer-address/entries/{entry_id}"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()