from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Route-Clear Backend"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "change_me"
    
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./route_clear.db"
    
    VLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_PRIMARY: str = "gemini-3.5-flash-lite"
    GEMINI_MODEL_FALLBACK: str = "gemini-3.8-flash"
    
    ROUTE_MODE: str = "simulation"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024 # 5 MB default

    FRONTEND_ORIGIN: str = "http://localhost:5173"
    DEMO_ACCESS_TOKEN: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
