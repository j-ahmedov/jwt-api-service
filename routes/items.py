from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user, require_admin
from database import ItemORM, UserORM, get_session

router = APIRouter(prefix="/items", tags=["items"])


class ItemCreate(BaseModel):
    name: str = Field(examples=["Widget Pro"])
    price: float = Field(examples=[19.99])


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float = Field(examples=[19.99])
    owner_id: int

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_cents(cls, obj: ItemORM) -> "ItemResponse":
        return cls(id=obj.id, name=obj.name, price=round(obj.price / 100, 2), owner_id=obj.owner_id)


@router.get("/", response_model=list[ItemResponse])
async def list_items(
    _: UserORM = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(ItemORM))
    return [ItemResponse.from_orm_cents(i) for i in result.scalars().all()]


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    _: UserORM = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(ItemORM, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemResponse.from_orm_cents(item)


@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(
    body: ItemCreate,
    current_user: UserORM = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    item = ItemORM(name=body.name, price=round(body.price * 100), owner_id=current_user.id)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return ItemResponse.from_orm_cents(item)


@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    _: UserORM = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(ItemORM, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await session.delete(item)
    await session.commit()
    return {"detail": f"Item {item_id} deleted"}
