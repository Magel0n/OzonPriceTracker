import unittest

from scraper import OzonScraper
from api_models import *

class TestScrapper(unittest.TestCase):
    def test__check_url(self):
        scraper = OzonScraper()
        print("DUH")