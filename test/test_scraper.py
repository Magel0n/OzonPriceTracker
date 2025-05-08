import unittest
from unittest.mock import patch, MagicMock
from api_models import TrackedProductModel
from database import Database
from scraper import OzonScraper

from tgwrapper import TelegramWrapper


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
    def test__check_url(self):
        scraper = OzonScraper("", "")
        print("DUH")


if __name__ == '__main__':
    database = Database()
    scraper = OzonScraper(database, TelegramWrapper(database, "123"))

    print(scraper.keepFailure)
    print(scraper.headlessness)
    print(scraper.update_time)

    # url1 = "https://www.ozon.ru/product/spalnyy-meshok-rsp-sleep-450-big-225-90-sm-molniya-sprava-1711093999/"
    # url2 = "https://www.ozon.ru/product/palatka-4-mestnaya-2031340268/"
    # url3 = ("https://www.ozon.ru/product/arbuznyy-instrument-iz-nerzhaveyushchey-stali-dlya-narezki-iskusstvennyh"
    #         "-priborov-nozh-instrumenty-1691927723/")
    #
    # url11 = "https://www.ozon.ru/product/spalnyy-meshok-turisticheskiy-golden-shark-elbe-450-xl-pravaya-molniya-1950697799/?at=jYtZoW3qgfRmpMwgC6NjPA5c4Q2j7EtXY392WU77N8wn"
    #
    # url = scraper._check_url(url1)
    # print(scraper._check_url(url1))
    # print(scraper.scrape_product(url=url1))
    # print(scraper.scrape_product(url=url2))
    # print(scraper.scrape_product(url=url3))
    # print(scraper.scrape_product(url=url11))