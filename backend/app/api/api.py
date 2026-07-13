from fastapi import APIRouter

from app.api.v1 import auth, calendar, chat, favorites, policies, recommend, review, users
api_router = APIRouter()

# v1 라우터 등록
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(favorites.router, prefix="/favorites", tags=["Favorites"])
api_router.include_router(policies.router, prefix="/policies", tags=["Policies"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["Calendar"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat RAG"])
api_router.include_router(recommend.router, prefix="/recommend", tags=["Recommend"])
api_router.include_router(review.router, prefix="/review", tags=["Review"])
