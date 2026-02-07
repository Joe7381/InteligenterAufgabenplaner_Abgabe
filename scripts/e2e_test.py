#!/usr/bin/env python3
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def post(url, data, token=None):
    b = json.dumps(data).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(url, data=b, headers=headers, method='POST')
    try:
        with urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except HTTPError as e:
        try:
            body = e.read().decode('utf-8')
            return {'error': f'HTTPError {e.code}', 'body': body}
        except Exception:
            return {'error': f'HTTPError {e.code}', 'reason': str(e)}
    except Exception as e:
        return {'error': 'exception', 'reason': str(e)}

def get(url, token=None):
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(url, headers=headers, method='GET')
    try:
        with urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except HTTPError as e:
        try:
            body = e.read().decode('utf-8')
            return {'error': f'HTTPError {e.code}', 'body': body}
        except Exception:
            return {'error': f'HTTPError {e.code}', 'reason': str(e)}
    except Exception as e:
        return {'error': 'exception', 'reason': str(e)}

BASE = 'http://localhost:8000'

def pretty(obj):
    try:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    except Exception:
        print(str(obj))

if __name__ == '__main__':
    # 1) Register (ignore if exists)
    print('== register ==')
    r = post(BASE + '/register', {'email': 'testuser@example.com', 'password': 'testpass123'})
    pretty(r)

    # 2) Login
    print('\n== login ==')
    login = post(BASE + '/login', {'email': 'testuser@example.com', 'password': 'testpass123'})
    pretty(login)
    token = login.get('access_token')
    if not token:
        print('Login did not return token, aborting')
        sys.exit(1)

    # 3) Chat
    print('\n== chat ==')
    prompt = 'Ich möchte am 24.12.2025 um 12:00 einen Termin'
    chat = post(BASE + '/chat', {'prompt': prompt}, token=token)
    pretty(chat)
    conv_id = chat.get('conversation_id')

    # 4) Confirm -> create task
    print('\n== chat/confirm ==')
    if not conv_id:
        print('No conversation_id returned, aborting confirm test')
    else:
        conf = post(BASE + '/chat/confirm', {'conversation_id': conv_id}, token=token)
        pretty(conf)

    # 5) List tasks
    print('\n== tasks ==')
    tasks = get(BASE + '/tasks', token=token)
    pretty(tasks)

    # 6) recent-chats
    print('\n== recent-chats ==')
    recent = get(BASE + '/recent-chats?limit=5')
    pretty(recent)
