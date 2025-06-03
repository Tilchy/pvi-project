import os
import json
import requests

from nicegui import ui, app, run

from utils import require_authentication, get_image_url, get_charts, get_button_color, get_button_classes, get_css_file_path, logout, SERVER_URI

from login import render_login_page
from dotenv import load_dotenv


load_dotenv()

STORAGE_KEY = os.getenv('STORAGE_KEY')

@ui.page('/')
def root_page():
    ui.navigate.to('/login')

@ui.page('/login')
def login_page():
    render_login_page()

@ui.page('/evaluation')
async def evaluation_page():
    """
    Renders the evaluation page after checking user authentication.

    This function displays a spinner while verifying authentication.
    If authentication is successful, the spinner is removed and the 
    evaluation page is rendered.
    """

    @ui.refreshable
    async def show_chart():
        image_url, image_description = await get_image_url()
        with ui.card().classes('w-full h-fit max-h-[40rem]'):
            ui.image(image_url).props('fit="contain"')
            with ui.card_section():
                ui.label(image_description)

    @ui.refreshable
    async def show_image():
        image_url, image_description = await get_image_url()
        ui.image(image_url).classes('w-full h-full').props('fit="scale-down"')

    @ui.refreshable
    async def show_textarea_or_spinner():
        # Show spinner while loading
        if app.storage.user.get('is_loading', False):
            with ui.row().classes('w-full justify-center items-center mt-8'):
                ui.spinner(size='xl') 
            ui.button(color='var(--primary-color)', text='Pošlji vprašanje').classes('w-full text-white mt-4 mx-8 lg:mx-16 xl:mx-32 mb-16').props('disable')
        else:
            question = ui.textarea(label='Vprašanje', placeholder='Zapišite vprašanje...').props('outlined rows="6"').classes('w-full pt-8 mx-8 lg:mx-16 xl:mx-32 text-lg')
            ui.button(color='var(--primary-color)', text='Pošlji vprašanje', on_click=lambda: handle_question_submit(question.value)).classes('w-full text-white mt-4 mx-8 mb-16 lg:mx-16 xl:mx-32')

    @ui.refreshable
    async def show_chart_buttons():
        charts = await get_charts() 
        
        for idx, chart in enumerate(charts):
            ui.button(f'{idx + 1}', color=get_button_color(chart), on_click=lambda c=chart: set_chart(c)).classes(get_button_classes(chart)).tooltip(f'Graf {idx + 1}')

    @ui.refreshable
    async def get_evaluation_text(markdown_ui: ui.markdown, scroll_area: ui.scroll_area):
        """
        Get the evaluation text for the current user and chart id
        by querying the server and parsing the response.

        If the response is valid, it will display the chat history
        in a markdown format. If the response is invalid, it will
        display a message asking the user to ask a question.
        """
        url = f"{SERVER_URI}/evaluations/{app.storage.user.get('email')}/{app.storage.user.get('chart_id')}"
        headers = {"Authorization": f"Bearer {app.storage.user.get('access_token')}"}
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
            markdown_ui.clear()
            for i, (role, content) in enumerate(zip(roles[1:], contents[1:])):
                translated_role = "Uporabnik" if role == "user" else "AI Pomočnik"

                message_block = f"**{translated_role}**\n\n{content}"

                if i == len(roles[1:]) - 1:
                    ui.markdown(message_block).classes('highlight-last p-2').props('id="last-message"')
                else:
                    ui.markdown("---\n\n" + message_block + "\n\n").classes('p-2 w-full')
            
            markdown_ui.set_content(markdown_content.strip())
            ui.run_javascript("""
                const last = document.getElementById('last-message');
                if (last) {
                    last.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            """)
        except KeyError:
            markdown_ui.set_content('**Tukaj bodo prikazani odgovori AI pomočnika, potem ko jih postavite.**')

    async def set_chart(chart_id):
        app.storage.user.update({'chart_id': chart_id})
        show_chart.refresh()
        show_image.refresh()
        show_chart_buttons.refresh()
        get_evaluation_text.refresh()

    async def handle_question_submit(question: str):
        app.storage.user.update({'is_loading': True})
        show_textarea_or_spinner.refresh()

        await submit_question(question)

        app.storage.user.update({'is_loading': False})
        show_textarea_or_spinner.refresh()

    async def submit_question(question: str):
        """
        Submit a question to the server and update the chat history.

        Args:
            question (str): The question to submit to the server.
        """
        if not question.strip():
            ui.notify('Please enter a question.')
            return

        url = f"{SERVER_URI}/evaluations/{app.storage.user.get('email')}/{app.storage.user.get('chart_id')}"
        headers = {"Authorization": f"Bearer {app.storage.user.get('access_token')}"}

        # Run the POST request in a background thread
        await run.io_bound(requests.post, url, headers=headers, json={'question': question})

        get_evaluation_text.refresh()

    async def render_evaluation_page():
        ui.add_css(get_css_file_path())

        if 'is_loading' not in app.storage.user:
            app.storage.user.update({'is_loading': False})
        
        with ui.dialog() as dialog, ui.card(align_items='end').classes('w-full h-full').style('max-width: none'):
            ui.button('X', on_click=dialog.close)
            await show_image()

        with ui.header(elevated=True).style('background-color: var(--primary-color);').classes('flex items-center justify-between h-20 px-4'):
            with ui.row().classes('items-center'):
                ui.label('AI Pomočnik').classes('text-2xl text-white')
            
            with ui.row().classes('gap-4 items-center'):
                ui.button(text='', color='var(--primary-color)', on_click=lambda: logout(), icon='logout').props("flat round").tooltip('Logout')
        
        with ui.element('div').classes('w-full xl:h-[calc(100vh-7.5rem)] flex flex-wrap'):
            with ui.column().classes('w-full h-full xl:w-2/5'):   
                with ui.row(align_items='center').classes('h-fit w-full justify-center').style('background-color: #e0e7eb'):
                    with ui.element('div').on('click', dialog.open).classes('w-full h-full cursor-pointer p-4').tooltip('Kliknite za povečavo slike'):
                            await show_chart()

                with ui.row(align_items='start').classes('gap-4 w-full h-fit justify-center pt-8 px-4').style('background-color: #e0e7eb'):
                    await show_chart_buttons()

            with ui.column().classes('w-full h-fit xl:w-3/5'):
                with ui.row(align_items='center').classes('h-full w-full justify-center px-8 lg:px-32 pt-8 text-lg').style('background-color: #e0e7eb'):
                    with ui.scroll_area().classes('min-h-[20rem] xl:min-h-[30rem]') as scroll_area:
                        markdown_ui = ui.markdown()
                        await get_evaluation_text(markdown_ui, scroll_area)
                with ui.row(align_items='start').classes('h-full w-full min-h-80').style('background-color: #e0e7eb'):
                    await show_textarea_or_spinner()
                        
        with ui.footer(elevated=False).style('background-color: #29363d;').classes('items-center h-10'):
            ui.label('Tilen Tratnjek - Univerza v Mariboru 2025').classes('pl-4 text-sm text-gray-200')


    spinner = ui.spinner(size=30).classes('absolute-center')  # Show a spinner while checking authentication
    
    async def check_authentication():
        user_data = require_authentication()
        if user_data:
            spinner.delete()
            await render_evaluation_page()

    await check_authentication()

ui.run(title='My App', storage_secret=STORAGE_KEY)