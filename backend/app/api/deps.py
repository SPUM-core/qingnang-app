"""api deps - 依赖注入"""
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from jose import JWTError

from ..database import get_db
from ..utils.security import decode_access_token
from ..models import User


async def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> User:
    """从 Bearer Token 解析当前用户"""
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="无效的认证头")
    except ValueError:
        raise HTTPException(status_code=401, detail="缺少 Bearer Token")

    sub = decode_access_token(token)
    if not sub:
        raise HTTPException(status_code=401, detail="Token 已过期或无效")

    user = db.query(User).filter(User.qingnang_id == sub).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


async def get_current_doctor(
    current: User = Depends(get_current_user),
) -> User:
    """确保当前用户是医生"""
    if not current.is_doctor:
        raise HTTPException(status_code=403, detail="需要医生权限")
    return current
