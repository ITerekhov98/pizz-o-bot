from environs import Env

from cms_lib import CmsAuthentication, create_field_for_flow

import json 

def main():
    env = Env()
    env.read_env()
    client_id = env.str('ELASTIC_PATH_CLIENT_ID')
    client_secret = env.str('ELASTIC_PATH_CLIENT_SECRET')
    cms_auth = CmsAuthentication(client_id, client_secret)
    cms_token = cms_auth.get_access_token()


    

if __name__ == '__main__':
    main()