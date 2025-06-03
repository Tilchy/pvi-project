import requests

from pathlib import Path
from nicegui import ui, app

#SERVER_URI = "http://api:80"
SERVER_URI = "http://127.0.0.1:8000"
def logout():
    app.storage.user.clear()
    ui.navigate.to('/login')

def get_css_file_path():
    return str(Path(__file__).parent / 'main.css')

def verify_token() -> dict | None:
    access_token = app.storage.user.get('access_token', None)
    if not access_token:
        print('Access token is empty, please login.')
        return None
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


async def get_image_url():
    """Get the image URL and description for the current chart ID.

    Query the server with the current chart ID and access token to get the image URL and description.

    Args:
        None

    Returns:
        tuple: A tuple of the image URL and description.
    """
    url = f"{SERVER_URI}/charts/{app.storage.user.get('chart_id')}"
    headers = {"Authorization": f"Bearer {app.storage.user.get('access_token')}"}
    response = requests.get(url, headers=headers).json()
    return response['url'], response['description']


def get_button_classes(chart_id):
    active_button = app.storage.user.get('chart_id', None)
    if active_button == chart_id:
        return 'text-white text-lg'
    return 'text-black text-lg'

def get_button_color(chart_id):
    active_button = app.storage.user.get('chart_id', None)
    if active_button == chart_id:
        return 'var(--primary-color)'
    return 'var(--disabled-color)'

async def get_charts():
    """Get the list of charts from the server.

    Query the server to get the list of available charts.

    Args:
        None

    Returns:
        list: A list of chart names.
    """
    url = f"{SERVER_URI}/charts/"
    headers = {"Authorization": f"Bearer {app.storage.user.get('access_token')}"}
    response = requests.get(url, headers=headers).json()

    return [chart['name'] for chart in response]