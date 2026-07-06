from fastapi import APIRouter
from app.api.v1 import auth, users, policies, recommend, chat, review, calendar

api_router = APIRouter()

# v1 라우터 등록
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(policies.router, prefix="/policies", tags=["Policies"])       # 김정연
api_router.include_router(recommend.router, prefix="/recommend", tags=["Recommend"])    # 안주현
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])                   # 김정연
api_router.include_router(review.router, prefix="/review", tags=["Review"])             # 이충헌
api_router.include_router(calendar.router, prefix="/calendar", tags=["Calendar"])       # 이재혁
