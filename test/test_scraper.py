import unittest
from unittest.mock import patch, MagicMock
from api_models import TrackedProductModel
from database import Database
from scraper import (OzonScraper)


class TestScrapper(unittest.TestCase):
    def setUp(self):
        self.database = Database()
    def test__check_url(self):
        scraper = OzonScraper("", "")
        print("DUH")