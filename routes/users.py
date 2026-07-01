from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user, require_admin
from database import UserORM, get_session
from models.user import Role, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


class RoleUpdate(BaseModel):
    role: Role


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserORM = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=list[UserResponse])
async def list_users(
    _: UserORM = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(UserORM))
    return result.scalars().all()


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    body: RoleUpdate,
    current_admin: UserORM = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot change their own role",
        )
    user = await session.get(UserORM, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = body.role
    await session.commit()
    await session.refresh(user)
    return user
