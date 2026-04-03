from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_cases import router as cases_router
from src.api.routes_chat import router as chat_router
from src.config import settings

app = FastAPI(
    title="Howl Vision API",
    version="0.1.0",
    description="Veterinary AI Copilot powered by Gemma 4",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(cases_router)
app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "backend"}
