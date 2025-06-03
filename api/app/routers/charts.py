import re

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlmodel import Field, SQLModel, Session, select

from app.dependencies import get_session
from app.routers.users import verify_if_admin, verify_user

class ChartBase(SQLModel):
    name: str
    description: str
    instruction: str
    url: str

class Chart(ChartBase, table=True):
    name: str = Field(primary_key=True)
    description: str
    instruction: str
    url: str

class ChartCreate(ChartBase):
    pass

class ChartUpdate(ChartBase):
    name: Optional[str] = None
    description: Optional[str] = None
    instruction: Optional[str] = None
    url: Optional[str] = None


router = APIRouter(
    prefix="/charts", 
    tags=["charts"]
)

SessionDep = Annotated[Session, Depends(get_session)] 

@router.post("/")
def create_chart(chart: ChartCreate, session: SessionDep, authorization: str = Header()):

    """
    Create a new chart.

    This endpoint creates a new chart in the database.

    Args:
    chart: The chart data to create.
    session: The database session.

    Returns:
    The created chart.

    Raises:
    HTTPException: 401 if the access token is invalid.
    HTTPException: 400 if the chart name contains invalid characters or a chart with the same filename already exists.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    verify_if_admin(token, session)

    if not re.fullmatch(r"[a-z0-9-]+", chart.name):
        raise HTTPException(status_code=400, detail="Chart name can only contain lowercase alphanumeric characters and hyphens")

    statement = select(Chart).where(Chart.name == chart.name)
    if session.exec(statement).first():
        raise HTTPException(status_code=400, detail="Chart with this filename already exists")
    
    db_chart = Chart(
        name=chart.name,
        description=chart.description,
        instruction=chart.instruction,
        url=chart.url
    )
    session.add(db_chart)
    session.commit()
    session.refresh(db_chart)

    return db_chart

@router.get("/{filename}")
async def get_chart(filename: str, session: SessionDep, authorization: str = Header()):
    """
    Retrieve a chart by filename.

    This endpoint retrieves a specific chart from the database using the provided filename.

    Args:
    filename: The filename of the chart to retrieve.
    session: The database session.
    authorization: The Bearer token for user verification.

    Returns:
    The requested chart if found.

    Raises:
    HTTPException: 401 if the token is invalid.
    HTTPException: 404 if the chart is not found.
    """

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    await verify_user(token, session)

    db_chart = session.get(Chart, filename)
    if not db_chart:
        raise HTTPException(status_code=404, detail="Chart not found")

    return db_chart

@router.get("/", response_model=list[ChartBase])
async def list_charts(session: SessionDep, authorization: str = Header()):
    """
    List all charts.

    This endpoint retrieves all charts from the database.

    Args:
    session: The database session.
    authorization: The Bearer token for user verification.

    Returns:
    A list of all charts.

    Raises:
    HTTPException: 401 if the token is invalid.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    await verify_user(token, session)

    statement = select(Chart)
    charts = session.exec(statement).all()

    return charts

@router.put("/{filename}", response_model=ChartBase)
async def update_chart(filename: str, chart: ChartUpdate, session: SessionDep, authorization: str = Header()):
    """
    Update a chart.

    This endpoint updates an existing chart in the database with the provided
    chart data. The user must have admin privileges to perform this operation.

    Args:
    filename: The filename of the chart to update.
    chart: The chart data to update.
    session: The database session.
    authorization: The Bearer token for user verification.

    Returns:
    The updated chart.

    Raises:
    HTTPException: 401 if the token is invalid or the user is not an admin.
    HTTPException: 404 if the chart is not found.
    """

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    verify_if_admin(token, session)

    db_chart = session.get(Chart, filename)
    if not db_chart:
        raise HTTPException(status_code=404, detail="Chart not found")

    chart_data = chart.model_dump(exclude_unset=True)
    for key, value in chart_data.items():
        setattr(db_chart, key, value)

    session.commit()
    session.refresh(db_chart)

    return db_chart

@router.delete("/{filename}", status_code=204)
async def delete_chart(filename: str, session: SessionDep, authorization: str = Header()):
    """
    Delete a chart by filename.

    This endpoint deletes a chart from the database.

    Args:
    filename: The filename of the chart to delete.
    session: The database session.
    authorization: The Bearer token for user verification.

    Returns:
    None

    Raises:
    HTTPException: 401 if the token is invalid or the user is not an admin.
    HTTPException: 404 if the chart is not found.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]

    verify_if_admin(token, session)

    db_chart = session.get(Chart, filename)
    if not db_chart:
        raise HTTPException(status_code=404, detail="Chart not found")

    session.delete(db_chart)
    session.commit()