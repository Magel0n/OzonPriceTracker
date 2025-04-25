import os

class Database:

    db_name: str
    
    def __init__(self):
        self.db_name = os.environ.get("DB_NAME", "database.db")