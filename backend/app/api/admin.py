"""Quản trị vai trò tối giản cho mô hình nhiều người dùng."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.auth import user_response
from app.api.dependencies import DbSession, require_permission
from app.api.schemas import UserResponse
from app.auth.permissions import ROLE_PERMISSIONS, USER_MANAGE
from app.db.models import User, UserRole

router = APIRouter(prefix="/api/admin", tags=["admin"])


class RoleUpdate(BaseModel):
    role: UserRole


@router.get("/users", response_model=list[UserResponse])
async def list_users(db: DbSession, _admin: User = Depends(require_permission(USER_MANAGE))):
    return [user_response(user) for user in (await db.scalars(select(User))).all()]


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_role(
    user_id: str,
    payload: RoleUpdate,
    db: DbSession,
    admin: User = Depends(require_permission(USER_MANAGE)),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    if user.id == admin.id and payload.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=400, detail="Không thể tự hạ quyền super admin đang đăng nhập."
        )
    user.role = payload.role.value
    await db.commit()
    return user_response(user)


@router.get("/roles")
async def list_roles(_admin: User = Depends(require_permission(USER_MANAGE))):
    return {role: sorted(permissions) for role, permissions in ROLE_PERMISSIONS.items()}
