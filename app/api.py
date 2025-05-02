import os
import uvicorn
from api_models import *
from fastapi import FastAPI
from database import Database
from tgwrapper import TelegramWrapper
from scraper import OzonScraper

database: Database = None
tgwrapper: TelegramWrapper = None
scraper: OzonScraper = None

api_url = os.environ.get("API_URL", "0.0.0.0")
api_port = int(os.environ.get("API_PORT", "12345"))

app = FastAPI()

@app.get("/user/{tid}")
async def get_user(tid) -> UserResponse | ErrorResponse:
    user = tgwrapper.get_user_info(tid)
    products = database.get_tracked_products(tid)
    
    if user == None:
        return ErrorResponse("Could not retrieve user info")
    return UserResponse(
        user = user,
        tracked_products = products
    )

@app.post("/tracking")
async def add_tracking(tracking: CreateTrackingModel) -> TrackedProductModel | ErrorResponse:
    product = scraper.scrape_product(tracking.product_sku, tracking.product_url)
    
    if product == None:
        return ErrorResponse("Product could not be scraped")
        
    id = database.add_product(product)
    
    if id == None:
        return ErrorResponse("Database could not be inserted into")
    
    product.id = id
    
    default_tracking_price = str(float(product.price) * 0.9)
    
    success = database.add_tracking(TrackingModel(tracking.user_tid, id, default_tracking_price))
    
    if not success:
        return ErrorResponse("Error while adding tracking to database")
        
    return product

@app.put("/tracking")
async def update_threshold(tracking: TrackingModel) -> StatusResponse:
    success = database.add_tracking(tracking)
    
    if not success:
        return StatusResponse(false, "Error while adding tracking to database")
        
    return StatusResponse(true, "")

@app.delete("/tracking")
async def delete_tracking(tracking: TrackingModel) -> StatusResponse:
    
    # success = database.add_tracking(tracking)
    
    #if not success:
    #    return StatusResponse(false, "Error while adding tracking to database")
        
    return StatusResponse(false, "i do not do anything yet cuz i forgor to add to disdoc")
    
@app.get("/product/{product_id}/history")
async def get_product_history(product_id: str) -> ProductHistoryResponse | ErrorResponse:
    history = database.get_price_history(product_id)
    
    if history == None:
        return ErrorResponse("Could not get price history from database")
    
    return ProductHistoryResponse(history)
    

def start_server(
    database_obj: Database,
    tgwrapper_obj: TelegramWrapper,
    scraper_obj: OzonScraper):
    
    database = database_obj
    tgwrapper = tgwrapper_obj
    scraper = scraper_obj

    uvicorn.run(
        "api:app",
        host=api_url,
        port=api_port,
        log_level="debug",
    )

if __name__ == "__main__":
    database = Database()
    tgwrapper = TelegramWrapper()
    scraper = OzonScraper(database)

    start_server(database, tgwrapper, scraper)
