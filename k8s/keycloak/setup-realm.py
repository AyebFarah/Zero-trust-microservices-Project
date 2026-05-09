import requests
import json

KEYCLOAK_URL = 'http://localhost:8080'
ADMIN_USER = 'admin'
ADMIN_PASS = 'admin-zero-trust-2026'
REALM_NAME = 'zero-trust-project'

def get_admin_token():
    resp = requests.post(
        f'{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token',
        data={
            'grant_type': 'password',
            'client_id': 'admin-cli',
            'username': ADMIN_USER,
            'password': ADMIN_PASS,
        }
    )
    if resp.status_code != 200:
        print(f'Erreur token admin: {resp.status_code} {resp.text}')
        exit(1)
    return resp.json()['access_token']

def create_realm(token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    realm_config = {
        'realm': REALM_NAME,
        'enabled': True,
        'displayName': 'Zero Trust Project',
        'accessTokenLifespan': 300,
        'refreshTokenMaxReuse': 0,
    }
    resp = requests.post(
        f'{KEYCLOAK_URL}/admin/realms',
        headers=headers,
        json=realm_config
    )
    print(f'Realm créé : {resp.status_code}')

def create_client(token, client_id, client_name):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    client_config = {
        'clientId': client_id,
        'name': client_name,
        'enabled': True,
        'serviceAccountsEnabled': True,
        'standardFlowEnabled': False,
        'directAccessGrantsEnabled': False,
        'secret': f'{client_id}-secret-2026',
    }
    resp = requests.post(
        f'{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/clients',
        headers=headers,
        json=client_config
    )
    print(f'Client {client_id} créé : {resp.status_code}')

if __name__ == '__main__':
    print('Connexion à Keycloak...')
    token = get_admin_token()
    print('Token admin obtenu OK')

    create_realm(token)

    services = [
        ('service-auth',         'Service Auth'),
        ('service-orders',       'Service Orders'),
        ('service-payment',      'Service Payment'),
        ('service-notification', 'Service Notification'),
        ('lsa-agent',            'LSA Security Agent'),
    ]

    for client_id, name in services:
        create_client(token, client_id, name)

    print('Configuration Keycloak terminée !')
