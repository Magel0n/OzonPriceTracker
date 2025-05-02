from app.database import Database, UserModel, TrackedProductModel, TrackingModel

class TestDatabase:
    def test_add_product(self):
        # This test ensures correct id assignment to new variables,
        db = Database()
        product1 = TrackedProductModel(url="https://ozon.ru",
                                      sku="what_is_sku",
                                      name="product name",
                                      price="999",
                                      seller="ozonstore",
                                      tracking_price="899")
        product2 = TrackedProductModel(url="https://ozon.ru",
                                      sku="what_is_sku",
                                      name="product name",
                                      price="999",
                                      seller="ozonstore",
                                      tracking_price="899")
        product3 = TrackedProductModel(id=45,
                                       url="https://ozon.ru",
                                       sku="what_is_sku",
                                       name="product name",
                                       price="999",
                                       seller="ozonstore",
                                       tracking_price="899")
        assert db.add_product(product1) == 1
        assert db.add_product(product2) == 2
        assert db.add_product(product3) == 45

    def test_whatever(self):
        db = Database()
        user = UserModel(tid=288, name="Timur", username="tjann", user_pfp="asfgvsvbwef1234")
        product = TrackedProductModel(url="https://ozon.ru", sku="what_is_sku", name="product name", price="999", seller="ozonstore", tracking_price="899")
        db.login_user(user)
        db.add_product(product)
        db.add_tracking()

