from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as documents_router
from app.api.auth import verify_demo_token
from app.db.session import engine, Base
from app.core.config import settings

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for Route-Clear Fulfillment-to-Settlement Controller",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    documents_router, 
    prefix=f"{settings.API_V1_STR}/documents", 
    tags=["Documents"],
    dependencies=[Depends(verify_demo_token)]
)

@app.get("/health")
def health_check():
    return {"status": "ok"}
