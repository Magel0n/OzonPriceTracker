from database import Database
from api_models import *


class TestDatabase:
    def test_add_product_id_autoincrement(self):
        # This test ensures ids when assigned get incremented next time automatically
        # HOWEVER !!!
        # Sometimes ids do not start from 1 (tables do not get deleted)
        db = Database()
        db.reset()
        product1 = TrackedProductModel(id=None,
                                       url="https://ozon.ru",
                                       sku="sku_1",
                                       name="product name",
                                       price="999",
                                       seller="ozonstore",
                                       tracking_price="899")
        product2 = TrackedProductModel(id="",
                                       url="https://ozon.ru",
                                       sku="sku_2",
                                       name="product name",
                                       price="999",
                                       seller="ozonstore",
                                       tracking_price="899")
        product3 = TrackedProductModel(id="45",
                                       url="https://ozon.ru",
                                       sku="sku_3",
                                       name="product name",
                                       price="999",
                                       seller="ozonstore",
                                       tracking_price="899")
        id_1 = db.add_product(product1)
        id_2 = db.add_product(product2)
        id_3 = db.add_product(product3)
        assert id_1 is not None and id_1 >= 1
        assert id_2 is not None and id_2 >= 1 and id_2 != id_1
        assert id_3 is not None and id_3 >= 1 and id_3 != id_2
    
    def test_update_product(self):
        db = Database()
        db.reset()
        products = [
            TrackedProductModel(id="1",
                                url="https://ozon.ru",
                                sku="sku_1",
                                name="product name",
                                price="999",
                                seller="ozonstore",
                                tracking_price="899"),
            TrackedProductModel(id="2",
                                url="https://ozon.ru",
                                sku="sku_2",
                                name="product name",
                                price="999",
                                seller="ozonstore",
                                tracking_price="899"),
            TrackedProductModel(id="3",
                                url="https://ozon.ru",
                                sku="sku_3",
                                name="product name",
                                price="999",
                                seller="ozonstore",
                                tracking_price="899")
        ]
        prod_1 = db.add_product(products[0])
        prod_2 = db.add_product(products[1])
        prod_3 = db.add_product(products[2])
        
        test_user = UserModel(tid=288, name="Timur", username="tjann", user_pfp="asfgvsvbwef1234")
        db.login_user(test_user)
        
        
        db.add_tracking(TrackingModel(user_tid=str(test_user.tid), product_id=str(prod_1), new_price=None))
        db.add_tracking(TrackingModel(user_tid=str(test_user.tid), product_id=str(prod_2), new_price=None))
        db.add_tracking(TrackingModel(user_tid=str(test_user.tid), product_id=str(prod_3), new_price=None))
        
        for product in products:
            product.name = "changed product name"
        db.update_products(products)
        results = db.get_tracked_products(test_user.tid)
        assert len(results) == 3 and \
            results[0].name == products[0].name and \
            results[1].name == products[1].name and \
            results[2].name == products[2].name

        db.delete_tracking(TrackingModel(user_tid=str(test_user.tid), product_id=str(prod_3), new_price=None))
        
        results = db.get_tracked_products(test_user.tid)
        assert len(results) == 2 and \
            results[0].name == products[0].name and \
            results[1].name == products[1].name
        
        
    def test_whatever(self):
        db = Database()
        db.reset()
        user = UserModel(tid=288, name="Timur", username="tjann", user_pfp="asfgvsvbwef1234")
        product = TrackedProductModel(id=None,
                                      url="https://ozon.ru", 
                                      sku="what_is_sku", 
                                      name="product name",
                                      price="999",
                                      seller="ozonstore", 
                                      tracking_price="899")
        db.login_user(user)
        prod_id = db.add_product(product)
        track = TrackingModel(user_tid=str(user.tid), product_id=str(prod_id), new_price=product.price)
        db.add_tracking(track)
        new_product = db.get_tracked_products(user.tid)[0]
        assert product.url == new_product.url and \
            product.sku == new_product.sku and \
            product.name == new_product.name
                