import os
import time
import threading

import seleniumbase

from api_models import TrackedProductModel
from database import Database
from tgwrapper import TelegramWrapper


class OzonScraper:
    database: Database

    def __init__(self, database: Database, tgwrapper: TelegramWrapper):
        self.headlessness: bool = bool(
            os.environ.get("scraper_headlessness", False))
        self.update_time: int = int(
            os.environ.get("scraper_update_time", 60 * 60 * 24))
        self.keepFailure: bool = bool(
            os.environ.get("scraper_keepFailure", False))
        self.tgwrapper = tgwrapper
        threading.Thread(target=self.update_loop, daemon=True).start()

    def update_loop(self):
        self.database = Database()
        job = self.update_offers_job
        while True:
            job = job()
            time.sleep(self.update_time)

    def update_offers_job(self):
        products = self.database.get_products()
        urls = []
        for product in products:
            if product.url == "https://www.ozon.ru/product/" + product.sku:
                urls.append(product.sku)
            else:
                urls.append(product.url)

        new_prices = self._get_price_for_products(urls)
        products_to_send: list[TrackedProductModel] = []
        for product, newPrice in zip(products, new_prices):
            if newPrice is None:
                continue

            if float(product.price) < newPrice:
                products_to_send.append(product)

            product.price = str(newPrice)

        self.database.update_products(products)
        products_ids = [product.id for product in products]
        self.database.add_to_price_history(products_ids, int(time.time()))
        usersToSend = self.database.get_users_by_products(products_to_send)

        users_to_products: dict[str, list[TrackedProductModel]] = {}

        for userId, items in usersToSend.items():
            for item in (
                    filter(lambda x: x in products_to_send, items)):
                if users_to_products[str(userId)]:
                    users_to_products[str(userId)] = [item]
                else:
                    users_to_products[str(userId)].append(item)

        self.tgwrapper.push_notifications(users_to_products)
        return self.update_offers_job

    # Should return product info by sku or url
    # use sku or url to find everything else
    def scrape_product(self,
                       sku: str | None = None,
                       url: str | None = None) -> TrackedProductModel | None:
        if sku is not None and url is not None:
            return None  # Why are you having both?

        if sku is None and url is None:
            return None  # Nothing inputted

        if sku is None:
            correct_url = self._check_url(url)
        else:
            correct_url = self._check_url("https://www.ozon.ru/product/" + sku)
        name_lasting = None
        price_lasting = None
        seller_lasting = None
        if correct_url is None:
            return None  # Failure to parse url

        # print(correct_url)  # TODO fix url as sku possibility

        name_lasting, price_lasting, seller_lasting = (
            self._get_info_for_product(correct_url))
        name = None
        price = None
        seller = None
        if (seller_lasting is None
                or price_lasting is None
                or name_lasting is None):
            for i in range(3):
                name, price, seller = self._get_info_for_product(correct_url)
                if seller_lasting is None:
                    seller_lasting = seller
                if price_lasting is None:
                    price_lasting = price
                if name_lasting is None:
                    name_lasting = name

        if seller_lasting is None:
            seller_lasting = ""
        if name_lasting is None:
            name_lasting = ""

        if price_lasting is None:
            return None

        if sku is None:
            sku = ""

        if url is None:
            url = correct_url

        product = TrackedProductModel(id=None,
                                      url=url,
                                      sku=sku,
                                      name=name_lasting,
                                      price=str(price_lasting),
                                      seller=seller_lasting,
                                      tracking_price=None)

        return product

    def _get_price_for_products(self, urls: list[str]) -> list[int | None]:
        prices = []
        try:
            with seleniumbase.SB(undetectable=True,
                                 headless=self.headlessness) as sb:
                for url in urls:
                    sb.uc_open_with_reconnect(url, 4)
                    prices.append(self._selenium_get_price_for_product(sb))
                return prices
        except Exception as e:
            print(e)
            return [None] * len(urls)

    def _selenium_get_name_for_product(self, sb: seleniumbase.SB)\
            -> str | None:
        known_names = [".m2q_28", ".m1q_28", ".m3q_28"]
        for i in range(3):
            for elem in known_names:
                result = sb.find_elements(elem)
                if result:
                    return result[0].text
                sb.sleep(1)
            if self.keepFailure:
                sb.save_page_source("failureName")
        return None

    def _selenium_get_seller_for_product(self, sb: seleniumbase.SB)\
            -> str | None:
        known_names = [".tsCompactControl500Medium > span:nth-child(1)",
                       "div.tsCompactControl500Medium > span:nth-child(1)",
                       ".m5p_28",
                       ".y6k_28 > div:nth-child(2) > "
                       "div:nth-child(2) > div:nth-child(1)"
                       " > div:nth-child(1) > a:nth-child(1)"]
        for i in range(3):
            for elem in known_names:
                result = sb.find_elements(elem)
                if result:
                    return result[0].text
                sb.sleep(1)
            if self.keepFailure:
                sb.save_page_source("failureSeller")
        return None

    def _selenium_get_price_for_product(self, sb: seleniumbase.SB)\
            -> int | None:
        known_names = [".m6p_28", ".m5p_28", "div.m5p_28"]
        for i in range(3):
            for elem in known_names:
                result = sb.find_elements(elem)
                if result:
                    result = result[0].text
                    result = int("".join(result[:-1].split("\u2009")))
                    return result
                sb.sleep(1)
            if self.keepFailure:
                sb.save_page_source("failurePrice")
        return None

    def _get_info_for_product(self, url: str) \
            -> (str | None, int | None, str | None):
        """
        Gets the price of a product from Ozon using Selenium.

        Args:
            url (str): The url to check.

        Returns:
            name   of the product or None if failed to access.
            price  of the product or None if failed to access.
            seller of the product or None if failed to access.
        """
        name = None
        price = None
        seller = None
        try:
            with seleniumbase.SB(undetectable=True,
                                 headless=self.headlessness) as sb:
                sb.uc_open_with_reconnect(url, 4)

                name = self._selenium_get_name_for_product(sb)
                seller = self._selenium_get_seller_for_product(sb)
                price = self._selenium_get_price_for_product(sb)

                return name, price, seller
        except Exception as e:
            print(e)
            return None, None, None

    def _check_url(self, url: str) -> str | None:
        """
        Checks if the url is valid

        Args:
            url (str): The url to check.

        Returns:
            None: If the url is invalid.
            str:  If the url is valid, removes unnecessary info.
        """
        if url is None:
            return None

        splitted: list[str] = url.split("/")

        if splitted[0] == "https:" or splitted[0] == "http:":
            if splitted[1] == "":
                splitted = splitted[2:]
            else:
                return None

        if len(splitted) < 3:
            return None

        if splitted[0] == "www.ozon.ru":
            if splitted[1] != "product":
                return None
            if splitted[2] == "":
                return None

            return "https://" + "/".join(splitted[:3])

        else:
            return None
