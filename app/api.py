import os
import uvicorn
from api_models import *
from logging import getLogger
from fastapi import FastAPI
from database import Database
from tgwrapper import TelegramWrapper
from scraper import OzonScraper

database: Database = Database()
tgwrapper: TelegramWrapper = TelegramWrapper(database)
scraper: OzonScraper = OzonScraper(database)

#tgwrapper.start()

api_url = os.environ.get("API_URL", "0.0.0.0")
api_port = int(os.environ.get("API_PORT", "12345"))

app = FastAPI()

@app.get("/user/{tid}")
async def get_user(tid) -> UserResponse | ErrorResponse:
    user = database.get_user(tid)
    
    if user == None:
        return ErrorResponse(message="Could not retrieve user info")
    return UserResponse(
        user = user,
        tracked_products = products
    )

@app.post("/tracking")
async def add_tracking(tracking: CreateTrackingModel) -> TrackedProductModel | ErrorResponse:
    product = scraper.scrape_product(tracking.product_sku, tracking.product_url)
    
    if product == None:
        return ErrorResponse(message="Product could not be scraped")
        
    id = database.add_product(product)
    
    if id == None:
        return ErrorResponse(message="Database could not be inserted into")
    
    product.id = id
    
    default_tracking_price = str(float(product.price) * 0.9)
    
    success = database.add_tracking(TrackingModel(tracking.user_tid, id, default_tracking_price))
    
    if not success:
        return ErrorResponse(message="Error while adding tracking to database")
        
    return product

@app.put("/tracking")
async def update_threshold(tracking: TrackingModel) -> StatusResponse:
    success = database.add_tracking(tracking)
    
    if not success:
        return StatusResponse(success=false, message="Error while adding tracking to database")
        
    return StatusResponse(success=true, message="")

@app.delete("/tracking")
async def delete_tracking(tracking: TrackingModel) -> StatusResponse:
    
    success = database.delete_tracking(tracking)
    
    if not success:
        return StatusResponse(false, "Error while deleting tracking from database")
        
    return StatusResponse(success=false, message="i do not do anything yet cuz i forgor to add to disdoc")
    
@app.get("/product/{product_id}/history")
async def get_product_history(product_id: str) -> ProductHistoryResponse | ErrorResponse:
    history = database.get_price_history(product_id)
    
    if history == None:
        return ErrorResponse(message="Could not get price history from database")
    
    return ProductHistoryResponse(history=history)
    

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=api_url,
        port=api_port,
        log_level="debug",
    )
