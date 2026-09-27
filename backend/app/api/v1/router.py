"""v1 router 汇总"""
from fastapi import APIRouter
from . import auth, cases, ppg, treatment, friends, assistant, shop, challenges, notifications, doctor, knowledge

api_router = APIRouter()

api_router.include_router(auth.router,           prefix="/auth",          tags=["认证"])
api_router.include_router(cases.router,          prefix="/cases",         tags=["案例"])
api_router.include_router(ppg.router,            prefix="/ppg",           tags=["PPG 采集"])
api_router.include_router(treatment.router,      prefix="/treatment",     tags=["调理方案"])
api_router.include_router(friends.router,        prefix="/friends",       tags=["好友"])
api_router.include_router(assistant.router,      prefix="/assistant",     tags=["青囊管家 AI"])
api_router.include_router(shop.router,            prefix="/shop",          tags=["商城"])
api_router.include_router(challenges.router,      prefix="/challenges",    tags=["挑战打卡"])
api_router.include_router(notifications.router,  prefix="/notifications", tags=["生活提醒"])
api_router.include_router(doctor.router,         prefix="/doctor",        tags=["医生端"])
api_router.include_router(knowledge.router,      prefix="/knowledge",     tags=["知识库"])
