from api_models import UserModel, TrackedProductModel, TrackingModel
from database import Database
from unittest import TestCase, mock
import os


class TestDatabase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env_patcher = mock.patch.dict('os.environ', {
                'db_url': 'test.db',
        })
        cls.env_patcher.start()
        # Using in-memory database avoids changes of primary database
        os.environ['db_url'] = "test.db"
        cls.db = Database()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.env_patcher.stop()

    def setUp(self):
        self.db.reset()

    def test_login_user_insert(self):
        user = UserModel(tid=2137193153,
                         name="Timur Suleymanov",
                         username="tjann7",
                         user_pfp="123id$#W%TG")
        result = self.db.login_user(user)

        self.assertTrue(result)

        test_user = self.db.get_user(user.tid)
        self.assertTrue(user.__eq__(test_user))

    def test_login_user_update(self):
        user = UserModel(tid=21113245345,
                         name="name",
                         username="username",
                         user_pfp="2q3rtefvgSD+{LPL+_)GFWE$^E%^T$T^")
        self.db.login_user(user)

        updated_user = UserModel(tid=21113245345,
                                 name="UPDATED name",
                                 username="UPDATED name",
                                 user_pfp="123id$#W%TG")
        result = self.db.login_user(updated_user)

        self.assertTrue(result)

        test_user = self.db.get_user(updated_user.tid)
        self.assertTrue(updated_user.__eq__(test_user))

    def test_update_products(self):
        product = TrackedProductModel(id=None,
                                      url="https://ozon.ru",
                                      sku="sku1",
                                      name="SuperProductName",
                                      price="99999",
                                      seller="OzonShop",
                                      delete_price="50000")
        product_id = self.db.add_product(product)

        self.assertTrue(product_id == 1)

        updated_product = TrackedProductModel(id=product_id,
                                              url="https://updated.ozon.ru",
                                              sku="new_sku1",
                                              name="new_SuperName",
                                              price="80000",
                                              seller="ozonUpdated",
                                              delete_price="45000")
        result = self.db.update_products([updated_product])
        self.assertTrue(result)

        products = self.db.get_products()
        self.assertTrue(updated_product.__eq__(products[0]))

    def test_update_products_no_change(self):
        product = TrackedProductModel(id=999,
                                      url="https://ozon.ru/no_change",
                                      sku="sku_no_change_1",
                                      name="ProductUnchanged",
                                      price="777",
                                      seller="shopUnchanged",
                                      delete_price="555")
        result = self.db.update_products([product])
        self.assertTrue(result)

    def test_add_product_new(self):
        product = TrackedProductModel(id=None,
                                      url="https://ozon.ru",
                                      sku="sku1",
                                      name="ProductName",
                                      price="99999",
                                      seller="OzonShop",
                                      delete_price="50000")
        product_id = self.db.add_product(product)

        self.assertIsNotNone(product_id)

        products = self.db.get_products()
        self.assertTrue(len(products) == 1)

    def test_add_product_existing(self):
        product1 = TrackedProductModel(id=None,
                                       url="url1",
                                       sku="sku1",
                                       name="name1",
                                       price="100",
                                       seller="seller1",
                                       delete_price="90")
        id_1 = self.db.add_product(product1)

        product2 = TrackedProductModel(id=None,
                                       url="url2",
                                       sku="sku1",
                                       name="name2",
                                       price="200",
                                       seller="seller2",
                                       delete_price="180")
        id_2 = self.db.add_product(product2)

        self.assertTrue(id_1 == id_2)

        product2.id = id_2
        products = self.db.get_products()
        self.assertTrue(products[0].__eq__(product2))

    def test_add_tracking_new(self):
        user = UserModel(tid=21113245345,
                         name="name",
                         username="username",
                         user_pfp="2q3rtefvgSD+{LPL+_)GFWE$^E%^T$T^")
        product = TrackedProductModel(id=None,
                                      url="url",
                                      sku="sku",
                                      name="name",
                                      price="100",
                                      seller="seller",
                                      delete_price="50")

        self.db.login_user(user)
        product_id = self.db.add_product(product)

        tracking = TrackingModel(user_tid=user.tid,
                                 product_id=product_id,
                                 tracking_price="80")
        result = self.db.add_tracking(tracking)

        self.assertTrue(result)

        tracked = self.db.get_tracked_products(user.tid)
        self.assertTrue(len(tracked) == 1)

    def test_add_tracking_update(self):
        tracking = TrackingModel(user_tid=111,
                                 product_id=222,
                                 tracking_price="333")
        result = self.db.add_tracking(tracking)

        self.assertTrue(result)

        updated_tracking = TrackingModel(user_tid=111,
                                         product_id=222,
                                         tracking_price="555")
        result = self.db.add_tracking(updated_tracking)

        self.assertTrue(result)

    def test_get_user_not_found(self):
        user = self.db.get_user("999")
        self.assertTrue(user is None)

    def test_get_tracked_products_empty(self):
        products = self.db.get_tracked_products("999")
        self.assertTrue(not products)

    def test_get_users_by_products(self):
        users = [
            UserModel(tid=21113245345,
                      name="tjann7",
                      username="Timur",
                      user_pfp="2q3rtefvgSD+{LPL+_)GFWE$^E%^T$T^"),
            UserModel(tid=999,
                      name="name",
                      username="username",
                      user_pfp="whatever")
        ]
        products = [
            TrackedProductModel(id=None,
                                url="url1",
                                sku="sku1",
                                name="name1",
                                price="300",
                                seller="seller1",
                                delete_price="100"),
            TrackedProductModel(id=None,
                                url="url2",
                                sku="sku2",
                                name="name2",
                                price="600",
                                seller="seller2",
                                delete_price="200")
        ]

        self.db.login_user(users[0])
        self.db.login_user(users[1])

        p1 = self.db.add_product(products[0])
        p2 = self.db.add_product(products[1])

        trackings = [
            TrackingModel(user_tid=21113245345, product_id=p1, tracking_price="40"),
            TrackingModel(user_tid=21113245345, product_id=p2, tracking_price="80"),
            TrackingModel(user_tid=999, product_id=p1, tracking_price="85")
        ]

        self.db.add_tracking(trackings[0])
        self.db.add_tracking(trackings[1])
        self.db.add_tracking(trackings[2])

        products[0].id = p1
        products[1].id = p2
        result = self.db.get_users_by_products(products)

        self.assertTrue(len(result[21113245345]) == 2)
        self.assertTrue(len(result[999]) == 1)

    def test_add_to_price_history(self):
        product = TrackedProductModel(id=None,
                                      url="url",
                                      sku="sku",
                                      name="name",
                                      price="100",
                                      seller="seller",
                                      delete_price="50")
        product_id = self.db.add_product(product)

        result = self.db.add_to_price_history([product_id], 20251231)
        self.assertTrue(result)

        history = self.db.get_price_history(product_id)
        self.assertTrue(len(history) == 1)

    def test_add_to_price_history_invalid_product(self):
        result = self.db.add_to_price_history([999], 20251231)
        self.assertFalse(result)

    def test_delete_tracking(self):
        self.test_add_tracking_new()
        product_id = self.db.get_products()[0].id

        tracking = TrackingModel(user_tid=21113245345,
                                 product_id=product_id,
                                 tracking_price="500")
        result = self.db.delete_tracking(tracking)

        self.assertTrue(result)

        tracked = self.db.get_tracked_products(21113245345)
        self.assertTrue(len(tracked) == 0)

    def test_delete_tracking_not_found(self):
        tracking = TrackingModel(user_tid=999, product_id=999, tracking_price="500")
        result = self.db.delete_tracking(tracking)

        self.assertFalse(result)
