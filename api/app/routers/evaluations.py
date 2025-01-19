from datetime import datetime, timezone
import json
import os
from typing import Annotated
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Header
import jwt
import requests
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
    user: str = Field(foreign_key="user.username")
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
@router.get("/{user}/{chart}")
def get_evaluation(user: str, chart: str, session: SessionDep, authorization: str = Header()):
    """
    Get an evaluation for a user and chart.

    Args:
    user (str): The username of the user to get the evaluation for.
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

    if not user or not chart:
        raise HTTPException(status_code=400, detail="User and chart must be provided")
    
    verify_user(token, session)

    payload = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
    if payload["username"] != user:
        raise HTTPException(status_code=401, detail=f"'{payload['username']}' is not authorized to access evaluation for '{user}'")


    statement = select(Evaluation).where(Evaluation.user == user).where(Evaluation.chart == chart).order_by(Evaluation.timestamp)
    evaluation = session.exec(statement).first()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return evaluation

@router.post("/{user}/{chart}")
async def ask_question(user: str, chart: str, question: Question, session: SessionDep, authorization: str = Header()):
    """
    Handle a user's question for a specific chart evaluation.

    This endpoint allows a user to ask a question related to a specific chart.
    It verifies the user's authorization and checks for the existence of an
    evaluation. If the evaluation does not exist, it creates a new one. If it
    does, it appends the new question to the existing chat history.

    Args:
    user (str): The username of the user asking the question.
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

    if not user or not chart:
        raise HTTPException(status_code=400, detail="User and chart must be provided")
    
    if not question.question:
        raise HTTPException(status_code=400, detail="Question must be provided")

    verify_user(token, session)

    payload = jwt.decode(token, JWT_KEY, algorithms=["HS256"])
    if payload["username"] != user:
        raise HTTPException(status_code=401, detail=f"'{payload['username']}' is not authorized to access evaluation for '{user}'")

    statement = select(Evaluation).where(Evaluation.user == user).where(Evaluation.chart == chart).order_by(Evaluation.timestamp)
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

        chat = send_request_to_openai([instruction, first_question])

        chat = json.dumps(chat).encode('utf-8')

        db_evaluation = Evaluation(
            user=user,
            chart=chart,
            timestamp=datetime.now(timezone.utc),
            chat_history=chat
        )

        session.add(db_evaluation)
        session.commit()
        session.refresh(db_evaluation)

    else:
        try:
            chat_history: list = json.loads(db_evaluation.chat_history.decode('utf-8'))
        except (json.JSONDecodeError):
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

        chat_history = send_request_to_openai(chat_history)

        print(chat_history)

        updated_chat_history = json.dumps(chat_history).encode('utf-8')

        db_evaluation.chat_history = updated_chat_history
        db_evaluation.timestamp = datetime.now(timezone.utc)  # Update the timestamp
        session.add(db_evaluation)
        session.commit()
        session.refresh(db_evaluation)

    return db_evaluation


def send_request_to_openai(chat: list):
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

    response = requests.post(url, headers=headers, json=data)
    response_dict = response.json()
    first_message = response_dict["choices"][0]["message"]
    role = first_message["role"]
    content = first_message["content"]

    chat.append({"role": role, "content": content})

    return chat