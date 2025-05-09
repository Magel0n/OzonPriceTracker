import os
import time
import threading

import seleniumbase

from api_models import TrackedProductModel
from database import Database
from tgwrapper import TelegramWrapper


class OzonScraper:
    database: Database

    def __init__(self, tgwrapper: TelegramWrapper,
                 retries: int = 3):  # pragma: no mutate
        self.headlessness: bool = bool(os.environ.get(  # pragma: no mutate
            "scraper_headlessness", False))  # pragma: no mutate
        self.update_time: int = int(os.environ.get(  # pragma: no mutate
            "scraper_update_time", 60 * 60 * 24))  # pragma: no mutate
        self.keepFailure: bool = bool(os.environ.get(  # pragma: no mutate
            "scraper_keepFailure", False))  # pragma: no mutate
        self.retries_count = retries  # pragma: no mutate
        self.tgwrapper = tgwrapper  # pragma: no mutate
        threading.Thread(target=self.update_loop,  # pragma: no mutate
                         daemon=True).start()  # pragma: no mutate

    def update_loop(self):
        self.database = Database()
        job = self.update_offers_job  # pragma: no mutate
        # print("Started the update loop")
        while True:
            time.sleep(self.update_time)
            job = job()  # pragma: no mutate

    def update_offers_job(self):
        products = self.database.get_products()
        urls = []
        # print("Started the update_offers_job")
        for product in products:
            if product.url is None:
                urls.append("https://www.ozon.ru/product/" + product.sku)
            else:
                urls.append(product.url)

        # print("Started the _get_price_for_products")
        new_prices = self._get_price_for_products(urls)
        # print("Ended the _get_price_for_products")
        products_to_send: list[TrackedProductModel] = []
        for product, newPrice in zip(products, new_prices):
            if newPrice is None:
                continue

            if float(product.price) > newPrice:
                products_to_send.append(product)

            product.price = str(newPrice)

        # print("Ended products phase\nUpdating database normal")
        self.database.update_products(products)
        # print("Ended database update\nUpdating database history")
        products_ids = [product.id for product in products]
        self.database.add_to_price_history(products_ids, int(time.time()))
        # print("Ended database update\nGetting users to send notifications")
        usersToSend = self.database.get_users_by_products(products_to_send)

        users_to_products: dict[str, list[TrackedProductModel]] = {}
        products_to_send_id = list(map(lambda product: product.id,
                                       products_to_send))
        # print(usersToSend, products_ids, products_to_send,
        # products_to_send_id, sep="\n")

        for userId, items in usersToSend.items():
            for item in (
                    filter(lambda x: x.id in products_to_send_id, items)):
                # print(users_to_products, item, userId)
                if str(userId) not in users_to_products.keys():
                    # print("creating a new item")
                    users_to_products[str(userId)] = [item]
                else:
                    # print("Appending to existing item")
                    users_to_products[str(userId)].append(item)
        # print(users_to_products)
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
            for i in range(self.retries_count):
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
            sku = self._create_sku_from_url(correct_url)

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
            while (len(prices) < len(urls)):
                prices.append(None)
            return prices

    def _selenium_get_name_for_product(self, sb: seleniumbase.SB) \
            -> str | None:
        known_names = [".m2q_28", ".m1q_28", ".m3q_28"]
        for i in range(self.retries_count):
            for elem in known_names:
                result = sb.find_elements(elem)
                if result:
                    return result[0].text
                sb.sleep(1)
            if self.keepFailure:
                sb.save_page_source("failureName")
        return None

    def _selenium_get_seller_for_product(self, sb: seleniumbase.SB) \
            -> str | None:
        known_names = [".tsCompactControl500Medium > span:nth-child(1)",
                       "div.tsCompactControl500Medium > span:nth-child(1)",
                       ".m5p_28",
                       ".y6k_28 > div:nth-child(2) > "
                       "div:nth-child(2) > div:nth-child(1)"
                       " > div:nth-child(1) > a:nth-child(1)"]
        for i in range(self.retries_count):
            for elem in known_names:
                result = sb.find_elements(elem)
                if result:
                    return result[0].text
                sb.sleep(1)
            if self.keepFailure:
                sb.save_page_source("failureSeller")
        return None

    def _selenium_get_price_for_product(self, sb: seleniumbase.SB) \
            -> int | None:
        known_names = [".m6p_28", ".m5p_28", "div.m5p_28"]
        for i in range(self.retries_count):
            for elem in known_names:
                result = sb.find_elements(elem)
                if result:
                    result = result[0].text
                    try:
                        result = int("".join(result[:-1].split("\u2009")))
                        return result
                    except ValueError:
                        print("Failed to parse price", result)
                        return None
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

    def _create_sku_from_url(self, url: str) -> str:
        if url is None:
            return ""

        splitted: list[str] = url.split("/")

        if splitted[0] == "https:" or splitted[0] == "http:":
            if splitted[1] == "":
                splitted = splitted[2:]
            else:
                return ""

        if len(splitted) < 3:
            return ""

        if splitted[0] == "www.ozon.ru":
            if splitted[1] != "product":
                return ""
            if splitted[2] == "":
                return ""

            if splitted[2].split("-"):
                try:
                    sku = int(splitted[2].split("-")[-1])
                    return str(sku)
                except ValueError:  # No sku found
                    return ""
        return ""
