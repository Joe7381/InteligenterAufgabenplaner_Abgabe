from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from dependencies import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware # Added import
import os
from dotenv import load_dotenv

# Routers
from routers.auth import router as auth_router
from routers.tasks import router as tasks_router
from routers.chat import router as chat_router
from routers.calendar import router as calendar_router

load_dotenv()

app = FastAPI()

# Rate Limiter Setup (Globally available via app.state.limiter)
# limiter imported from dependencies
app.state.limiter = limiter

# Custom Rate Limit Handler
def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    limit_info = str(exc.limit) if hasattr(exc, "limit") else "einigen"
    return JSONResponse(
        status_code=429,
        content={"detail": f"Zu viele Anfragen. Limit überschritten ({limit_info}). Bitte warten Sie kurz."},
    )
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# Custom Middleware for Security Headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Middleware
app.add_middleware(
    CORSMiddleware,
    # Allow explicit origins only (Strict CORS)
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    # Strict Host Header Validation
    allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0"] 
)

# Include Routers
app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(chat_router)
app.include_router(calendar_router)

# Mount Static Files (Frontend)
frontend_build_path = os.path.join(os.path.dirname(__file__), 'frontend', 'build')
if os.path.exists(frontend_build_path):
    app.mount("/", StaticFiles(directory=frontend_build_path, html=True), name="static")
else:
    print(f"Warning: Frontend build path not found at {frontend_build_path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
