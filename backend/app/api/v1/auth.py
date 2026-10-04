"""auth - 注册 / 登录"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ...database import get_db
from ...models import User
from ...utils.security import hash_pwd, verify_pwd, create_access_token
from ..deps import get_current_user

router = APIRouter()


class RegisterIn(BaseModel):
    phone: str = Field(..., min_length=6, max_length=20)
    password: str = Field(..., min_length=6)
    nickname: str = Field(default="")
    gender: str = Field(default="")
    height: int | None = Field(default=None, ge=30, le=250)   # cm, onboarding 补填
    weight: float | None = Field(default=None, ge=10, le=250)  # kg, onboarding 补填
    birth_date: str = Field(default="")
    birth_hour: str = Field(default="")


class LoginIn(BaseModel):
    phone: str
    password: str


class TokenOut(BaseModel):
    token: str
    token_type: str = "bearer"
    qingnang_id: str
    nickname: str
    is_doctor: bool
    is_onboarded: bool


def gen_qingnang_id(db: Session) -> str:
    """生成 QN-xxxxxx 格式的青囊 ID"""
    import random, string
    while True:
        suffix = "".join(random.choices(string.digits, k=6))
        qid = f"QN-{suffix}"
        if not db.query(User).filter(User.qingnang_id == qid).first():
            return qid


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """注册新用户 - 自动生成青囊 ID + 五形初始基底（等 onboarding）"""
    if db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(status_code=400, detail="手机号已注册")

    qid = gen_qingnang_id(db)
    user = User(
        qingnang_id=qid,
        phone=body.phone,
        password_hash=hash_pwd(body.password),
        nickname=body.nickname or f"青囊用户_{qid[-4:]}",
        gender=body.gender,
        birth_date=body.birth_date,
        birth_hour=body.birth_hour,
        height=body.height,
        weight=body.weight,
        is_doctor=False,
        is_onboarded=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenOut(
        token=create_access_token(user.qingnang_id),
        qingnang_id=user.qingnang_id,
        nickname=user.nickname,
        is_doctor=False,
        is_onboarded=False,
    )


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    """登录 - 支持手机号"""
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user or not verify_pwd(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")

    return TokenOut(
        token=create_access_token(user.qingnang_id),
        qingnang_id=user.qingnang_id,
        nickname=user.nickname,
        is_doctor=user.is_doctor,
        is_onboarded=user.is_onboarded,
    )


@router.get("/me")
def me(current: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "qingnang_id": current.qingnang_id,
        "nickname": current.nickname,
        "gender": current.gender,
        "birth_date": current.birth_date,
        "birth_hour": current.birth_hour,
        "height": current.height,
        "weight": current.weight,
        "is_doctor": current.is_doctor,
        "is_onboarded": current.is_onboarded,
        "v_base": current.v_base,
    }


class MePatch(BaseModel):
    nickname: str | None = None
    gender: str | None = None
    # PATCH 端点放宽 ge/le — 问诊自动补填场景可能来自 number input，允许更宽范围
    height: int | None = Field(default=None, ge=30, le=250)
    weight: float | None = Field(default=None, ge=10, le=250)
    birth_date: str | None = None
    birth_hour: str | None = None


@router.patch("/me")
def patch_me(body: MePatch, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """更新当前用户信息（问诊流程补填身高体重走这里）"""
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(current, k, v)
    db.commit()
    db.refresh(current)
    return me(current)
