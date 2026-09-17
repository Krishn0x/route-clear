from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader
from app.core.config import settings

api_key_header = APIKeyHeader(name="x-demo-token", auto_error=False)

def verify_demo_token(api_key: str = Security(api_key_header)):
    if not settings.DEMO_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Server misconfiguration: DEMO_ACCESS_TOKEN not set")
    if not api_key or api_key != settings.DEMO_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing demo token")
    return api_key
