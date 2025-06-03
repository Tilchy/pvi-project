import aiohttp
import asyncio
import jwt
import json
import os
from datetime import datetime, timezone
from typing import Annotated
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlmodel import Field, SQLModel, Session, select
from pydantic import BaseModel
from app.dependencies import get_session
from app.routers.charts import Chart
from app.routers.users import verify_user

load_dotenv()
JWT_KEY = os.getenv("JWT_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")

class EvaluationBase(SQLModel):
    pass

class Evaluation(EvaluationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(foreign_key="user.email")
    chart: str = Field(foreign_key="chart.name")
    timestamp: datetime
    chat_history: bytes

class Question(BaseModel):
    question: str

router = APIRouter(
    prefix="/evaluations", 
    tags=["evaluations"]
)

SessionDep = Annotated[Session, Depends(get_session)] 


# Check if evaluation exists for current user and chart, evaluations need to be sorted by timestamp (latest first)
# If evaluation exists, return it, else create a new one
@router.get("/{email}/{chart}")
async def get_evaluation(email: str, chart: str, session: SessionDep, authorization: str = Header()):
    """
    Get an evaluation for a user and chart.

    Args:
    user (str): The email of the user to get the evaluation for.
    chart (str): The name of the chart to get the evaluation for.
    session (SessionDep): The database session.
    authorization (str = Header()): The Bearer token to verify the user.

    Returns:
    Evaluation: The evaluation for the user and chart.

    Raises:
    HTTPException: 400 if the user and chart are not provided.
    HTTPException: 401 if the token is invalid or the user is not authorized to access the evaluation.
    HTTPException: 404 if the evaluation is not found.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    if not email or not chart:
        raise HTTPException(status_code=400, detail="User and chart must be provided")
    
    await verify_user(token, session)

    payload = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
    if payload["email"] != email:
        raise HTTPException(status_code=401, detail=f"'{payload['email']}' is not authorized to access evaluation for '{email}'")


    statement = select(Evaluation).where(Evaluation.email == email).where(Evaluation.chart == chart).order_by(Evaluation.timestamp)
    evaluation = session.exec(statement).first()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return evaluation

@router.post("/{email}/{chart}")
async def ask_question(email: str, chart: str, question: Question, session: SessionDep, authorization: str = Header()):
    """
    Handle a user's question for a specific chart evaluation.

    This endpoint allows a user to ask a question related to a specific chart.
    It verifies the user's authorization and checks for the existence of an
    evaluation. If the evaluation does not exist, it creates a new one. If it
    does, it appends the new question to the existing chat history.

    Args:
    email (str): The email of the user asking the question.
    chart (str): The name of the chart related to the question.
    question (Question): The question being asked.
    session (SessionDep): The database session.
    authorization (str, optional): The Bearer token for user verification.

    Returns:
    Evaluation: The updated or newly created evaluation containing the chat history.

    Raises:
    HTTPException: 400 if user, chart, or question is not provided.
    HTTPException: 401 if the token is invalid or user is not authorized.
    HTTPException: 404 if the chart is not found.
    HTTPException: 500 if there is an error decoding existing chat history.
    """
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    if not email or not chart:
        raise HTTPException(status_code=400, detail="Email and chart must be provided")

    if not question.question:
        raise HTTPException(status_code=400, detail="Question must be provided")

    await verify_user(token, session)

    payload = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
    if payload["email"] != email:
        raise HTTPException(status_code=401, detail=f"'{payload['email']}' is not authorized to access evaluation for '{email}'")

    statement = select(Evaluation).where(Evaluation.email == email).where(Evaluation.chart == chart).order_by(Evaluation.timestamp)
    db_evaluation = session.exec(statement).first()

    if not db_evaluation:
        statement = select(Chart).where(Chart.name == chart)
        db_chart = session.exec(statement).first()
        if not db_chart:
            raise HTTPException(status_code=404, detail="Chart not found")
        
        instruction = {
            "role": "system",
            "content": db_chart.instruction
        }

        first_question = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"{question.question}"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"{db_chart.url}"
                    }
                }
            ]
        }

        chat = await send_request_to_openai([instruction, first_question])
        chat_json = json.dumps(chat).encode('utf-8')

        db_evaluation = Evaluation(
            email=email,
            chart=chart,
            timestamp=datetime.now(timezone.utc),
            chat_history=chat_json
        )

        session.add(db_evaluation)
        session.commit()
        session.refresh(db_evaluation)

    else:
        try:
            chat_history: list = json.loads(db_evaluation.chat_history.decode('utf-8'))
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to decode existing chat history")

        new_question = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"{question.question}"
                }
            ]
        }
        chat_history.append(new_question)

        chat_history = await send_request_to_openai(chat_history)

        updated_chat_history = json.dumps(chat_history).encode('utf-8')

        db_evaluation.chat_history = updated_chat_history
        db_evaluation.timestamp = datetime.now(timezone.utc)
        session.add(db_evaluation)
        session.commit()
        session.refresh(db_evaluation)

    return db_evaluation


async def send_request_to_openai(chat: list):
    """
    Non-blocking HTTP request to OpenAI API using aiohttp
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_KEY}"
    }

    data = {
        "model": "gpt-4o-mini",
        "messages": chat,
        "max_completion_tokens": 300
    }

    timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=502, 
                        detail=f"OpenAI API error: {response.status} - {error_text}"
                    )
                
                response_dict = await response.json()
                
        first_message = response_dict["choices"][0]["message"]
        role = first_message["role"]
        content = first_message["content"]

        chat.append({"role": role, "content": content})
        return chat
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="OpenAI API request timed out")
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to OpenAI API: {str(e)}")
    except KeyError as e:
        raise HTTPException(status_code=502, detail=f"Unexpected OpenAI API response format: {str(e)}")