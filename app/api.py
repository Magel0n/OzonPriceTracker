import os
import random
import string
from sre_constants import SUCCESS
import uvicorn
import time
from api_models import *
from logging import getLogger
from fastapi import FastAPI
from database import Database
from tgwrapper import create_telegram_wrapper
from scraper import OzonScraper
from contextlib import asynccontextmanager
import logging
from typing import Annotated
import jwt
from fastapi import Depends, FastAPI, HTTPException, status, Request
from jwt.exceptions import InvalidTokenError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

TOKEN_ENCRYPTION_ALGORITHM = os.environ.get("TOKEN_ENCRYPTION_ALGORITHM", "HS256")

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
    scraper = OzonScraper(database)
    
    secret_key = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(32))
    
    try:
        # Initialize Telegram bot
        tgwrapper = await create_telegram_wrapper(database, secret_key)
        await tgwrapper.start()
        logger.info("Telegram bot started successfully")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        raise
    
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
            
async def validate_token(token: Annotated[str, Depends(HTTPBearer())]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if token.scheme != "Bearer":
            raise credentials_exception
        payload = jwt.decode(token.credentials, app.state.secret_key, algorithms=[TOKEN_ENCRYPTION_ALGORITHM])
        user_id = payload.get("id")
        if user_id is None:
            raise credentials_exception
        return user_id
    except InvalidTokenError:
        raise credentials_exception


@app.get("/profile")
async def get_user(user_tid: Annotated[str, Depends(validate_token)]) -> UserResponse | ErrorResponse:
    user = app.state.database.get_user(tid)

    if user == None:
        return ErrorResponse(message="Could not retrieve user info")
    
    products = app.state.database.get_tracked_products(tid)
    return UserResponse(
        user=user,
        tracked_products=products
    )

@app.post("/tracking")
async def add_tracking(tracking: CreateTrackingModel, user_tid: Annotated[str, Depends(validate_token)]) -> TrackedProductModel | ErrorResponse:
    if user_tid != tracking.user_tid:
        return ErrorResponse(message="Unauthorized to perform actions on other users")
        
    product = app.state.scraper.scrape_product(tracking.product_sku, tracking.product_url)
    
    if product == None:
        return ErrorResponse("Product could not be scraped")
        
    id = app.state.database.add_product(product)
    
    if id == None:
        return ErrorResponse("Database could not be inserted into")
    
    product.id = id
    
    default_tracking_price = str(float(product.price) * 0.9)
    
    success = app.state.database.add_tracking(TrackingModel(tracking.user_tid, id, default_tracking_price))
    
    if not success:
        return ErrorResponse("Error while adding tracking to database")
        
    return product

@app.put("/tracking")
async def update_threshold(tracking: TrackingModel, user_tid: Annotated[str, Depends(validate_token)]) -> StatusResponse:
    if user_tid != tracking.user_tid:
        return ErrorResponse(message="Unauthorized to perform actions on other users")

    success = app.state.database.add_tracking(tracking)
    
    if not success:
        return StatusResponse(success=False, message="Error while adding tracking to database")
        
    return StatusResponse(success=True, message="")

@app.delete("/tracking")
async def delete_tracking(tracking: TrackingModel, user_tid: Annotated[str, Depends(validate_token)]) -> StatusResponse:
    if user_tid != tracking.user_tid:
        return ErrorResponse(message="Unauthorized to perform actions on other users")

    success = app.state.database.delete_tracking(tracking)
    
    if not success:
        return StatusResponse(success=False, message="Error while deleting tracking from database")
        
    return StatusResponse(success=True, message="")
    
@app.get("/product/{product_id}/history")
async def get_product_history(product_id: str, user_tid: Annotated[str, Depends(validate_token)]) -> ProductHistoryResponse | ErrorResponse:
    history = app.state.database.get_price_history(product_id)
    
    if history == None:
        return ErrorResponse("Could not get price history from database")
    
    return ProductHistoryResponse(history)
    

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=os.getenv("API_URL", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "12345")),
        log_level="debug",
        reload=True
    )
