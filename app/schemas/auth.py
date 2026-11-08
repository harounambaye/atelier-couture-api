from pydantic import BaseModel


class Jeton(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int