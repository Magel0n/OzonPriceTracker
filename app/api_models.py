from pydantic import BaseModel


class ErrorResponse(BaseModel):
    message: str


class StatusResponse(BaseModel):
    success: bool
    message: str


class UserModel(BaseModel):
    def __eq__(self, other):
        if not isinstance(other, UserModel):
            return NotImplemented
        return self.tid == other.tid and \
            self.name == other.name and \
            self.username == other.username and \
            self.user_pfp == other.user_pfp

    tid: int
    name: str
    username: str
    user_pfp: str | None = None


class CreateTrackingModel(BaseModel):
    user_tid: int
    product_url: str | None = None
    product_sku: str | None = None


class TrackedProductModel(BaseModel):
    def __eq__(self, other):
        if not isinstance(other, TrackedProductModel):
            return NotImplemented
        return self.id == other.id and \
            self.url == other.url and \
            self.sku == other.sku and \
            self.name == other.name and \
            self.price == other.price and \
            self.seller == other.seller and \
            self.tracking_price == other.tracking_price

    id: int | None
    url: str
    sku: str
    name: str
    price: str
    seller: str
    tracking_price: str | None


class TrackingModel(BaseModel):
    def __eq__(self, other):
        if not isinstance(other, TrackingModel):
            return NotImplemented
        return self.user_tid == other.user_tid and \
            self.product_id == other.product_id and \
            self.new_price == other.new_price

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
