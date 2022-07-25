## Tg-Бот с приёмом платежей для пиццерии

### Установка
Скачайте код из репозитория, перейдите в каталог и установите необходимые зависимости:
```
pip3 install -r requirements.txt
```
### Настройка
В каталоге с кодом создайте файл `.env` и заполните его в формате `Ключ=значение` следующими данными:
- ELASTIC_PATH_CLIENT_ID - ID вашего профиля в [Moltin](https://www.elasticpath.com/)
- ELASTIC_PATH_CLIENT_SECRET - secret key вашего профиля в [Moltin](https://www.elasticpath.com/)
- TG_BOT_TOKEN - токен вашего tg бота
- REDIS_HOST - данные вашей базы данных в redis, используется для хранения промежуточных данных.
- REDIS_PORT
- REDIS_PASSWORD
- YANDEX_API_TOKEN - токен для [геокодера яндекс](https://yandex.ru/dev/maps/geocoder/). Нужен для определения координат по присланному от клиента адресу
- TG_PAYMENT_TOKEN - токен для приёма платежей в телеграмм, можно получить через [BotFather](https://t.me/BotFather)
- FEEDBACK_DELAY - задержка в секундах для отправки клиенту сообщения обратной связи

### Запуск

Запустите бота командой:
```
python tg_bot.py
```

Названия пицц, их описания и фото взяты из меню сети пиццерий [dodopizza](https://dodopizza.ru/) в целях визуализации функциональности бота.
