#!/usr/bin/env python3
import os
import sys
import json
import requests

# bootstrap frappe in repo
cwd = os.getcwd()
sys.path.insert(0, os.path.join(cwd, 'apps', 'frappe'))
import frappe
from frappe import init, connect, destroy

sites_path = os.path.join(cwd, 'sites')
init(site='tapbuddy.local', sites_path=sites_path)
connect()

try:
    settings = frappe.get_single('TAP Buddy Settings')
    base = settings.glific_url.rstrip('/') if getattr(settings, 'glific_url', None) else os.environ.get('GLIFIC_URL')
    if not base:
        print('Glific base URL not configured. Set TAP Buddy Settings.glific_url or GLIFIC_URL env var.')
        sys.exit(1)

    phone = os.environ.get('GLIFIC_PHONE_NUMBER')
    password = os.environ.get('GLIFIC_PASSWORD')
    if not phone or not password:
        print('Please set GLIFIC_PHONE_NUMBER and GLIFIC_PASSWORD environment variables.')
        sys.exit(1)

    url = base + '/session' if base.endswith('/api/v1') else base + '/api/v1/session' if not base.endswith('/session') else base
    print('Logging in to', url)
    payload = {'user': {'phone': phone, 'password': password}}
    resp = requests.post(url, json=payload, timeout=20)
    print('status', resp.status_code)
    if resp.status_code != 200:
        print('Login failed:', resp.text)
        sys.exit(2)
    data = resp.json().get('data', resp.json())
    access = data.get('access_token')
    refresh = data.get('renewal_token') or data.get('refresh_token')
    expiry = data.get('token_expiry_time') or data.get('expires_at')

    if access:
        settings.glific_access_token = access
    if refresh:
        settings.glific_refresh_token = refresh
    if expiry:
        settings.glific_token_expiry = expiry

    settings.save(ignore_permissions=True)
    frappe.db.commit()
    print('Saved tokens into TAP Buddy Settings (masked):')
    print(' access=', access[:10] + '...' if access else None)
    print(' refresh=', refresh[:10] + '...' if refresh else None)
    print(' expiry=', expiry)

finally:
    destroy()
