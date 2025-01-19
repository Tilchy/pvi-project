from nicegui import ui

from utils import get_css_file_path, logout

def render_admin_page():
    ui.add_css(get_css_file_path())
    
    with ui.header(elevated=True).style('background-color: var(--primary-color);').classes('items-center justify-between h-20'):
        ui.label('Chart Evaluation').classes('text-2xl text-white pl-4')
        ui.button(text='', color='var(--primary-color)', on_click=lambda: logout(), icon='logout').props("flat round").classes('mr-8 text-xl').tooltip('Logout')

    with ui.footer(elevated=True).style('background-color: #29363d;').classes('items-center h-10'):
        ui.label('©Tilen Tratnjek 2025').classes('pl-4 text-sm text-gray-200')