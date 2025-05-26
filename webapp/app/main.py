import os
from nicegui import ui

from utils import require_authentication

from admin import render_admin_page
from evaluation import render_evaluation_page
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
    spinner = ui.spinner(size=30).classes('absolute-center')  # Show a spinner while checking authentication
    
    async def check_authentication():
        user_data = require_authentication()
        if user_data:
            spinner.delete()
            await render_evaluation_page()

    await check_authentication()

@ui.page('/admin')
def admin_page():
    spinner = ui.spinner(size=30).classes('absolute-center')

    def check_authentication():
        user_data = require_authentication(required_type='admin')
        if user_data:
            spinner.delete()
            render_admin_page()

    check_authentication()

ui.run(title='My App', storage_secret=STORAGE_KEY)

