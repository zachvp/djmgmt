'''
Subsonic client
Primary functionality
    * startScan
    * report when scan is finished
'''

'''
Request steps
    URL encode request params
    
'''

from urllib.parse import urlencode
from requests import Response
import requests
import hashlib
import random
import string
import json
import xml.etree.ElementTree as ET
import keyring
import argparse
import logging

from . import common

def parse_args(valid_endpoints: set[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('endpoint', type=str, help=f"Which endpoint to call. One of: '{valid_endpoints}'")
    
    args = parser.parse_args()
    
    if args.endpoint not in valid_endpoints:
        parser.error(f"invalid function: '{args.function}")
    
    return args

def create_token(password: str, salt: str) -> str:
    return hashlib.md5((password + salt).encode()).hexdigest()

def create_salt(length: int) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def create_query(params: dict[str, str] = {}) -> str:
    # construct query params
    password = keyring.get_password('navidrome_client', 'api_client')
    assert password is not None, f'unable to fetch password'
    salt = create_salt(12)
    base_params = {
        'u': 'api_client',                      # user
        't': f'{create_token(password, salt)}', # token
        's': f'{salt}',                         # salt
        'v': '1.16.1',                          # version
        'c': 'corevega_client'                  # client id
    }
    # add any params
    for key, value in params.items():
        base_params[key] = value
    return urlencode(base_params)

def call_endpoint(endpoint: str, params: dict[str, str] = {}) -> Response:
    # call the endpoint
    query_string = create_query(params)
    # base_url = f"http://corevega.local:4533/rest"
    base_url = f"https://corevega.net/rest"
    url = f"{base_url}/{endpoint}.view?{query_string}"
    logging.debug(f'send request: {url}')
    return requests.get(url)

def get_response_content(response: Response) -> dict[str, str]:
    content = ET.fromstring(response.text)
    if len(content) > 0:
        return content[0].attrib
    else:
        return content.attrib

def handle_response(response: Response, endpoint: str) -> dict[str, str] | None: # todo: determine endpoint from response
    if response.status_code == 200:
        content = get_response_content(response)
        logging.debug(f"successful call to '{endpoint}'\n{json.dumps(content, indent=2)}")
        
        return content
    else:
        '''
        0 	A generic error.
        10 	Required parameter is missing.
        20 	Incompatible Subsonic REST protocol version. Client must upgrade.
        30 	Incompatible Subsonic REST protocol version. Server must upgrade.
        40 	Wrong username or password.
        41 	Token authentication not supported for LDAP users.
        50 	User is not authorized for the given operation.
        60 	The trial period for the Subsonic server is over. Please upgrade to Subsonic Premium. Visit subsonic.org for details.
        70 	The requested data was not found.
        '''
        logging.error(f'error: {response.json()}')
        return None

class API:
    PING = 'ping'
    START_SCAN = 'startScan'
    GET_SCAN_STATUS = 'getScanStatus'
    
    ENDPOINTS: set[str] = {PING, START_SCAN, GET_SCAN_STATUS}
    
    RESPONSE_STATUS = 'status'
    RESPONSE_SCAN_STATUS = 'scanning'

if __name__ == '__main__':
    # setup
    common.configure_log(logging.DEBUG, path=__name__)
    
    # DEV testing
    endpoint = API.PING
    # main_response = call_endpoint(endpoint, { 'fullScan': 'true' })
    main_response = call_endpoint(endpoint)
    handle_response(main_response, endpoint)
    
    endpoint = API.GET_SCAN_STATUS
    # main_response = call_endpoint(endpoint, { 'fullScan': 'true' })
    main_response = call_endpoint(endpoint)
    handle_response(main_response, endpoint)
    
    
    # exit()
    
    # script_args = parse_args(API.ENDPOINTS)
    # response = call_endpoint(script_args.endpoint, {})
