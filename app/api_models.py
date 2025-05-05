from pydantic import BaseModel

class ErrorResponse(BaseModel):
    message: str

class StatusResponse(BaseModel):
    success: bool
    message: str

class UserModel(BaseModel):
    tid: int
    name: str
    username: str
    user_pfp: str | None = None
    
class CreateTrackingModel(BaseModel):
    user_tid: int
    product_url: str | None = None
    product_sku: str | None = None

class TrackedProductModel(BaseModel):
    id: int | None
    url: str
    sku: str
    name: str
    price: str
    seller: str
    tracking_price: str | None
    
class TrackingModel(BaseModel):
    user_tid: int
    product_id: int
    new_price: str | None

class UserResponse(BaseModel):
    user: UserModel
    tracked_products: list[TrackedProductModel]

class VerifyTokenResponse(BaseModel):
    user_tid: int

class ProductHistoryResponse(BaseModel):
    # Unix epoch seconds to price in string
    history: list[tuple[int, str]]
