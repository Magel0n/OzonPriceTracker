import os
import random
import string
import time
import logging
from contextlib import asynccontextmanager
from typing import Annotated

import jwt
from jwt.exceptions import InvalidTokenError

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles

from api_models import (
    StatusResponse,
    CreateTrackingModel,
    TrackedProductModel,
    TrackingModel,
    UserResponse,
    VerifyTokenResponse,
    ProductHistoryResponse,
    SearchProductsRequest,
    SearchProductsResponse
)
from database import Database
from tgwrapper import create_telegram_wrapper
from scraper import OzonScraper

TOKEN_ENCRYPTION_ALGORITHM = \
    os.environ.get("TOKEN_ENCRYPTION_ALGORITHM", "HS256")

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize components
    database = Database()

    secret_key = ''.join(
        random.SystemRandom().choice(string.ascii_letters + string.digits)
        for _ in range(32)
    )

    try:
        # Initialize Telegram bot
        tgwrapper = await create_telegram_wrapper(database, secret_key)
        await tgwrapper.start()
        logger.info("Telegram bot started successfully")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        raise

    scraper = OzonScraper(database, tgwrapper)

    # Store components in app state
    app.state.database = database
    app.state.scraper = scraper
    app.state.tgwrapper = tgwrapper
    app.state.secret_key = secret_key

    yield

    # Cleanup
    try:
        await tgwrapper.stop()
        logger.info("Telegram bot stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping Telegram bot: {e}")

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

blacklist = set()


async def validate_token(token: Annotated[str, Depends(HTTPBearer())]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if token.scheme != "Bearer":
            raise credentials_exception
        if token.credentials in blacklist:
            raise credentials_exception
        payload = jwt.decode(
            token.credentials,
            app.state.secret_key,
            algorithms=[TOKEN_ENCRYPTION_ALGORITHM]
        )
        user_id = payload.get("id")
        if user_id is None:
            raise credentials_exception
        return int(user_id)
    except InvalidTokenError:
        raise credentials_exception


async def validate_token_token(token: Annotated[str, Depends(HTTPBearer())]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if token.scheme != "Bearer":
            raise credentials_exception
        if token.credentials in blacklist:
            raise credentials_exception
        payload = jwt.decode(
            token.credentials,
            app.state.secret_key,
            algorithms=[TOKEN_ENCRYPTION_ALGORITHM]
        )
        user_id = payload.get("id")
        if user_id is None:
            raise credentials_exception
        return token.credentials
    except InvalidTokenError:
        raise credentials_exception


@app.get("/verify-token")
async def verify_token(
    user_tid: Annotated[int, Depends(validate_token)]
) -> VerifyTokenResponse:
    return VerifyTokenResponse(user_tid=user_tid)


@app.get("/logout")
async def logout(
    token: Annotated[str, Depends(validate_token_token)]
) -> StatusResponse:
    blacklist.add(token)
    return StatusResponse(success=True, message="")


@app.get("/profile")
async def get_user(
    user_tid: Annotated[int, Depends(validate_token)]
) -> UserResponse:
    user = app.state.database.get_user(user_tid)

    if user is None:
        raise HTTPException(status_code=500, detail="Could not find user data")

    products = app.state.database.get_tracked_products(user_tid)
    return UserResponse(
        user=user,
        tracked_products=products
    )


@app.post("/tracking")
async def add_tracking(
    tracking: CreateTrackingModel,
    user_tid: Annotated[int, Depends(validate_token)]
) -> TrackedProductModel:
    logger.info(f"{user_tid}, {tracking.user_tid}")
    if user_tid != tracking.user_tid:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify other user data"
        )

    product = app.state.scraper.scrape_product(
        tracking.product_sku,
        tracking.product_url
    )

    if product is None:
        raise HTTPException(
            status_code=500,
            detail="Product could not be scraped"
        )

    id = app.state.database.add_product(product)

    if id is None:
        raise HTTPException(
            status_code=500,
            detail="Database could not be inserted into"
        )

    app.state.database.add_to_price_history([id], int(time.time()))

    product.id = id

    default_tracking_price = str(float(product.price) * 0.9)

    success = app.state.database.add_tracking(TrackingModel(
        user_tid=tracking.user_tid,
        product_id=id,
        new_price=default_tracking_price
    ))

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Error while adding tracking to database"
        )

    return product


@app.put("/tracking")
async def update_threshold(
    tracking: TrackingModel,
    user_tid: Annotated[int, Depends(validate_token)]
) -> StatusResponse:
    if user_tid != tracking.user_tid:
        raise HTTPException(
            status_code=500,
            detail="Unauthorized to perform actions on other users"
        )

    success = app.state.database.add_tracking(tracking)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Error while adding tracking to database"
        )

    return StatusResponse(success=True, message="")


@app.delete("/tracking")
async def delete_tracking(
    tracking: TrackingModel,
    user_tid: Annotated[int, Depends(validate_token)]
) -> StatusResponse:
    if user_tid != tracking.user_tid:
        raise HTTPException(
            status_code=500,
            detail="Unauthorized to perform actions on other users"
        )

    success = app.state.database.delete_tracking(tracking)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Error while deleting tracking from database"
        )

    return StatusResponse(success=True, message="")


@app.get("/product/{product_id}/history")
async def get_product_history(
    product_id: int,
    user_tid: Annotated[int, Depends(validate_token)]
) -> ProductHistoryResponse:
    history = app.state.database.get_price_history(product_id)

    if history is None:
        raise HTTPException(
            status_code=500,
            detail="Could not get price history from database"
        )

    return ProductHistoryResponse(history=history)


@app.post("/search")
async def search(
    search_data: SearchProductsRequest,
    user_tid: Annotated[int, Depends(validate_token)]
) -> SearchProductsResponse:
    tracked_products = \
        set(map(lambda item: item.product_id,
            app.state.database.get_tracked_products(user_tid)))

    def filter_foo(product: TrackedProductModel) -> bool:
        if product.id in tracked_products:
            return False
        if not search_data.min_price <= float(product['price']) \
                <= search_data.max_price:
            return False
        if search_data.query and search_data.query.lower() \
                not in product['name'].lower():
            return False
        if search_data.seller and search_data.seller.lower() \
                not in product['seller'].lower():
            return False
        return True

    products = app.state.database.get_products()

    if products is None:
        raise HTTPException(
            status_code=500,
            detail="Could not get products from database"
        )

    return SearchProductsResponse(products=filter(filter_foo, products))


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=os.getenv("API_URL", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "12345")),
        log_level="debug",
        reload=True
    )
