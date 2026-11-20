from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .core.auth import authenticate, reset_current_user, set_current_user
from .core.router import router as core_router
from .core.component_router import router as component_router
from .core.insights_router import router as insights_router
from .site.router import router as site_router
from .acceptance.router import router as acceptance_router
from .engineering_ai.router import router as engineering_ai_router

app = FastAPI(title="Construction Site Assistant")


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail, "code": f"http_{exc.status_code}"},
                        status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": jsonable_encoder(exc.errors()), "code": "validation_error"}, status_code=422)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/v1") and path != "/api/v1/auth/login":
        value = request.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            return JSONResponse({"detail": "Authentication required", "code": "http_401"}, status_code=401)
        try:
            user = authenticate(value[7:])
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail, "code": f"http_{exc.status_code}"}, status_code=exc.status_code)
        token = set_current_user(user)
        try:
            return await call_next(request)
        finally:
            reset_current_user(token)
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(core_router, prefix="/api/v1")
app.include_router(component_router, prefix="/api/v1")
app.include_router(insights_router, prefix="/api/v1")
app.include_router(site_router, prefix="/api/v1")
app.include_router(acceptance_router, prefix="/api/v1")
app.include_router(engineering_ai_router, prefix="/api/v1")
