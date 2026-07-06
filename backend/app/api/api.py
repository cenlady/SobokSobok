from fastapi import APIRouter
from app.api.v1 import auth, users

api_router = APIRouter()

# v1 라우터 등록
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
