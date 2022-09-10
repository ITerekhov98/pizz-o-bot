import os

import requests
from flask import Flask, request
from environs import Env
import redis
from cms_lib import CmsAuthentication, get_all_products, get_photo_by_id, add_product_to_cart, get_cart_items
from fb_bot_lib import get_menu, ResponseObject, get_user_cart


app = Flask(__name__)

@app.route('/', methods=['GET'])
def verify():
    """
    При верификации вебхука у Facebook он отправит запрос на этот адрес. На него нужно ответить VERIFY_TOKEN.
    """
    
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == app.config.get('fb_verify_token'):
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return 'Hi', 200
    


@app.route('/', methods=['POST'])
def webhook():
    """
    Основной вебхук, на который будут приходить сообщения от Facebook.
    """
    db = app.config.get('db')
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                response_details = ResponseObject(
                    sender_id = messaging_event["sender"]["id"],
                    recipient_id = messaging_event["recipient"]["id"],
                )
                if messaging_event.get("message"):
                    response_details.message_text = messaging_event["message"]["text"]
                elif messaging_event.get("postback"):
                    response_details.postback_payload = messaging_event["postback"]["payload"]
                handle_users_reply(response_details, db)
    return "ok", 200


def handle_users_reply(response_details: ResponseObject, db):
    
    states_functions = {
        'START': handle_start,
        'HANDLE_MENU': handle_menu,
    }
    recorded_state = db.get(response_details.sender_id)
    if not recorded_state or recorded_state not in states_functions.keys():
        user_state = "START"
    else:
        user_state = recorded_state
    if response_details.message_text == "/start":
        user_state = "START"
    state_handler = states_functions[user_state]
    next_state = state_handler(response_details)
    db.set(response_details.sender_id, next_state)


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


def handle_start(response_details: ResponseObject, category_id=''):
    cms_token = app.config.get('cms_auth').get_access_token()
    static_url = app.config.get('static_url')
    menu = get_menu(
            cms_token=cms_token, 
            static_url=static_url, 
            category_id=category_id,
    )
    send_response(app.config.get('fb_token'), response_details.sender_id, menu)
    return 'HANDLE_MENU'


def send_user_cart(response_details: ResponseObject):
    cms_token = app.config.get('cms_auth').get_access_token()
    static_url = app.config.get('static_url')
    cart = get_user_cart(cms_token, static_url, response_details.sender_id)
    send_response(app.config.get('fb_token'), response_details.sender_id, cart)
    return 'HANDLE_MENU'


def handle_menu(response_details: ResponseObject):
    cms_token = app.config.get('cms_auth').get_access_token()
    action = response_details.postback_payload
    if not action:
        return 'HANDLE_MENU'
    
    if action.split('_')[0] == 'add':
        product_id = action.split('_')[1]
        add_product_to_cart(
            cms_token,
            response_details.sender_id,
            product_id,
            1
        )
        send_message(
            response_details.sender_id,
            'Товар добавлен в корзину!'
        )

    elif action.split('_')[0] == 'category':
        category_id = action.split('_')[1]
        return handle_start(response_details, category_id)

    elif action == 'cart':
        return send_user_cart(response_details)
    elif action == 'menu':    
        return handle_start(response_details)
    return 'HANDLE_MENU'


def send_message(recipient_id, message_text):
    params = {"access_token": app.config.get('fb_token')}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    }
    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def create_app():
    env = Env()
    env.read_env()
    client_id = env.str('ELASTIC_PATH_CLIENT_ID'),
    client_secret = env.str('ELASTIC_PATH_CLIENT_SECRET')
    cms_auth = CmsAuthentication(client_id, client_secret)
    app.config.update(
        cms_auth = cms_auth,
        fb_token = env.str("PAGE_ACCESS_TOKEN"),
        fb_verify_token = env.str("VERIFY_TOKEN"),
        static_url = env.str("STATIC_URL"),
        db = redis.StrictRedis(
            host=env.str('REDIS_HOST'),
            port=env.int('REDIS_PORT'),
            password=env.str('REDIS_PASSWORD'),
            charset="utf-8",
            decode_responses=True,
        )
    )
    return app

if __name__ == '__main__':
    create_app = create_app()
    create_app.run()
else:
    gunicorn_app = create_app()
