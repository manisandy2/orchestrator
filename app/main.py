import logging

from fastapi import FastAPI
from app.api.routers import router as process_router

from app.core.logger import setup_logger

setup_logger()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import db
    db.create_tables()
    yield

app = FastAPI(title="Multi Agent Review System", lifespan=lifespan)

@app.get("/")
def root():
    return {"status": "ok"}

app.include_router(process_router)
