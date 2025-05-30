import io
import os
import csv

from typing import Annotated
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, Header, Request, UploadFile
from requests import Session
from sqlmodel import delete

from app.dependencies import get_session
from app.routers.users import User
from app.routers.charts import Chart
from app.routers.evaluations import Evaluation

router = APIRouter(
    prefix="/reset", 
    tags=["reset"]
)

SessionDep = Annotated[Session, Depends(get_session)]

load_dotenv()
KEY=os.getenv("KEY")

@router.post("/users")
async def reset_users(session: SessionDep, authorization: Annotated[str, Header()],file: UploadFile = File(...)):
    """
    Reset all users in the database and add a new set of users from an uploaded CSV file.

    This endpoint deletes all existing users in the database, adds an admin
    user with a default password, and then populates the database with users
    defined in an uploaded CSV file. The CSV file should have columns for
    'username', 'full_name', 'disabled', 'type', and 'password'.

    Args:
        request: The request object.
        session: The database session.
        authorization: Secret key for authorization.
        file: CSV file containing user data.

    Returns:
        A success message indicating that users have been reset successfully.

    Raises:
        HTTPException: If the secret key is invalid.
    """

    if authorization != KEY:
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
    statement = delete(User)
    session.exec(statement)

    admin_user = User(
        username="admin",
        email="admin@example.com",
        disabled=False,
        type="admin"
    )
    session.add(admin_user)

    file_content = io.TextIOWrapper(file.file, encoding="utf-8")
    csv_reader = csv.DictReader(file_content)
    for row in csv_reader:
        user = User(
            username=row["username"],
            email=row.get("email", "Unknown"),
            disabled=row.get("disabled", "False").lower() == "true",
            type=row.get("type", "user")
        )
        session.add(user)

    session.commit()
    return {"message": "Users reset successfully"}

@router.post("/charts")
async def reset_charts(session: SessionDep, authorization: Annotated[str, Header()],file: UploadFile = File(...)):
    """
    Reset charts data.

    This endpoint deletes all existing charts in the database and inserts new
    charts based on the data provided in a CSV file. The CSV file should contain
    columns for chart name, description, instruction, and URL.

    Args:
        session: The database session.
        authorization: The secret key for authorization.
        file: The CSV file containing chart data.

    Returns:
        A success message indicating that charts have been reset successfully.

    Raises:
        HTTPException: If the secret key is invalid.
    """

    if authorization != KEY:
        raise HTTPException(status_code=403, detail="Invalid secret key")

    statement = delete(Chart)
    session.exec(statement)

    file_content = io.TextIOWrapper(file.file, encoding="utf-8")
    csv_reader = csv.DictReader(file_content)
    for row in csv_reader:
        chart = Chart(
            name=row["name"],
            description=row["description"],
            instruction=row["instruction"],
            url=row["url"]
        )
        session.add(chart)

    session.commit()
    return {"message": "Charts reset successfully"}

@router.post("/evaluations")
async def reset_evaluations(request: Request, session: SessionDep, authorization: Annotated[str, Header()]): 
    """
    Reset evaluation data.

    This endpoint deletes all existing evaluation charts in the database.

    Args:
        request: The request object.
        session: The database session.
        authorization: The secret key for authorization.

    Returns:
        None

    Raises:
        HTTPException: If the secret key is invalid.
    """

    if authorization != KEY:
        raise HTTPException(status_code=403, detail="Invalid secret key")

    statement = delete(Evaluation)
    session.exec(statement)