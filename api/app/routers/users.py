import jwt
import os

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Form, Header
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session, select
from passlib.hash import argon2
from dotenv import load_dotenv

from app.dependencies import get_session

load_dotenv()
JWT_KEY = os.getenv("JWT_KEY")

class UserBase(SQLModel):
    username: str
    full_name: str
    disabled: bool = False
    type: str

class User(UserBase, table=True):
    username: str = Field(primary_key=True)
    full_name: str
    disabled: bool
    type: str
    password: str

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    username: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    type: Optional[str] = None
    password: Optional[str] = None

class TokenBase(SQLModel):
    token: str
    expires_at: datetime

class RevokedToken(TokenBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    token: str
    expires_at: datetime

class TokenRequest(BaseModel):
    token: str

router = APIRouter(
    prefix="/users", 
    tags=["users"]
)

SessionDep = Annotated[Session, Depends(get_session)] 

def hash_password(password: str) -> str:
    """
    Hash a password using Argon2.

    Args:
    password: The plain text password to be hashed.

    Returns:
    The hashed password as a string.
    """

    return argon2.hash(password)

@router.post("/", response_model=UserBase)
async def create_user(user: UserCreate, session: SessionDep, authorization: str = Header()):
    """Create a new user.

    This endpoint creates a new user in the database after verifying
    the provided Bearer token.

    Args:
    user: The user to be created.
    session: The database session.

    Returns:
    The created user.

    Raises:
    HTTPException: If a user with the same username already exists.
    """

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    verify_if_admin(token, session)

    statement = select(User).where(User.username == user.username)
    if session.exec(statement).first():
        raise HTTPException(status_code=400, detail="User with this username already exists")

    hashed_password = hash_password(user.password)
    db_user = User(username=user.username, full_name=user.full_name, disabled=user.disabled, type=user.type, password=hashed_password)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@router.get("/{username}", response_model=UserBase)
async def get_user(username: str, session: SessionDep, authorization: str = Header()):
    """
    Get a user by username.

    Args:
        username (str): username of the user to retrieve
        session (SessionDep): database session

    Returns:
        User: The requested user

    Raises:
        HTTPException: 404 if the user is not found
    """

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    # verify if user is requesting their own data
    payload = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
    if payload["username"] != username:
        verify_if_admin(token, session)
    else:
        verify_user(token, session)

    db_user = session.get(User, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.put("/{username}", response_model=UserBase)
async def update_user(username: str, user: UserUpdate, session:SessionDep, authorization: str = Header()):
    """
    Update a user.

    This endpoint updates a user in the database.

    Args:
    username: The username of the user to update.
    user: The user data to update.
    session: The database session.

    Returns:
    The updated user.

    Raises:
    HTTPException: 404 if the user is not found.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    verify_if_admin(token, session)

    db_user = session.get(User, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user.model_dump(exclude_unset=True)
    for key, value in user_data.items():
        setattr(db_user, key, value)

    if "password" in user_data:
        db_user.password = hash_password(user_data["password"])

    session.commit()
    session.refresh(db_user)
    return db_user

@router.delete("/{username}", status_code=204)
async def delete_user(username: str, session: SessionDep, authorization: str = Header()):
    """
    Delete a user.

    This endpoint deletes a user from the database.

    Args:
    username: The username of the user to delete.
    session: The database session.

    Returns:
    None

    Raises:
    HTTPException: 404 if the user is not found.
    """

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    verify_if_admin(token, session)

    db_user = session.get(User, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(db_user)
    session.commit()

    return None

@router.post("/login")
async def login_user(username: Annotated[str, Form()], password: Annotated[str, Form()], session: SessionDep):
    """
    Log in a user and issue an access token.

    This endpoint verifies the user's credentials and issues an access token
    if the credentials are correct and the user is active.

    Args:
    username: The username of the user trying to log in.
    password: The password of the user trying to log in.
    session: The database session.

    Returns:
    A dictionary with the access token.

    Raises:
    HTTPException: 404 if the user is not found.
    HTTPException: 401 if the password is incorrect or the user is disabled.
    """

    db_user = session.get(User, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not argon2.verify(password, db_user.password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    if db_user.disabled:
        raise HTTPException(status_code=401, detail="User is disabled")

    access_token = issue_access_token(username)

    return {"access_token": access_token}

def issue_access_token(username: str):
    """
    Issue an access token for a user.

    This function creates an access token that contains the username and an
    expiration time (7 days from now). The token is signed with the secret key.

    Args:
        username (str): The username to issue the token for

    Returns:
        str: The issued access token
    """
    payload = {"username": username, "exp": datetime.now(tz=timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, JWT_KEY, algorithm="HS256")

@router.post("/verify", response_model=UserBase)
async def verify_access_token(request: TokenRequest, session: SessionDep):
    """
    Verify an access token.

    This endpoint verifies that the provided access token is valid and
    has not expired or been revoked.

    Args:
    token: The access token to verify.

    Returns:
    The user associated with the access token if it is valid.

    Raises:
    HTTPException: 401 if the token is invalid or has expired.
    HTTPException: 404 if the user associated with the token does not exist.
    """
    token = request.token
    try:
        payload = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
        username = payload["username"]
        
        db_user = session.get(User, username)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        if db_user.disabled:
            raise HTTPException(status_code=401, detail="User is disabled")

        revoked_query = select(RevokedToken).where(RevokedToken.token == token)
        revoked_token = session.exec(revoked_query).first()
        if revoked_token:
            raise HTTPException(status_code=401, detail="Access token has been revoked")
        
        return db_user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid access token")
    
@router.post("/revoke")
def revoke_access_token(request: TokenRequest, session: SessionDep):
    """
    Revoke an access token.

    This endpoint revokes an access token and makes it invalid for
    authentication. The token is added to the RevokedToken table.

    Args:
    token: The access token to revoke.

    Returns:
    A success message if the token is revoked successfully.

    Raises:
    HTTPException: 404 if the user associated with the token does not exist.
    HTTPException: 400 if the token is already revoked.
    HTTPException: 401 if the token is invalid or has expired.
    """
    token = request.token    
    try:
        payload: dict = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
        username = payload["username"]

        db_user = session.get(User, username)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        revoked_query = select(RevokedToken).where(RevokedToken.token == token)
        revoked_token = session.exec(revoked_query).first()
        if revoked_token:
            raise HTTPException(status_code=400, detail="Token is already revoked")

        expires_at = payload.get("exp", None)
        if expires_at:
            expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        else:
            raise HTTPException(status_code=400, detail="Invalid token expiration")

        revoked_instance = RevokedToken(token=token, expires_at=expires_at)
        session.add(revoked_instance)
        session.commit()
        session.refresh(revoked_instance)

        return {"message": "Access token revoked successfully"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid access token")
    

def verify_if_admin(token: str, session: SessionDep):
    """
    Verify if the user associated with the access token is an admin.

    This function verifies the access token and checks if the user associated
    with the token is an admin. If the token is invalid, revoked, or expired,
    it raises an HTTPException with a 401 status code. If the user is not an
    admin, it raises an HTTPException with a 401 status code.

    Args:
    token: The access token to verify.
    session: The database session.

    Raises:
    HTTPException: 401 if the access token is invalid, revoked, or expired.
    HTTPException: 401 if the user is not an admin.
    """
    try:
        payload = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
        username = payload["username"]
        # Verify that the user exists and is active
        db_user = session.get(User, username)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        if db_user.disabled:
            raise HTTPException(status_code=401, detail="User is disabled")

        revoked_query = select(RevokedToken).where(RevokedToken.token == token)
        revoked_token = session.exec(revoked_query).first()
        if revoked_token:
            raise HTTPException(status_code=401, detail="Access token has been revoked")
        
        if not db_user.type == "admin":
            raise HTTPException(status_code=401, detail="User is not admin")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid access token")
    

def verify_user(token: str, session: SessionDep):
    """
    Verify if the user associated with the access token is a user.

    This function verifies the access token and checks if the user associated
    with the token is a user. If the token is invalid, revoked, or expired,
    it raises an HTTPException with a 401 status code. If the user is not a
    user, it raises an HTTPException with a 401 status code.

    Args:
    token: The access token to verify.
    session: The database session.

    Raises:
    HTTPException: 401 if the access token is invalid, revoked, or expired.
    HTTPException: 401 if the user is not a user.
    """
    try:
        payload = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
        username = payload["username"]

        db_user = session.get(User, username)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        if db_user.disabled:
            raise HTTPException(status_code=401, detail="User is disabled")

        revoked_query = select(RevokedToken).where(RevokedToken.token == token)
        revoked_token = session.exec(revoked_query).first()
        if revoked_token:
            raise HTTPException(status_code=401, detail="Access token has been revoked")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid access token")