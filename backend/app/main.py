from fastapi import FastAPI
from app.api.endpoints import router as documents_router
from app.db.session import engine, Base
from app.core.config import settings

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for Route-Clear Fulfillment-to-Settlement Controller",
    version="0.1.0",
)

app.include_router(documents_router, prefix=f"{settings.API_V1_STR}/documents", tags=["Documents"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
