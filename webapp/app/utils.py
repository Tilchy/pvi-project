import requests

from pathlib import Path
from nicegui import ui, app

SERVER_URI = "http://api:80"
#SERVER_URI = "http://127.0.0.1:8000"
def logout():
    app.storage.user.clear()
    ui.navigate.to('/login')

def get_css_file_path():
    return str(Path(__file__).parent / 'main.css')

def verify_token() -> dict | None:
    if 'access_token' not in app.storage.user:
        print('No access token found, please login.')
        return None 

    access_token = app.storage.user['access_token']
    data = {'token': access_token}
    response = requests.post(f'{SERVER_URI}/users/verify', json=data)

    if response.status_code != 200:
        ui.notify(response.json())
        return None

    user_data = response.json()
    return user_data 

def require_authentication(required_type=None):
    user_data = verify_token()
    if not user_data:
        ui.notify('Access denied: Please login first.', color='red')
        ui.timer(3.0, lambda: ui.navigate.to('/login'), once=True)
        return None
    if required_type and user_data.get('type') != required_type:
        ui.notify(f'Access denied: {required_type.capitalize()} privileges required.', color='red')
        ui.timer(3.0, lambda: ui.navigate.to('/evaluation'), once=True)
        return None
    return user_data