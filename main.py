import logging

from fastapi import FastAPI
from app.api.routers import router as process_router

from app.core.logger import setup_logger

setup_logger()

app = FastAPI(title="Multi Agent Review System")

@app.get("/")
def root():
    return {"status": "ok"}

app.include_router(process_router)
