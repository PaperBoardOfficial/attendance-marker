import http
import json
import os
import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
from bs4 import BeautifulSoup
from base64 import b64decode, b64encode


def lambda_handler(event, context):
    error_message = ""
    if os.getcwd().endswith('tests'):
        file_path = '../src/config.json'
    else:
        file_path = 'src/config.json'
    with open(file_path, "r") as f:
        file_data = json.loads(f.read())
    for credentials in file_data['details']:
        with requests.session() as session:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0',
                }
                session.headers.update(headers)
                view_state = get_view_state(session)
                login(session, credentials, view_state)
                user_details = get_user_details(session)
                attendance_details = get_attendance_details(session, user_details)
                punch_attendance(session, user_details, attendance_details)
            except Exception as e:
                print(e)
                error_message += ' for username: ' + credentials["username"]
    if len(error_message) != 0:
        raise Exception(error_message)


def get_view_state(session):
    response = session.get(url='https://elevate.peoplestrong.com/altLogin.jsf')
    check_status_code(response)
    html = BeautifulSoup(response.text, 'html.parser')
    return html.find("input", {"name": "javax.faces.ViewState"}).get("value")


def login(session, credentials, view_state):
    pubkey = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC9juqgXB+P/ijlgxv3FvJ2OSC/kktrMOdB6154QJYpDpYyLLlmBemgs9ebAvY1ty8zQrTnHO2NkdzOvc+ZG4H3XtOWHz0fzjmVwl0MEwHygKHML65CGT3TZUbNTxC4aVB9UJHQSWxSv39nqXAbY8kMD0CAuQIVxBW7DT0iVHRuPwIDAQAB"
    key_der = b64decode(pubkey)
    key_rsa = RSA.importKey(key_der)
    cipher = PKCS1_v1_5.new(key_rsa)
    username = b64encode(cipher.encrypt(credentials['username'].encode()))
    password = b64encode(cipher.encrypt(credentials['password'].encode()))
    form_data = {
        "loginForm:username": username,
        "loginForm:password": password,
        "loginForm": "loginForm",
        "loginForm:username12": "",
        "loginForm:loginButton": "",
        "javax.faces.ViewState": view_state

    }
    response = session.post('https://elevate.peoplestrong.com/altLogin.jsf',
                            data=form_data)
    check_status_code(response)


def get_user_details(session):
    json_data = {
        "input": {
            "portalType": "Employee Portal",
            "companyURL": "elevate.peoplestrong.com",
            "userNameHash": "",
            "passwordHash": "",
            "keycloakEnabled": True,
            "oktaEnabled": False,
            "authToken": session.cookies.get('AccessToken')
        }
    }
    response = session.post(url='https://onewebapi.peoplestrong.com/service/user/api/login/v1', json=json_data)
    check_status_code(response)
    response_data = json.loads(response.content)
    check_message(response, response_data)
    return response_data.get('responseData')


def get_attendance_details(session, user_details):
    request_json = {
        "userID": user_details.get('userId'), "employeeID": user_details.get('employeeId'),
        "organizationID": user_details.get('organizationId'),
        "tenantId": "905", "employeeCode": user_details.get('employeeCode'), "tenantID": "905"
    }
    headers = {
        'sessiontoken': session.cookies.get('SessionToken'),
        'session_token': session.cookies.get('SessionToken'),
        'Origin': 'https://elevate.peoplestrong.com',
        'bundleId': '1',
        'bundle_name': 'EN',
        'platform': 'Web',
        'timezone': 'Asia/Kolkata'
    }
    session.headers.update(headers)
    response = session.post(url='https://onewebapi.peoplestrong.com/api/punch/v1/inout/web/get-attendance',
                            json=request_json)
    check_status_code(response)
    response_data = json.loads(response.content)
    check_message(response, response_data)
    return response_data.get('responseData')


def punch_attendance(session, user_details, attendance_details):
    request_json = {"userID": user_details.get('userId'), "employeeID": user_details.get('employeeId'),
                    "organizationID": user_details.get('organizationId'), "tenantId": "905",
                    "employeeCode": user_details.get('employeeCode'), "tenantID": "905", "bundleName": "EN",
                    "shiftId": attendance_details.get('shiftId'),
                    "shiftPremiseID": 207268,
                    "holiday": attendance_details.get('holiday'), "roasterId": 0,
                    "roasterSource": ""}
    reponse = session.post(url='https://onewebapi.peoplestrong.com/api/punch/v1/inout/web/punch-attendance',
                           json=request_json)
    check_status_code(reponse)
    check_message(reponse, json.loads(reponse.content))


def check_status_code(response):
    if response.status_code == http.HTTPStatus.OK.value:
        return
    else:
        raise Exception(
            'status code not 200 ' + str(response.url) + ' ' + str(response.status_code))


def check_message(r, response):
    if response.get('message').get('code') == 'EC200':
        return
    else:
        raise Exception('message is not EC200 for ' + str(response) + ' ' + str(r.url))
