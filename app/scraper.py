from database import Database

class OzonScraper:

    database: Database

    def __init__(self, database: Database):
        self.database = database