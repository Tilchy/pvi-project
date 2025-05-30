import jwt
import os
import random
import string

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Form, Header
from pydantic import BaseModel, EmailStr
from sqlmodel import Field, SQLModel, Session, select
from dotenv import load_dotenv

from app.dependencies import get_session

load_dotenv()
JWT_KEY = os.getenv("JWT_KEY")

class UserBase(SQLModel):
    email: EmailStr
    username: str
    disabled: bool = False
    type: str

class User(UserBase, table=True):
    email: EmailStr = Field(primary_key=True) 
    username: str
    disabled: bool
    type: str

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

@router.post("/login")
async def login_user(email: Annotated[EmailStr, Form()], session: SessionDep):
    """
    Log in a user and issue an access token.

    This endpoint issues an access token and saves it in the database if not already present.

    Args:
    email: The email of the user trying to log in.
    session: The database session.

    Returns:
    A dictionary with the access token.

    Raises:
    HTTPException: 404 if the user is not found.
    HTTPException: 401 if the password is incorrect or the user is disabled.
    """

    db_user = session.get(User, email)
    if not db_user:
        db_user = User(email=email, username=''.join(random.choices(string.ascii_letters + string.digits, k=6)), disabled=False, type='user')
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    if db_user.disabled:
        raise HTTPException(status_code=401, detail="User is disabled")

    access_token = issue_access_token(email)

    return {"access_token": access_token}

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
        email = payload["email"]

        db_user = session.get(User, email)
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

def issue_access_token(email: str):
    """
    Issue an access token for a user.

    This function creates an access token that contains the email and an
    expiration time (7 days from now). The token is signed with the secret key.

    Args:
        email (str): The email to issue the token for

    Returns:
        str: The issued access token
    """
    payload = {"email": email, "exp": datetime.now(tz=timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, JWT_KEY, algorithm="HS256")


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
        email = payload["email"]

        db_user = session.get(User, email)
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
        email = payload["email"]
        # Verify that the user exists and is active
        db_user = session.get(User, email)
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
        email = payload["email"]

        db_user = session.get(User, email)
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