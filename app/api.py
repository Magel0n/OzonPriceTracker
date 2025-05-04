import os
from sre_constants import SUCCESS
import uvicorn
from api_models import *
from logging import getLogger
from fastapi import FastAPI
from database import Database
from tgwrapper import create_telegram_wrapper
from scraper import OzonScraper
from contextlib import asynccontextmanager
import logging

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
    
    try:
        # Initialize Telegram bot
        tgwrapper = await create_telegram_wrapper(database)
        await tgwrapper.start()
        logger.info("Telegram bot started successfully")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        raise
    
    # Store components in app state
    app.state.database = database
    app.state.scraper = scraper
    app.state.tgwrapper = tgwrapper
    
    yield
    
    # Cleanup
    try:
        await tgwrapper.stop()
        logger.info("Telegram bot stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping Telegram bot: {e}")

app = FastAPI(lifespan=lifespan)

@app.get("/user/{tid}")
async def get_user(tid) -> UserResponse | ErrorResponse:
    user = app.state.database.get_user(tid)

    if user == None:
        return ErrorResponse(message="Could not retrieve user info")
    
    products = app.state.database.get_tracked_products(tid)
    return UserResponse(
        user=user,
        tracked_products=products
    )

@app.post("/tracking")
async def add_tracking(tracking: CreateTrackingModel) -> TrackedProductModel | ErrorResponse:
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
async def update_threshold(tracking: TrackingModel) -> StatusResponse:
    success = app.state.database.add_tracking(tracking)
    
    if not success:
        return StatusResponse(success=False, message="Error while adding tracking to database")
        
    return StatusResponse(success=True, message="")

@app.delete("/tracking")
async def delete_tracking(tracking: TrackingModel) -> StatusResponse:
    success = app.state.database.delete_tracking(tracking)
    
    if not success:
        return StatusResponse(success=False, message="Error while deleting tracking from database")
        
    return StatusResponse(success=True, message="")
    
@app.get("/product/{product_id}/history")
async def get_product_history(product_id: str) -> ProductHistoryResponse | ErrorResponse:
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
