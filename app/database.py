import os
import sqlite3
from pydantic import BaseModel


class UserModel(BaseModel):
    tid: int
    name: str
    username: str
    user_pfp: str | None = None


class TrackedProductModel(BaseModel):
    id: str | None = None
    url: str
    sku: str
    name: str
    price: str
    seller: str
    tracking_price: str | None = None
    

class TrackingModel(BaseModel):
    user_tid: str
    product_id: str
    new_price: str | None


class Database:
    conn: sqlite3.Connection
    db_url: str
    # TODO: I guess these aren't needed for now
    # db_user: str 
    # db_pass: str
    
    def __init__(self):
        self.db_url = os.environ.get("db_url", "database.db")
        self.conn = sqlite3.connect(self.db_url)
        self._init_db()
    
    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT NOT NULL,
            user_pfp BLOB
        );""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            sku TEXT NOT NULL,
            name TEXT NOT NULL,
            price TEXT NOT NULL,
            seller TEXT NOT NULL,
            tracking_price TEXT
        );""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracking (
            telegram_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            new_price TEXT,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            PRIMARY KEY (telegram_id, product_id)
        );""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            product_id INTEGER,
            price TEXT NOT NULL,
            time TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );""") # TODO: TIMESTAMP for time maybe. Don't know which is more complicated operation
        self.conn.commit()
    
    # Update user if already present
    def login_user(self, user: UserModel) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE users
        SET name = ?, username = ?, user_pfp = ?
        WHERE telegram_id = ?
        RETURNING *;
        """, (user.name, user.username, user.user_pfp, user.tid))

        self.conn.commit()
        return True
        
        
    # All products passed should have id so they can overwrite existing stuff
    def update_products(self, products: list[TrackedProductModel]) -> bool:
        cursor = self.conn.cursor()
        def lmb(p: TrackedProductModel):
            cursor.execute("""
            UPDATE products
            SET url = ?, sku = ?, name = ?, price = ?,
            seller = ?, tracking_price = ?
            WHERE product_id = ?
            RETURNING *;
            """, (p.url, p.sku, p.name, p.price,
                  p.seller, p.tracking_price, p.id))
            return len(cursor.fetchall())
        [lmb(prod) for prod in products]

        self.conn.commit()
        return True
    
    # Should not have id or tracking_price, should have everything else, returns the id of the product
    # do not create new if the product with same sku is present
    def add_product(self, product: TrackedProductModel) -> str:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT product_id FROM products
        WHERE sku = ?;
        """, (product.sku))
        if cursor.fetchall():
            cursor.execute("""
            INSERT INTO products
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING product_id;
            """, (product.id, product.url, product.sku,
                  product.name, product.price, product.seller,
                  product.tracking_price))
            ret = cursor.fetchone()[0]
            self.conn.commit()
        
        return ret
    
    # Should add or update entry into tracking
    def add_tracking(self, tracking_info: TrackingModel) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE tracking
        SET new_price = ?
        WHERE telegram_id = ?, product_id = ?
        RETURNING *;
        """, (tracking_info.new_price,
              tracking_info.user_tid,
              tracking_info.product_id))
        
        if cursor.fetchone():
            cursor.execute("""
            INSERT INTO tracking
            VALUES(? ? ?);
            """, (tracking_info.new_price,
                  tracking_info.user_tid,
                  tracking_info.product_id))
        self.conn.commit()
        return True
    
    # Should return list of products that a specific user has tracked
    def get_tracked_products(self, user_tid: str) -> list[TrackedProductModel] | None:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT * FROM products
        WHERE product_id = ?;
        """, (user_tid,))

        ret = [TrackedProductModel(val) for val in cursor.fetchall()]
        return ret
    
    # Should return dictionary of users that track the products listed
    def get_users_by_products(self, product_ids: list[TrackedProductModel]) -> dict[str, list[TrackedProductModel]] | None:
        cursor = self.conn.cursor()
        ret = dict()
        def lmb(p: TrackedProductModel):
            cursor.execute("""
            SELECT telegram_id FROM tracking
            WHERE product_id = ?;
            """, (p,))
            for user in cursor.fetchall():
                ret[user] = ret[user] + p
        [lmb(prod) for prod in product_ids]
        
    # Add updated price information to history table, you may not check if the price has changed 
    def add_to_price_history(self, product_ids: list[str], time: int) -> bool:
        cursor = self.conn.cursor()
        def lmb(p):
            cursor.execute("""
            SELECT price FROM products
            WHERE product_id = ?;
            """, (p,))
            price = cursor.fetchone()[0]
            cursor.execute("""
            INSERT INTO history
            VALUES (?, ?, ?);
            """, (p, price, time))
        [lmb(prod) for prod in product_ids]

        self.conn.commit()
        return True
        
    # Get price history of product by its id, sort by timestamp
    def get_price_history(self, product_id: str) -> list[tuple[int, str]] | None:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT price, time FROM history
        WHERE product_id = ?;
        """, (product_id,))
        ret = [(result[0], result[1]) for result in cursor.fetchall()]
        return sorted(ret, key=lambda x: x[1])
    
    def close(self):
        if self.conn:
            self.conn.close()
