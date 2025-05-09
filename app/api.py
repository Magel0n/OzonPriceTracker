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

    scraper = OzonScraper(tgwrapper)

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


@app.get("/alive")
async def alive() -> StatusResponse:
    """
    Simply returns a successfull response, used as a liveness probe
    """
    return StatusResponse(success=True, message="I am in fact, alive")


@app.get("/verify-token")
async def verify_token(
    user_tid: Annotated[int, Depends(validate_token)]
) -> VerifyTokenResponse:
    """
    Verifies the user's JWT token, returning their telegram id
    for further operaion
    """
    return VerifyTokenResponse(user_tid=user_tid)


@app.get("/logout")
async def logout(
    token: Annotated[str, Depends(validate_token_token)]
) -> StatusResponse:
    """
    Adds the user's token to the blacklist, essentially
    loggin them out
    """
    blacklist.add(token)
    return StatusResponse(success=True, message="")


@app.get("/profile")
async def get_user(
    user_tid: Annotated[int, Depends(validate_token)]
) -> UserResponse:
    """
    Gets information for the user's profile page:
    their user info from telegram and the products
    that they are tracking
    """
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
    """
    Adds a new product to the user's tracked products,
    scraping its price and adding it to the database
    """

    # We cannot add product to not ourselves
    if user_tid != tracking.user_tid:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify other user data"
        )

    # Getting the existing products of user
    existing_products = \
        app.state.database.get_tracked_products(user_tid)

    # If any products are the ones the user already owns,
    # do not add it a second time
    if any([(product.url == tracking.product_url or
            product.sku == tracking.product_sku)
           for product in existing_products]
           ):
        raise HTTPException(
            status_code=500,
            detail="You are already tracking this product!"
        )

    # Scrape product info from Ozon
    product = app.state.scraper.scrape_product(
        tracking.product_sku,
        tracking.product_url
    )

    if product is None:
        raise HTTPException(
            status_code=500,
            detail="Product could not be scraped"
        )

    # Add the scraped product to the database
    id = app.state.database.add_product(product)

    if id is None:
        raise HTTPException(
            status_code=500,
            detail="Database could not be inserted into"
        )

    # Add the price of the product to history
    app.state.database.add_to_price_history([id], int(time.time()))

    product.id = id

    # Set default tracking price of product
    default_tracking_price = str(float(product.price) * 0.9)

    # Add the tracking entry to the database
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
    """
    Update the tracking with a new price threshold
    """

    # We cannot modify other users' data
    if user_tid != tracking.user_tid:
        raise HTTPException(
            status_code=500,
            detail="Unauthorized to perform actions on other users"
        )

    # Add the tracking entry to the database
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
    """
    Delete our product from being tracked
    """

    # We cannot modify other users' data
    if user_tid != tracking.user_tid:
        raise HTTPException(
            status_code=500,
            detail="Unauthorized to perform actions on other users"
        )

    # Delete the tracking entry from the database
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
    """
    Get the price history of a product in the form of
    a list of data points
    """
    history = app.state.database.get_price_history(product_id)

    if history is None:
        raise HTTPException(
            status_code=500,
            detail="Could not get price history from database"
        )

    return ProductHistoryResponse(history=history)


def gen_filter_foo(
    search_data: SearchProductsRequest,
    my_products_ids: list[int]
):
    """
    Generate a filter function for the searching functionality
    """
    def filter_foo(product: TrackedProductModel) -> bool:
        # We do not return products we are already tracking
        if product.id in my_products_ids:
            return False
        # Filter by price
        if not search_data.min_price <= float(product.price) \
                <= search_data.max_price:
            return False
        # Filter by name
        if search_data.query and search_data.query.lower() \
                not in product.name.lower():
            return False
        # Filter by seller
        if search_data.seller and search_data.seller.lower() \
                not in product.seller.lower():
            return False
        return True
    return filter_foo


@app.post("/search")
async def search(
    search_data: SearchProductsRequest,
    user_tid: Annotated[int, Depends(validate_token)]
) -> SearchProductsResponse:
    """
    Search products that we are already tracking
    so that the user can add them for themselves
    """

    # Getting the ids of our products for filter
    my_products = app.state.database.get_tracked_products(user_tid)

    if my_products is None:
        raise HTTPException(
            status_code=500,
            detail="Could not get my products from database"
        )

    my_products_ids = \
        set(map(lambda item: item.id, my_products))

    # Getting all products to filter them
    products = app.state.database.get_products()

    if products is None:
        raise HTTPException(
            status_code=500,
            detail="Could not get products from database"
        )

    return SearchProductsResponse(
        products=list(filter(
                gen_filter_foo(search_data, my_products_ids),
                products
        ))
    )

# Run api
if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=os.getenv("API_URL", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "12345")),
        log_level="debug",
        reload=True
    )
