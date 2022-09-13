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

## Реализация для Facebook

В отличие от телеграма, для взаимодействия с которым используется технология long-polling и достаточно поддерживать открытое соединение чтобы обеспечить работу бота, facebook требует постоянно работающий веб-сервис (web hook) на который он будет присылать события для бота. Так как сервис обязательно должен работать по защищённому протоколу https, а также желательно наличие web-сервера для раздачи статики, ниже приведена краткая инструкция по развёртыванию приложения с использованием flask, gunicorn и nginx.

- Создайте приложение бота и получите токен у facebook. [Инструкция](https://dvmn.org/encyclopedia/api-docs/how-to-get-facebook-api/)

- Скачиваем репозиторий, если этого ещё не сделали, устанавливаем нужные зависимости и библиотеки:
```
pip3 install -r requirements.txt
```
- Создаём виртуальное окружения для проекта:
```
python3 -m venv env
```
- Помимо указанных в предыдущем пункте настроек, понадобится ещё несколько:
  + FB_ACCESS_TOKEN - токен facebook который вы получили в первом шаге.
  + VERIFY_TOKEN - токен для верификации, вы укажете его при создании страницы приложения.
  + STATIC_URL - путь к папке со статикой.

- Создаём служебный файл systemd, для автоматического запуска и работы приложения:
  + в директории /etc/systemd/system создайте файл `fb_bot.service` и заполните следующим образом:
  ```
  [Unit]
  Description=MyUnit
  After=syslog.target
  After=network.target

  [Service]
  WorkingDirectory= {Рабочая директория проекта}
  ExecStart={Рабочая директория проекта}/env/bin/gunicorn --bind 127.0.0.1:5000 fb_bot:gunicorn_app

  [Install]
  WantedBy=multi-user.target
  ```
  + Далее активируем юнит и добавим его в автозапуск при старте системы:
  ```
  systemctl start fb_bot.service
  systemctl enable fb_bot.service
  ```
- Установим и настроим nginx:
  + `apt install nginx`
  + Открывам директорию `/etc/nginx/sites-available/` создаём файл `fb_bot`, заполняем:
  ```
  server {
    server_name {ваш домен};

    location / {
        include proxy_params;
        proxy_pass http://127.0.0.1:5000;
    }

    location /static/ {
        alias {Путь до папки с статикой}/static/;
    }
  }
  ```
  + Активируем созданную конфигурацию:
  ```
  ln -s /etc/nginx/sites-available/fb_bot /etc/nginx/sites-enabled
  systemctl restart nginx
  ```
- Получим сертификат ssl:
  + `apt install certbot`
  + `certbot --nginx -d {Ваш домен}`
  + Следуем инструкциям certbot
  
Вебхук поднят и готов принимать уведомления от facebook.
  
  
  
  
  
  
  
  
