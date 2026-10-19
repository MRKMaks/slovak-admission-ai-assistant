from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.config import settings

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
    )
    application.include_router(api_router, prefix=settings.API_V1_STR)
    return application

app = create_application()