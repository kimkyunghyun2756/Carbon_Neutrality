from fastapi import FastAPI
from apps.backend.api.routers_health import router as health_router

app = FastAPI()
app.include_router(health_router)