from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.database import init_db
from app.routers import web

app = FastAPI(title="Meeting Scribe")

# Монтируем статику (JS/CSS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключаем роутер
app.include_router(web.router)

@app.on_event("startup")
def on_startup():
    init_db()