from fastapi import FastAPI

app = FastAPI(
    title="Howl Vision — Vision Service",
    version="0.1.0",
    description="Specialized vision model serving for veterinary image analysis",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "vision-service"}
