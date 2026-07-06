# main.py

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import pages, auth, profile, recommendations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем приложение
app = FastAPI(
    title="Daily Tuner Web Interface",
    version="2.0.0",
    description="Веб-интерфейс с поддержкой аутентификации"
)

# CORS (для разработки)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(recommendations.router)

# Для обратной совместимости - оставляем старые endpoints
# (чтобы не сломать существующие ссылки)

@app.on_event("shutdown")
async def shutdown_event():
    """Закрытие ресурсов при завершении"""
    from .web_client import web_client
    await web_client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "web.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True
    )
