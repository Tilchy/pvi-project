import json
import requests

from nicegui import app, ui
from utils import get_css_file_path, logout, SERVER_URI

def set_chart(chart_id):
    app.storage.user['chart_id'] = chart_id
    show_chart.refresh()
    show_image.refresh()
    show_chart_buttons.refresh()
    get_evaluation_text.refresh()

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

@ui.refreshable
def show_chart():
    image_url, image_description = get_image_url()
    with ui.card().classes('w-full h-full'):
        ui.image(image_url).props(':ratio="16/9"').classes('w-full h-full')
        with ui.card_section():
            ui.label(image_description)

@ui.refreshable
def show_image():
    image_url, image_description = get_image_url()
    ui.image(image_url).props(':ratio="16/9"').classes('w-full h-full')

@ui.refreshable
def show_chart_buttons():
    ui.button('1', color=get_button_color('chart-a'), on_click=lambda: set_chart('chart-a')).classes(get_button_classes('chart-a')).tooltip('Chart 1')
    ui.button('2', color=get_button_color('chart-b'), on_click=lambda: set_chart('chart-b')).classes(get_button_classes('chart-b')).tooltip('Chart 2')
    ui.button('3', color=get_button_color('chart-c'), on_click=lambda: set_chart('chart-c')).classes(get_button_classes('chart-c')).tooltip('Chart 3')
    ui.button('4', color=get_button_color('chart-d'), on_click=lambda: set_chart('chart-d')).classes(get_button_classes('chart-d')).tooltip('Chart 4')
    ui.button('5', color=get_button_color('chart-e'), on_click=lambda: set_chart('chart-e')).classes(get_button_classes('chart-e')).tooltip('Chart 5')

@ui.refreshable
def get_evaluation_text(markdown_ui: ui.markdown):
    """
    Get the evaluation text for the current user and chart id
    by querying the server and parsing the response.

    If the response is valid, it will display the chat history
    in a markdown format. If the response is invalid, it will
    display a message asking the user to ask a question.
    """
    url = f"{SERVER_URI}/evaluations/{app.storage.user['username']}/{app.storage.user['chart_id']}"
    headers = {"Authorization": f"Bearer {app.storage.user['access_token']}"}
    response = requests.get(url, headers=headers)

    try:
        response = json.loads(json.dumps(response.json()))
        history =json.loads(response['chat_history'])

        roles = []
        contents = []
        for index, message in enumerate(history):
            role = message['role']
            content = message['content']
            
            if role == "user" and isinstance(content, list):
                content = " ".join(item['text'] for item in content if item['type'] == 'text')

            roles.append(role)
            contents.append(content)

        markdown_content = ""
        for role, content in zip(roles[1:], contents[1:]):
            markdown_content += "---\n\n"
            markdown_content += f"**{role.capitalize()}**\n\n{content}\n\n"

        markdown_ui.clear()
        markdown_ui.set_content(markdown_content.strip())
    except KeyError:
        markdown_ui.set_content('**Ask a question about the chart image displayed on the left.**')

def submit_question(question):
    """
    Submit a question to the server and update the chat history.

    Args:
        question (str): The question to submit to the server.

    Returns:
        None
    """
    spinner = ui.spinner(size="xl").classes('absolute-center')
    if question == '':
        ui.notify('Please enter a question.')
        spinner.delete()
        return

    url = f"{SERVER_URI}/evaluations/{app.storage.user['username']}/{app.storage.user['chart_id']}"
    headers = {"Authorization": f"Bearer {app.storage.user['access_token']}"}
    response = requests.post(url, headers=headers, json={'question': question})

    spinner.delete()

def get_image_url():
    """Get the image URL and description for the current chart ID.

    Query the server with the current chart ID and access token to get the image URL and description.

    Args:
        None

    Returns:
        tuple: A tuple of the image URL and description.
    """
    url = f"{SERVER_URI}/charts/{app.storage.user['chart_id']}"
    headers = {"Authorization": f"Bearer {app.storage.user['access_token']}"}
    response = requests.get(url, headers=headers).json()
    return response['url'], response['description']

def render_evaluation_page():
    ui.add_css(get_css_file_path())
    
    with ui.dialog() as dialog, ui.card(align_items='end').classes('w-full h-full').style('max-width: none'):
        ui.button('X', on_click=dialog.close)
        show_image()

    with ui.header(elevated=True).style('background-color: var(--primary-color);').classes('flex items-center justify-between h-20 px-4'):
        with ui.row().classes('items-center'):
            ui.label('Chart Evaluation').classes('text-2xl text-white')
        
        with ui.row().classes('gap-4 items-center'):
            ui.button(text='', color='var(--primary-color)', on_click=lambda: logout(), icon='contact_support').props("flat round").tooltip('Documentation')
            ui.button(text='', color='var(--primary-color)', on_click=lambda: logout(), icon='logout').props("flat round").tooltip('Logout')
    
    with ui.element('div').classes('w-full h-[calc(100vh-7.5rem)] flex flex-wrap'):
        with ui.column().classes('w-full md:w-2/5 h-full'):
            with ui.element('div').classes('grid grid-rows-[6fr_4fr] h-full w-full'):      
                with ui.row(align_items='center').classes('h-full w-full justify-center').style('background-color: #e0e7eb'):
                    with ui.element('div').on('click', dialog.open).classes('w-full h-full cursor-pointer p-4').tooltip('Enlarge image'):
                            show_chart()

                with ui.row(align_items='start').classes('gap-4 w-full h-full justify-center pt-8').style('background-color: #e0e7eb'):
                    show_chart_buttons()

        with ui.column().classes('w-full md:w-3/5 h-full'):
            with ui.element('div').classes('grid grid-rows-[5fr_3fr] h-full w-full'):
                with ui.row(align_items='center').classes('h-full w-full justify-center px-32 pt-8 text-lg').style('background-color: #e0e7eb'):
                    with ui.scroll_area().classes('w-full h-full'):
                        markdown_ui = ui.markdown()
                        ui.timer(1.0, lambda: get_evaluation_text(markdown_ui))
                        
                with ui.row(align_items='start').classes('h-full w-full').style('background-color: #e0e7eb'):
                    question = ui.textarea(label='Question', placeholder='Start typing your question?').props('outlined rows="6"').classes('w-full pt-8 mx-64 text-lg')
                    ui.button(color='var(--primary-color)', text='Submit', on_click=lambda: (submit_question(question.value), question.set_value(''))).classes('w-full text-white mt-4 mx-64')

    with ui.footer(elevated=True).style('background-color: #29363d;').classes('items-center h-10'):
        ui.label('Tilen Tratnjek - Univerza v Mariboru 2025').classes('pl-4 text-sm text-gray-200')