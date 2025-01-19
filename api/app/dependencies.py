from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import Session, create_engine, SQLModel
from dotenv import load_dotenv

import os

load_dotenv()
sqlite_file_name = os.getenv("DATABASE_NAME")
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    """
    Create the database and tables.

    This function initializes the database by creating all the tables
    defined in the SQLModel metadata using the configured database engine.
    """

    SQLModel.metadata.create_all(engine)

def get_session():
    """
    FastAPI dependency that returns a database session.

    Yields a database session that will be closed when the response is sent.
    This is a context manager that will be used by FastAPI as a dependency.
    The session is created using the configured database engine.
    """
    with Session(engine) as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
