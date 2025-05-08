import os
import sqlite3
from api_models import UserModel, TrackedProductModel, TrackingModel


class Database:
    conn: sqlite3.Connection
    db_url: str

    def __init__(self):
        self.db_url = os.environ.get("db_url", "database.db")
        self.conn = sqlite3.connect(self.db_url, timeout=20)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT NOT NULL,
            user_pfp TEXT
        );""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            sku TEXT NOT NULL,
            name TEXT NOT NULL,
            price TEXT NOT NULL,
            seller TEXT NOT NULL
        );""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracking (
            telegram_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            tracking_price TEXT,
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
        );""")
        self.conn.commit()
        cursor.close()

    # Update user if already present
    def login_user(self, user: UserModel) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE users
        SET name = ?, username = ?, user_pfp = ?
        WHERE telegram_id = ?
        RETURNING *;
        """, (user.name, user.username, user.user_pfp, user.tid))
        if not cursor.fetchall():
            cursor.execute("""
            INSERT INTO users
            VALUES (?, ?, ?, ?)
            """, (user.tid, user.name, user.username, user.user_pfp))

        self.conn.commit()
        cursor.close()
        return True

    # All products passed should have id so they can overwrite existing stuff.
    # If Successful - True, Error - False
    def update_products(self, products: list[TrackedProductModel]) -> bool:
        cursor = self.conn.cursor()

        def lmb(p: TrackedProductModel):
            cursor.execute("""
            UPDATE products
            SET url = ?, sku = ?, name = ?,
            price = ?, seller = ?
            WHERE product_id = ?
            RETURNING *;
            """, (p.url, p.sku, p.name,
                  p.price, p.seller, p.id))
            return len(cursor.fetchall())
        [lmb(prod) for prod in products]
        self.conn.commit()
        cursor.close()
        return True

    # Should not have id or delete_price, should have everything else,
    # returns the id of the product
    # update if the product with same sku is present
    def add_product(self, product: TrackedProductModel) -> str:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT product_id FROM products
        WHERE sku = ?;
        """, (product.sku,))
        ret = cursor.fetchall()
        if not ret:
            cursor.execute("""
            INSERT INTO products
            (url, sku, name, price, seller)
            VALUES (?, ?, ?, ?, ?)
            RETURNING product_id;
            """, (product.url, product.sku, product.name,
                  product.price, product.seller))
        else:
            cursor.execute("""
            UPDATE products
            SET url = ?, name = ?, price = ?, seller = ?
            WHERE sku = ?
            RETURNING product_id;
            """, (product.url, product.name, product.price,
                  product.seller, product.sku))

        ret = cursor.fetchall()[0][0]
        self.conn.commit()
        cursor.close()
        return ret

    # Should add or update entry into tracking.
    # If Successful - True, Error - False
    def add_tracking(self, tracking_info: TrackingModel) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE tracking
        SET tracking_price = ?
        WHERE telegram_id = ? AND product_id = ?
        RETURNING *;
        """, (tracking_info.new_price,
              tracking_info.user_tid,
              tracking_info.product_id))

        if not cursor.fetchall():
            cursor.execute("""
            INSERT INTO tracking
            VALUES (?, ?, ?);
            """, (tracking_info.user_tid,
                  tracking_info.product_id,
                  tracking_info.new_price))
            cursor.fetchall()

        self.conn.commit()
        cursor.close()
        return True

    def get_user(self, tid: int) -> UserModel | None:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT * FROM users
        WHERE telegram_id = ?;
        """, (tid,))
        result = cursor.fetchall()

        def lmb(x):
            return UserModel(tid=x[0],
                             name=x[1],
                             username=x[2],
                             user_pfp=x[3])
        cursor.close()
        if not result:
            return None
        else:
            return lmb(result[0])

    # Should return list of products that a specific user has tracked
    def get_tracked_products(self, user_tid: int) \
            -> list[TrackedProductModel] | None:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT p.product_id, p.url, p.sku, p.name,
        p.price, p.seller, t.tracking_price
        FROM products p
        JOIN tracking t ON p.product_id = t.product_id
        WHERE t.telegram_id = ?;
        """, (user_tid,))
        results = cursor.fetchall()

        def lmb(x):
            return TrackedProductModel(id=x[0],
                                       url=x[1],
                                       sku=x[2],
                                       name=x[3],
                                       price=x[4],
                                       seller=x[5],
                                       tracking_price=x[6])
        ret = [lmb(val[0]) for val in results]
        cursor.close()
        return ret

    # Should return dictionary of users that track the products listed
    def get_users_by_products(self, product_ids: list[TrackedProductModel]) \
            -> dict[int, list[TrackedProductModel]] | None:
        cursor = self.conn.cursor()
        ret = dict()

        def lmb(p: TrackedProductModel):
            cursor.execute("""
            SELECT telegram_id FROM tracking
            WHERE product_id = ?;
            """, (p.id,))
            for user in cursor.fetchall():
                if user[0] not in ret:
                    ret[user[0]] = list()
                ret[user[0]].append(p)
        [lmb(prod) for prod in product_ids]
        cursor.close()
        return ret

    # gets ALL products
    def get_products(self) -> list[TrackedProductModel]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT * FROM products;
        """)
        results = cursor.fetchall()

        def lmb(x) -> TrackedProductModel:
            return TrackedProductModel(id=x[0],
                                       url=x[1],
                                       sku=x[2],
                                       name=x[3],
                                       price=x[4],
                                       seller=x[5],
                                       tracking_price=None)
        results = [lmb(result) for result in results]
        cursor.close()
        return results

    # Adds updated price information to history table
    # If Successful - True, Error - False
    def add_to_price_history(self, product_ids: list[int], time: int) -> bool:
        cursor = self.conn.cursor()

        def lmb(p):
            cursor.execute("""
            SELECT price FROM products
            WHERE product_id = ?;
            """, (p,))
            price = cursor.fetchall()

            if not price:
                return 1

            price = price[0][0]
            cursor.execute("""
            INSERT INTO history
            VALUES (?, ?, ?);
            """, (p, price, time))

            cursor.fetchall()
            return 0
        res = sum([lmb(prod) for prod in product_ids])

        self.conn.commit()
        cursor.close()
        if res > 0:
            return False
        return True

    # Get price history of product by its id, sorted by timestamp
    def get_price_history(self, product_id: int) \
            -> list[tuple[int, str]] | None:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT price, time FROM history
        WHERE product_id = ?;
        """, (product_id,))
        ret = [(result[0], result[1]) for result in cursor.fetchall()]
        cursor.close()
        return sorted(ret, key=lambda x: x[1])

    # Deleted given tracking
    # If not deleted anything - False, otherwise - True
    def delete_tracking(self, tracking_info: TrackingModel) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("""
        DELETE FROM tracking
        WHERE telegram_id = ? AND product_id = ?
        RETURNING *;
        """, (tracking_info.user_tid, tracking_info.product_id))
        ret = len(cursor.fetchall()) > 0

        self.conn.commit()
        cursor.close()
        return ret

    # Reset all the tables(required in development mostly)
    def reset(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        DROP TABLE IF EXISTS users;
        """)
        cursor.execute("""
        DROP TABLE IF EXISTS products;
        """)
        cursor.execute("""
        DROP TABLE IF EXISTS tracking;
        """)
        cursor.execute("""
        DROP TABLE IF EXISTS history;
        """)
        cursor.fetchall()
        self.conn.commit()
        cursor.close()
        self._init_db()

    # Closing Connection
    def close(self):
        if self.conn:
            self.conn.close()
