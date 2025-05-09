from api_models import UserModel, TrackedProductModel, TrackingModel
from database import Database
from unittest import TestCase, mock


class TestDatabase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env_patcher = mock.patch.dict('os.environ', {'db_url': ':memory:'})
        cls.env_patcher.start()
        cls.db = Database()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.env_patcher.stop()

    def setUp(self):
        self.db.reset()

    # Helper methods
    def _create_test_user(self, tid=2137193153):
        user = UserModel(
            tid=tid,
            name="Timur",
            username="tjann",
            user_pfp="pfp_template")
        self.db.login_user(user)
        return user

    def _create_test_product(self, sku="sku_FF", price="100"):
        product = TrackedProductModel(
            id=None,
            url="http://ozon.ru",
            sku=sku,
            name="SuperProductName",
            price=price,
            seller="OzonStore",
            tracking_price=None)
        product_id = self.db.add_product(product)
        product.id = product_id
        return product

    # Test cases begin
    def test_login_user_insert(self):
        user = UserModel(tid=1,
                         name="New",
                         username="new",
                         user_pfp="g4q34terwagt4*(&UE(*GY#&G))")
        result = self.db.login_user(user)
        
        self.assertTrue(result)
        self.assertTrue(self.db.get_user(1).__eq__(user))

    def test_login_user_update(self):
        user = UserModel(tid=1,
                         name="Old",
                         username="old",
                         user_pfp="*&GH*)&HRTVfb9duhu9fbn")
        self.db.login_user(user)

        updated = UserModel(tid=1,
                            name="New",
                            username="new",
                            user_pfp="(&*RGY9dfubh9dfubh9UFHbH(*))")
        result = self.db.login_user(updated)

        self.assertTrue(result)
        self.assertTrue(self.db.get_user(1).__eq__(updated))

    def test_get_user_not_found(self):
        self.assertIsNone(self.db.get_user(77777))

    def test_add_product_new(self):
        product = self._create_test_product()
        products = self.db.get_products()
        self.assertTrue(len(products) == 1)
        self.assertTrue(products[0].__eq__(product))

    def test_add_product_existing(self):
        product1 = self._create_test_product("skuff")
        product2 = TrackedProductModel(
            id=None,
            url="new_url",
            sku="skuff",
            name="New Name",
            price="200",
            seller="New Seller",
            tracking_price=None)
        product2_id = self.db.add_product(product2)
        self.assertTrue(product1.id == product2_id)

        products = self.db.get_products()
        self.assertTrue(len(products) == 1)
        self.assertTrue(products[0].name, "New Name")

    def test_update_products(self):
        product = self._create_test_product()
        updated = TrackedProductModel(
            id=product.id,
            url="updated",
            sku="updated",
            name="updated",
            price="200",
            seller="updated",
            tracking_price=None)
        result = self.db.update_products([updated])
        self.assertTrue(result)

        products = self.db.get_products()
        self.assertTrue(products[0].name == "updated")

    def test_update_nonexistent_product(self):
        product = TrackedProductModel(
            id=99999,
            url="test",
            sku="test",
            name="test",
            price="100",
            seller="test",
            tracking_price=None)
        result = self.db.update_products([product])
        self.assertTrue(result)

    def test_add_new_tracking(self):
        user = self._create_test_user()
        product = self._create_test_product()

        tracking = TrackingModel(
            user_tid=user.tid,
            product_id=product.id,
            new_price="31337"
        )
        result = self.db.add_tracking(tracking)
        self.assertTrue(result)

        tracked = self.db.get_tracked_products(user.tid)
        self.assertTrue(len(tracked) == 1)

    def test_update_tracking(self):
        user = self._create_test_user()
        product = self._create_test_product()

        tracking1 = TrackingModel(
            user_tid=user.tid,
            product_id=product.id,
            new_price="80"
        )
        self.db.add_tracking(tracking1)

        tracking2 = TrackingModel(
            user_tid=user.tid,
            product_id=product.id,
            new_price="90"
        )
        result = self.db.add_tracking(tracking2)
        self.assertTrue(result)

        tracked = self.db.get_tracked_products(user.tid)
        self.assertTrue(tracked[0].tracking_price == "90")

    def test_get_tracked_products_empty(self):
        user = self._create_test_user()
        tracked = self.db.get_tracked_products(user.tid)

        self.assertTrue(len(tracked) == 0)

    def test_delete_tracking(self):
        user = self._create_test_user()
        product = self._create_test_product()

        tracking = TrackingModel(
            user_tid=user.tid,
            product_id=product.id,
            new_price="80"
        )
        self.db.add_tracking(tracking)
        result = self.db.delete_tracking(tracking)

        self.assertTrue(result)
        self.assertTrue(len(self.db.get_tracked_products(user.tid)) == 0)

    def test_delete_nonexistent_tracking(self):
        tracking = TrackingModel(
            user_tid=999,
            product_id=999,
            new_price="80"
        )
        result = self.db.delete_tracking(tracking)
        self.assertFalse(result)

    def test_price_history(self):
        product = self._create_test_product()

        self.db.add_to_price_history([product.id], 1000)
        updated = TrackedProductModel(
            id=product.id,
            url=product.url,
            sku=product.sku,
            name=product.name,
            price="250",
            seller=product.seller,
            tracking_price=None)
        self.db.update_products([updated])
        self.db.add_to_price_history([product.id], 2000)

        history = self.db.get_price_history(product.id)

        self.assertTrue(len(history) == 2)
        self.assertTrue(history[0][0] == "100")
        self.assertTrue(history[1][0] == "250")

    def test_price_history_invalid_product(self):
        result = self.db.add_to_price_history([999], 1000)
        self.assertFalse(result)

    def test_get_users_by_products(self):
        user1 = self._create_test_user(1)
        user2 = self._create_test_user(2)
        product1 = self._create_test_product("sku1")
        product2 = self._create_test_product("sku2")

        self.db.add_tracking(TrackingModel(
            user_tid=user1.tid,
            product_id=product1.id,
            new_price="150"
        ))
        self.db.add_tracking(TrackingModel(
            user_tid=user1.tid,
            product_id=product2.id,
            new_price="200"
        ))
        self.db.add_tracking(TrackingModel(
            user_tid=user2.tid,
            product_id=product1.id,
            new_price="150"
        ))

        result = self.db.get_users_by_products([product1.id, product2.id])

        self.assertTrue(len(result[user1.tid]) == 2)
        self.assertTrue(len(result[user2.tid]) == 1)
