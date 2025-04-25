import os
import uvicorn
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

@app.get("/")
async def index():
    return "Hello world!"

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
