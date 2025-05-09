import unittest
from unittest.mock import patch, MagicMock
from api_models import TrackedProductModel
from database import Database
from scraper import OzonScraper


class TestScrapper(unittest.TestCase):
    def setUp(self):
        self.database = MagicMock()
        self.tgwrapper = MagicMock()
        self.env_patcher = patch.dict('os.environ', {
            'scraper_headlessness': 'True',
            'scraper_update_time': '60',
            'scraper_keepFailure': 'True'
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_initialization(self):
        scraper = OzonScraper(self.tgwrapper)
        self.assertTrue(scraper.headlessness)
        self.assertEqual(scraper.update_time, 60)
        self.assertTrue(scraper.keepFailure)
        del scraper

    def test_url_checker_valid(self):
        scraper = OzonScraper(self.tgwrapper)
        test_cases = [
            ("https://www.ozon.ru/product/123456", "https://www.ozon.ru/product/123456"),
            ("http://www.ozon.ru/product/456", "https://www.ozon.ru/product/456"),
            ("www.ozon.ru/product/789", "https://www.ozon.ru/product/789"),
        ]

        for input_url, expected in test_cases:
            with self.subTest(input_url=input_url):
                self.assertEqual(scraper._check_url(input_url), expected)

    def test_url_checker_invalid(self):
        scraper = OzonScraper(self.tgwrapper)
        test_cases = [
            None,
            "",
            "https://www.amazon.com/product/123",
            "https:/www.ozon.ru/category/123",
            "https://www.ozon.ru/category/123",
            "www.ozon.ru",
            "ozon.ru/product/123",
            "https://www.ozon.ru/product/",
        ]

        for input_url in test_cases:
            with self.subTest(input_url=input_url):
                self.assertIsNone(scraper._check_url(input_url))

    def test_sku_checker_valid(self):
        scraper = OzonScraper(self.tgwrapper)
        test_cases = [
            ("https://www.ozon.ru/product/123456", "123456"),
            ("http://www.ozon.ru/product/456", "456"),
            ("www.ozon.ru/product/789", "789"),
        ]

        for input_url, expected in test_cases:
            with self.subTest(input_url=input_url):
                self.assertEqual(scraper._create_sku_from_url(input_url), expected)

    def test_sku_checker_invalid(self):
        scraper = OzonScraper(self.tgwrapper)
        test_cases = [
            None,
            "",
            "https://www.amazon.com/product/123",
            "https:/www.ozon.ru/category/123",
            "https://www.ozon.ru/category/123",
            "www.ozon.ru",
            "ozon.ru/product/123",
            "https://www.ozon.ru/product/",
            "https://www.ozon.ru/product/-",
            "https://www.ozon.ru/product/wrong",
        ]

        for input_url in test_cases:
            with self.subTest(input_url=input_url):
                self.assertEqual(scraper._create_sku_from_url(input_url), "")

    @patch('seleniumbase.SB')
    def test_get_info_for_product_valid(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value
        mock_instance.find_elements.side_effect = [
            [MagicMock(text="Test Product")],
            [MagicMock(text="Test Seller")],
            [MagicMock(text="1\u2009999₽")],
        ]

        name, price, seller = scraper._get_info_for_product("HereThisIsWrongButItsMockedSoNoWorries")
        self.assertEqual(name, "Test Product")
        self.assertEqual(price, 1999)
        self.assertEqual(seller, "Test Seller")

    @patch('seleniumbase.SB')
    def test_get_info_for_product_invalid(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value
        mock_instance.find_elements.side_effect = []

        name, price, seller = scraper._get_info_for_product("HereThisIsWrongButItsMockedSoNoWorries")
        self.assertIsNone(name)
        self.assertIsNone(price)
        self.assertIsNone(seller)

    def test_scrape_product_with_url(self):
        scraper = OzonScraper(self.tgwrapper)
        with patch.object(scraper, '_get_info_for_product', return_value=("Test", 1000, "Seller")):
            result = scraper.scrape_product(url="https://www.ozon.ru/product/my-product-123")
            self.assertIsInstance(result, TrackedProductModel)
            self.assertEqual(result.name, "Test")
            self.assertEqual(result.price, "1000")
            self.assertEqual(result.seller, "Seller")
            self.assertEqual(result.url, "https://www.ozon.ru/product/my-product-123")
            self.assertEqual(result.sku, "123")

    def test_scrape_product_with_sku(self):
        scraper = OzonScraper(self.tgwrapper)
        with patch.object(scraper, '_get_info_for_product', return_value=("Test", 1000, "Seller")):
            result = scraper.scrape_product(sku="123")
            self.assertIsInstance(result, TrackedProductModel)
            self.assertEqual(result.name, "Test")
            self.assertEqual(result.price, "1000")
            self.assertEqual(result.seller, "Seller")
            self.assertEqual(result.url, "https://www.ozon.ru/product/123")
            self.assertEqual(result.sku, "123")

    def test_scrape_product_complete_failure(self):
        scraper = OzonScraper(self.tgwrapper)
        with patch.object(scraper, '_get_info_for_product', return_value=(None, None, None)) as mocked:
            result = scraper.scrape_product(url="https://www.ozon.ru/product/my-product-123")
            self.assertIsNone(result)
            self.assertEqual(mocked.call_count, scraper.retries_count + 1)

    def test_scrape_product_failure_name(self):
        scraper = OzonScraper(self.tgwrapper)
        with patch.object(scraper, '_get_info_for_product', return_value=(None, 1000, "Seller")) as mocked:
            result = scraper.scrape_product(sku="123")
            self.assertIsInstance(result, TrackedProductModel)
            self.assertEqual(result.name, "")
            self.assertEqual(result.price, "1000")
            self.assertEqual(result.seller, "Seller")
            self.assertEqual(result.url, "https://www.ozon.ru/product/123")
            self.assertEqual(result.sku, "123")
            self.assertEqual(mocked.call_count, scraper.retries_count + 1)

    def test_scrape_product_failure_seller(self):
        scraper = OzonScraper(self.tgwrapper)
        with patch.object(scraper, '_get_info_for_product', return_value=("Test", 1000, None)) as mocked:
            result = scraper.scrape_product(sku="123")
            self.assertIsInstance(result, TrackedProductModel)
            self.assertEqual(result.name, "Test")
            self.assertEqual(result.price, "1000")
            self.assertEqual(result.seller, "")
            self.assertEqual(result.url, "https://www.ozon.ru/product/123")
            self.assertEqual(result.sku, "123")
            self.assertEqual(mocked.call_count, scraper.retries_count + 1)

    def test_scrape_product_failure_price(self):
        scraper = OzonScraper(self.tgwrapper)
        with patch.object(scraper, '_get_info_for_product', return_value=("Test", None, "Seller")) as mocked:
            result = scraper.scrape_product(sku="123")
            self.assertIsNone(result)
            self.assertEqual(mocked.call_count, scraper.retries_count + 1)

    @patch('seleniumbase.SB')
    def test_selenium_get_price_for_product_success(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value

        mock_price_element = MagicMock()
        mock_price_element.text = "1\u2009999₽"
        mock_instance.find_elements.side_effect = [
            [mock_price_element],
        ]

        result = scraper._selenium_get_price_for_product(mock_instance)

        self.assertEqual(result, 1999)
        mock_instance.find_elements.assert_called_once()
        mock_instance.sleep.assert_not_called()

    @patch('seleniumbase.SB')
    def test_selenium_get_price_for_product_retry(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value

        mock_price_element = MagicMock()
        mock_price_element.text = "1\u2009999₽"
        mock_instance.find_elements.side_effect = [
            [],  # First selector fails (first attempt)
            [],  # Second selector fails (first attempt)
            [],  # Third selector fails (first attempt)
            [],  # First selector fails again (second attempt)
            [mock_price_element],  # Success on third selector (second attempt)
        ]

        result = scraper._selenium_get_price_for_product(mock_instance)

        self.assertEqual(result, 1999)
        assert mock_instance.find_elements.call_count == 5
        mock_instance.save_page_source.assert_called_once_with("failurePrice")

    @patch('seleniumbase.SB')
    def test_selenium_get_price_for_product_failure(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        scraper.keepFailure = False
        mock_instance = mock_sb.return_value.__enter__.return_value

        mock_price_element = MagicMock()
        mock_price_element.text = "1\u2009999₽"
        mock_instance.find_elements.return_value = []

        result = scraper._selenium_get_price_for_product(mock_instance)

        self.assertIsNone(result)
        assert mock_instance.find_elements.call_count == scraper.retries_count * 3
        mock_instance.save_page_source.assert_not_called()

    @patch('seleniumbase.SB')
    def test_selenium_get_name_for_product_success(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value

        mock_price_element = MagicMock()
        mock_price_element.text = "Name"
        mock_instance.find_elements.side_effect = [
            [mock_price_element],
        ]

        result = scraper._selenium_get_name_for_product(mock_instance)

        self.assertEqual(result, "Name")
        mock_instance.find_elements.assert_called_once()
        mock_instance.sleep.assert_not_called()

    @patch('seleniumbase.SB')
    def test_selenium_get_name_for_product_retry(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value

        mock_price_element = MagicMock()
        mock_price_element.text = "Name"
        mock_instance.find_elements.side_effect = [
            [],  # First selector fails (first attempt)
            [],  # Second selector fails (first attempt)
            [],  # Third selector fails (first attempt)
            [],  # First selector fails again (second attempt)
            [mock_price_element],  # Success on third selector (second attempt)
        ]

        result = scraper._selenium_get_name_for_product(mock_instance)

        self.assertEqual(result, "Name")
        assert mock_instance.find_elements.call_count == 5
        mock_instance.save_page_source.assert_called_once_with("failureName")

    @patch('seleniumbase.SB')
    def test_selenium_get_name_for_product_failure(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        scraper.keepFailure = False
        mock_instance = mock_sb.return_value.__enter__.return_value
        mock_instance.find_elements.return_value = []

        result = scraper._selenium_get_name_for_product(mock_instance)

        self.assertIsNone(result)
        assert mock_instance.find_elements.call_count == scraper.retries_count * 3
        mock_instance.save_page_source.assert_not_called()

    @patch('seleniumbase.SB')
    def test_selenium_get_seller_for_product_success(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value

        mock_price_element = MagicMock()
        mock_price_element.text = "Seller"
        mock_instance.find_elements.side_effect = [
            [mock_price_element],
        ]

        result = scraper._selenium_get_seller_for_product(mock_instance)

        self.assertEqual(result, "Seller")
        mock_instance.find_elements.assert_called_once()
        mock_instance.sleep.assert_not_called()

    @patch('seleniumbase.SB')
    def test_selenium_get_seller_for_product_retry(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value

        mock_price_element = MagicMock()
        mock_price_element.text = "Seller"
        mock_instance.find_elements.side_effect = [
            [],  # First selector fails (first attempt)
            [],  # Second selector fails (first attempt)
            [],  # Third selector fails (first attempt)
            [],  # First selector fails again (second attempt)
            [mock_price_element],  # Success on third selector (second attempt)
        ]

        result = scraper._selenium_get_seller_for_product(mock_instance)

        self.assertEqual(result, "Seller")
        assert mock_instance.find_elements.call_count == 5
        mock_instance.save_page_source.assert_called_once_with("failureSeller")

    @patch('seleniumbase.SB')
    def test_selenium_get_seller_for_product_failure(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        scraper.keepFailure = False
        mock_instance = mock_sb.return_value.__enter__.return_value
        mock_instance.find_elements.return_value = []

        result = scraper._selenium_get_seller_for_product(mock_instance)

        self.assertIsNone(result)
        assert mock_instance.find_elements.call_count == scraper.retries_count * 4
        mock_instance.save_page_source.assert_not_called()

    @patch('seleniumbase.SB', side_effect=AssertionError("SeleniumBase should not be called with invalid inputs"))
    def test_scrape_product_with_failures(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        self.assertIsNone(scraper.scrape_product(url="test", sku="123"))
        self.assertIsNone(scraper.scrape_product())
        with patch.object(scraper, '_check_url', return_value=None):
            self.assertIsNone(scraper.scrape_product(url="invalid"))

    @patch('seleniumbase.SB')
    def test_get_price_for_products_general(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value
        mock_instance.find_elements.side_effect = [
            [MagicMock(text="1\u2009999₽")],  # Some value for first
            [MagicMock(text="2\u2009499₽")],  # Some value for second
            [],  # Failure    for third
        ]

        urls = ["https://www.ozon.ru/product/123"] * 3
        prices = scraper._get_price_for_products(urls)
        self.assertEqual([1999, 2499, None], prices)

    @patch('seleniumbase.SB')
    def test_get_price_for_products_complete(self, mock_sb):
        scraper = OzonScraper(self.tgwrapper)
        mock_instance = mock_sb.return_value.__enter__.return_value
        mock_instance.find_elements.side_effect = [
            [MagicMock(text="1\u2009999₽")],  # Some value for first
            [MagicMock(text="2\u2009499₽")],  # Some value for second
            [MagicMock(text="3\u2009499₽")],  # Some value for third
        ]

        urls = ["https://www.ozon.ru/product/123"] * 3
        prices = scraper._get_price_for_products(urls)
        self.assertEqual([1999, 2499, 3499], prices)

    def test_update_offers_job_failure_to_parse(self):
        mock_db = MagicMock(spec=Database)
        product = MagicMock(spec=TrackedProductModel, price="1000", id=1,
                            url="https://www.ozon.ru/product/123", sku="123")
        mock_db.get_products.return_value = [product]
        with patch('scraper.Database', return_value=mock_db):
            with patch.object(mock_db, 'get_users_by_products', return_value={}):
                scraper = OzonScraper(self.tgwrapper)
                with patch.object(scraper, '_get_price_for_products', return_value=[None]):
                    result = scraper.update_offers_job()
                    # time.sleep(min(scraper.update_time - 1, 15))
                    self.assertEqual(result, scraper.update_offers_job)
                    scraper.database.get_users_by_products.assert_called_once_with([])
                    scraper.tgwrapper.push_notifications.assert_called_once_with({})

    def test_update_offers_job_failure_to_parse_no_url(self):
        mock_db = MagicMock(spec=Database)
        product = MagicMock(spec=TrackedProductModel, price="1000", id=1, url=None, sku="123")
        mock_db.get_products.return_value = [product]
        with patch('scraper.Database', return_value=mock_db):
            with patch.object(mock_db, 'get_users_by_products', return_value={}):
                scraper = OzonScraper(self.tgwrapper)
                with patch.object(scraper, '_get_price_for_products', return_value=[None]):
                    result = scraper.update_offers_job()
                    # time.sleep(min(scraper.update_time - 1, 15))
                    self.assertEqual(result, scraper.update_offers_job)
                    scraper.database.get_users_by_products.assert_called_once_with([])
                    scraper.tgwrapper.push_notifications.assert_called_once_with({})

    def test_update_offers_job_price_increase(self):
        mock_db = MagicMock(spec=Database)
        product = MagicMock(spec=TrackedProductModel, price="1000", id=1,
                            url="https://www.ozon.ru/product/123", sku="123")
        mock_db.get_products.return_value = [product]
        with patch('scraper.Database', return_value=mock_db):
            with patch.object(mock_db, 'get_users_by_products', return_value={}):
                scraper = OzonScraper(self.tgwrapper)
                with patch.object(scraper, '_get_price_for_products', return_value=[1500]):
                    result = scraper.update_offers_job()
                    # time.sleep(min(scraper.update_time - 1, 15))
                    self.assertEqual(result, scraper.update_offers_job)
                    self.assertEqual(product.price, "1500")
                    scraper.database.get_users_by_products.assert_called_once_with([])
                    scraper.database.add_to_price_history.assert_called_once_with(
                        [1], unittest.mock.ANY  # Timestamp
                    )
                    scraper.tgwrapper.push_notifications.assert_called_once_with({})

    def test_update_offers_job_price_decrease(self):
        mock_db = MagicMock(spec=Database)
        product = MagicMock(spec=TrackedProductModel, price="1500", id=1,
                            url="https://www.ozon.ru/product/123", sku="123")
        product2 = MagicMock(spec=TrackedProductModel, price="1500", id=2,
                             url="https://www.ozon.ru/product/1234", sku="1234")
        mock_db.get_products.return_value = [product, product2]
        with patch('scraper.Database', return_value=mock_db):
            with patch.object(mock_db, 'get_users_by_products', return_value={1: [product, product2]}):
                scraper = OzonScraper(self.tgwrapper)
                with patch.object(scraper, '_get_price_for_products', return_value=[1000, 1000]):
                    result = scraper.update_offers_job()
                    # time.sleep(min(scraper.update_time - 1, 15))
                    self.assertEqual(result, scraper.update_offers_job)
                    self.assertEqual(product.price, "1000")
                    scraper.database.get_users_by_products.assert_called_once_with([product, product2])
                    scraper.database.add_to_price_history.assert_called_once_with(
                        [1, 2], unittest.mock.ANY  # Timestamp
                    )
                    scraper.tgwrapper.push_notifications.assert_called_once_with({'1': [product, product2]})

    # This code is commented out because it gives little informational value, but makes mutmut tests long
    # def test_example(self):
    #     scraper = OzonScraper(self.tgwrapper)
    #
    #     answer = scraper.scrape_product(sku="1711093999")
    #     # print(answer)
    #     assert answer is not None  # The only way to check that at least something was parsed
