import json
import requests

from nicegui import app, ui, run
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
def show_textarea_or_spinner():
    # Show spinner while loading
    if app.storage.user.get('is_loading', False):
        with ui.row().classes('w-full justify-center items-center mt-8'):
            ui.spinner(size='xl') 
        ui.button(color='var(--primary-color)', text='Submit', on_click=lambda: handle_question_submit(question.value)).classes('w-full text-white mt-4 mx-64').props('disable')
    else:
        question = ui.textarea(label='Question', placeholder='Start typing your question?').props('outlined rows="6"').classes('w-full pt-8 mx-64 text-lg') 
        ui.button(color='var(--primary-color)', text='Submit', on_click=lambda: handle_question_submit(question.value)).classes('w-full text-white mt-4 mx-64')

@ui.refreshable
def show_chart_buttons():
    charts = get_charts() 
    
    for idx, chart in enumerate(charts):
        ui.button(f'{idx + 1}', color=get_button_color(chart), on_click=lambda c=chart: set_chart(c)).classes(get_button_classes(chart)).tooltip(f'Chart {idx + 1}')

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

async def submit_question(question: str):
    """
    Submit a question to the server and update the chat history.

    Args:
        question (str): The question to submit to the server.
    """
    if not question.strip():
        ui.notify('Please enter a question.')
        return

    url = f"{SERVER_URI}/evaluations/{app.storage.user['username']}/{app.storage.user['chart_id']}"
    headers = {"Authorization": f"Bearer {app.storage.user['access_token']}"}
    
    # Run the POST request in a background thread
    await run.io_bound(requests.post, url, headers=headers, json={'question': question})

    get_evaluation_text.refresh()
    
async def handle_question_submit(question: str):
    app.storage.user['is_loading'] = True
    show_textarea_or_spinner.refresh()
    get_evaluation_text.refresh()

    await submit_question(question)

    app.storage.user['is_loading'] = False
    show_textarea_or_spinner.refresh()

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

def get_charts():
    """Get the list of charts from the server.

    Query the server to get the list of available charts.

    Args:
        None

    Returns:
        list: A list of chart names.
    """
    url = f"{SERVER_URI}/charts/"
    headers = {"Authorization": f"Bearer {app.storage.user['access_token']}"}
    response = requests.get(url, headers=headers).json()

    return [chart['name'] for chart in response]


async def render_evaluation_page():
    ui.add_css(get_css_file_path())

    if 'is_loading' not in app.storage.user:
        app.storage.user['is_loading'] = False
    
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
                        get_evaluation_text(markdown_ui)
                with ui.row(align_items='start').classes('h-full w-full').style('background-color: #e0e7eb'):
                    show_textarea_or_spinner()
                    
    with ui.footer(elevated=True).style('background-color: #29363d;').classes('items-center h-10'):
        ui.label('Tilen Tratnjek - Univerza v Mariboru 2025').classes('pl-4 text-sm text-gray-200')