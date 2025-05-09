import os
import time
import threading

import seleniumbase

import asyncio

from api_models import TrackedProductModel
from database import Database
from tgwrapper import TelegramWrapper


class OzonScraper:
    database: Database

    def __init__(self, tgwrapper: TelegramWrapper,
                 retries: int = 3):  # pragma: no mutate
        """
        Initialise the Ozon scraper.

        This version is for testing purposes only.
        Due to Ozon's policy against scraping,
        this system is prone to failure.
        Forced usage of seleniumbase to at least connect to Ozon website.

        Parameters:
            tgwrapper (TelegramWrapper): telegram wrapper object
            retries (int): number of times to retry the scraping (default: 3)
        """
        self.headlessness: bool = bool(os.environ.get(  # pragma: no mutate
            "scraper_headlessness", False))  # pragma: no mutate
        self.update_time: int = int(os.environ.get(  # pragma: no mutate
            "scraper_update_time", 60))  # pragma: no mutate
        self.keepFailure: bool = bool(os.environ.get(  # pragma: no mutate
            "scraper_keepFailure", False))  # pragma: no mutate
        self.retries_count = retries  # pragma: no mutate
        self.tgwrapper = tgwrapper  # pragma: no mutate
        threading.Thread(target=self.update_loop,  # pragma: no mutate
                         daemon=True).start()  # pragma: no mutate

    def update_loop(self):
        """
        Update loop for the thread job.
        Makes sure that python won't fail due to recursion limit.
        Sleeps for the update_time seconds.
        """
        self.database = Database()
        job = self.update_offers_job  # pragma: no mutate
        # print("Started the update loop")
        while True:
            time.sleep(self.update_time)
            job = job()  # pragma: no mutate

    def update_offers_job(self):
        """
        Update the offers job for Ozon.
        Takes the products from the database,
        checks them using SeleniumBase,
        then updates the database
        and notifies users if needed.
        """
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
        print(f"Product ids: {products_to_send}")
        usersToSend = self.database.get_users_by_products(
            list(map(lambda x: x.id, products_to_send))
        )
        
        asyncio.run(self.tgwrapper.push_notifications(usersToSend))
        return self.update_offers_job

    # Should return product info by sku or url
    # use sku or url to find everything else
    def scrape_product(self,
                       sku: str | None = None,
                       url: str | None = None) -> TrackedProductModel | None:
        """
        Scrape the product from Ozon
        Most checks for the API are done within SeleniumBase
        I added some to comply with the requirements
        Price is the only required piece of information,
        so others will be returned as "" if not scraped.

        Parameters:
            sku (str | None): SKU of the product to scrape
            url (str | None): URL of the product to scrape
            Between sku and url at most one must be given

        Returns:
            TrackedProductModel: Tracked product model,
                            id and TrackingPrice are None
            None: if product price could not be parsed.
        """
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
        """
        This function scrapes the products from Ozon using SeleniumBase
        By creating just one instance of SeleniumBase, a lot of time is saved,
        so this is a very key improvement.

        Parameters:
            urls (list[str]): list of urls to scrape

        Returns:
            list[int | None]: list of  all the prices scraped, None per failure
        """
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
        """
        This function separates logic from general scraping.
        known_names are limited, as I could not observe
        the patterns of Ozon enough.
        Requires constant updates of known names for successive parsing,
        but saves failureName.html for debugging

        Parameters:
            sb: seleniumbase.SB: SeleniumBase object with url pre-connected

        Returns:
            str | None: the name of the product or None if failed
        """
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
        """
        This function separates logic from general scraping.
        known_names are limited, as I could not observe
        the patterns of Ozon enough.
        Requires constant updates of known names for successive parsing,
         but saves failureSeller.html for debugging

        Parameters:
            sb: seleniumbase.SB: SeleniumBase object with url pre-connected

        Returns:
            str | None: the seller of the product or None if failed
        """
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
        """
        This function separates logic from general scraping.
        known_names are limited, as I could not observe
        the patterns of Ozon enough.
        Requires constant updates of known names for successive parsing,
        but saves failurePrice.html for debugging

        Parameters:
            b: seleniumbase.SB: SeleniumBase object with url pre-connected

        Returns:
            int | None: the price of the product or None if failed
        """
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

        Parameters:
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

        Parameters:
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
        """
        Creates the sku from the url

        Apparently sku in russian is the same as Articule,
        which is at the end of the url
        Getting the sku is primarily for Database knowledge for now.

        Parameters:
            url: str: The url to map from

        Returns:
            str: sku or "" if failed
        """
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
