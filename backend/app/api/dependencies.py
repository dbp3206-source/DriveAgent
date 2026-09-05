"""FastAPI dependencies dùng chung cho authentication và authorization."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import permissions_for_role
from app.db.models import User
from app.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(request: Request, db: DbSession) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn chưa đăng nhập.")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không còn hợp lệ.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: str):  # type: ignore[no-untyped-def]
    async def dependency(user: CurrentUser) -> User:
        if permission not in permissions_for_role(user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Vai trò {user.role} không có quyền {permission}.",
            )
        return user

    return dependency
