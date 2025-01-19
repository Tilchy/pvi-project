from fastapi import  FastAPI

from .dependencies import lifespan
from .routers import users, charts, evaluations, reset

app = FastAPI(lifespan=lifespan)

app.include_router(users.router)
app.include_router(charts.router)
app.include_router(evaluations.router)
app.include_router(reset.router)