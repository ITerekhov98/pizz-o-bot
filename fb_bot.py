import os

import requests
from flask import Flask, request
from environs import Env

from cms_lib import CmsAuthentication, get_all_products, get_photo_by_id
from fb_bot_lib import get_menu

app = Flask(__name__)
env = Env()
env.read_env()
client_id = env.str('ELASTIC_PATH_CLIENT_ID')
client_secret = env.str('ELASTIC_PATH_CLIENT_SECRET')
cms_auth = CmsAuthentication(client_id, client_secret)
cms_token = cms_auth.get_access_token()
FACEBOOK_TOKEN = env.str("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = env.str("VERIFY_TOKEN")
STATIC_URL = env.str("STATIC_URL")


@app.route('/', methods=['GET'])
def verify():
    """
    При верификации вебхука у Facebook он отправит запрос на этот адрес. На него нужно ответить VERIFY_TOKEN.
    """
    
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return 'Hi there!', 200
    


@app.route('/', methods=['POST'])
def webhook():
    """
    Основной вебхук, на который будут приходить сообщения от Facebook.
    """
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    # recipient_id = messaging_event["recipient"]["id"]
                    # message_text = messaging_event["message"]["text"]
                    send_menu(sender_id)
    return "ok", 200


def send_menu(recipient_id):
    params = {"access_token": FACEBOOK_TOKEN}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": get_menu(cms_token, STATIC_URL)
    }
    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()



def send_message(recipient_id, message_text):
    params = {"access_token": FACEBOOK_TOKEN}
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

if __name__ == '__main__':
    app.run(debug=True)
