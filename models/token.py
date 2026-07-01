from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str          # user id (RFC 7519: string)
    role: str
    jti: str          # unique token id for revocation
    exp: int
    iat: int
    type: str         # "access" or "refresh"
