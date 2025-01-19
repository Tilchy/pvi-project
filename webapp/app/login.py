import requests
from nicegui import ui, app
from utils import get_css_file_path, SERVER_URI

def on_login(username: str, password: str):
    """Login to the server with the given username and password.

    If the login is successful, set the access token and user information in the
    session storage and navigate to the evaluation page. Otherwise, show a notification
    with the error message returned by the server.
    """

    form_data = {
        'username': username,
        'password': password
    }
    
    response = requests.post(f'{SERVER_URI}/users/login', data=form_data)

    if response.status_code == 200:
        access_token = dict(response.json()).get('access_token')
        app.storage.user['access_token'] = access_token
        app.storage.user['username'] = username
        app.storage.user['chart_id'] = 'chart-a'
        ui.navigate.to('/evaluation')
    else:
        ui.notify(response.json())

def render_login_page():
    ui.add_css(get_css_file_path())

    with ui.header(elevated=True).style('background-color: var(--primary-color);').classes('items-center justify-between h-20'):
        ui.label('Chart Evaluation').classes('text-2xl text-white pl-4')

    with ui.element('div').classes('w-full h-[calc(100vh-7.5rem)]').style('background-color: #e0e7eb'):
        with ui.element('div').classes('grid grid-rows-[1fr_8fr_1fr] grid-cols-[1fr_3fr_1fr] h-full w-full'):
            with ui.card().classes('w-full h-full gap-4 items-center justify-center').classes('row-span-3 col-span-3 md:row-span-1 md:col-span-1 md:col-start-2 md:row-start-2'):
                ui.label('Login').classes('text-2xl')
                username = ui.input('Username').props('outlined autofocus type=text').classes('w-2/5')
                password = ui.input('Password').props('outlined type=password').classes('w-2/5')
                ui.button(color='var(--primary-color)', text='Login', on_click=lambda: on_login(username.value, password.value)).classes('w-2/5 mt-4 text-white')

    with ui.footer(elevated=True).style('background-color: #29363d;').classes('items-center h-10'):
        ui.label('Tilen Tratnjek - Univerza v Mariboru 2025').classes('pl-4 text-sm text-gray-200')