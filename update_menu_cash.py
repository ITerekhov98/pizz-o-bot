from cms_lib import CmsAuthentication
from environs import Env
from fb_bot_lib import update_menu
import redis


def main():
    env = Env()
    env.read_env()
    client_id = env.str('ELASTIC_PATH_CLIENT_ID'),
    client_secret = env.str('ELASTIC_PATH_CLIENT_SECRET')
    cms_auth = CmsAuthentication(client_id, client_secret)
    cms_token = cms_auth.get_access_token()
    static_url = env.str("STATIC_URL")
    db = redis.StrictRedis(
            host=env.str('REDIS_HOST'),
            port=env.int('REDIS_PORT'),
            password=env.str('REDIS_PASSWORD'),
            charset="utf-8",
            decode_responses=True,
    )
    update_menu(cms_token, static_url, db)

if __name__ == '__main__':
    main()