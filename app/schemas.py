from pydantic import BaseModel, Field

class ReturnCreate(BaseModel):
    order_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=3, max_length=200)

class ReturnUpdate(BaseModel):
    status: str = Field(..., pattern="^(created|approved|rejected)$")

class ReturnOut(BaseModel):
    id: int
    order_id: int
    reason: str
    status: str

    class Config:
        from_attributes = True
