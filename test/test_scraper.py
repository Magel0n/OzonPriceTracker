import unittest
from unittest.mock import patch, MagicMock
from api_models import TrackedProductModel
from database import Database

class TestScrapper(unittest.TestCase):
    def test__check_url(self):
        # scraper = OzonScraper("", "")
        print("DUH")