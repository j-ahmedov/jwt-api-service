from enum import Enum
from pydantic import BaseModel, Field, field_validator


class Role(str, Enum):
    admin = "admin"
    user = "user"


class UserCreate(BaseModel):
    username: str = Field(examples=["demo"])
    email: str = Field(examples=["demo@example.com"])
    password: str = Field(examples=["demo1234"])

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        assert v.isalnum(), "Username must be alphanumeric"
        assert len(v) >= 3, "Username must be at least 3 characters"
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        assert len(v) >= 8, "Password must be at least 8 characters"
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}
