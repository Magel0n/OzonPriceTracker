import time

import seleniumbase

from api_models import TrackedProductModel
from database import Database
from tgwrapper import TelegramWrapper
import threading


class OzonScraper:
    database: Database

    def __init__(self, database: Database, tgwrapper: TelegramWrapper, headlessness: bool = False,
                 keepfailure: bool = False, update_time: int = 60 * 60 * 24):
        self.keepFailure = keepfailure
        self.database = database
        self.headlessness = headlessness
        self.tgwrapper = tgwrapper
        self.update_time = update_time
        threading.Thread(target=self.update_offers_job(), args=[self], daemon=True).start()

    # Should run every so often, implementation and other details are up to you lmao
    # Use Database.get_products, Database.update_products, Database.get_users_by_products
    # TelegramWrapper.push_notifications, Database.add_to_price_history
    def update_offers_job(self) -> None:
        threading.Timer(self.update_time, self.update_offers_job, args=[self]).start()
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

            if product.price < newPrice:
                products_to_send.append(product)

            product.price = newPrice

        self.database.update_products(products)
        products_ids = [product.id for product in products]
        self.database.add_to_price_history(products_ids, int(time.time()))
        usersToSend = self.database.get_users_by_products(products_to_send)

        users_to_products: dict[str, list[TrackedProductModel]] = {}

        for userId, items in usersToSend.items():
            productsForThisUser: list[TrackedProductModel] = []
            for item in filter(lambda x: x in products_to_send, items):
                if users_to_products[str(userId)]:
                    users_to_products[str(userId)] = [item]
                else:
                    users_to_products[str(userId)].append(item)

        self.tgwrapper.push_notifications(users_to_products)

    # Should return product info by sku or url
    # use sku or url to find everything else
    def scrape_product(self, sku: str | None = None, url: str | None = None) -> TrackedProductModel | None:
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

        name_lasting, price_lasting, seller_lasting = self._get_info_for_product(correct_url)
        name = None
        price = None
        seller = None
        if seller_lasting is None or price_lasting is None or name_lasting is None:
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

        product = TrackedProductModel(id=None, url=url, sku=sku, name=name_lasting, price=str(price_lasting),
                                      seller=seller_lasting, tracking_price=None)

        return product

    def _get_price_for_products(self, urls: list[str]) -> list[int | None]:
        prices = []
        try:
            with seleniumbase.SB(undetectable=True, headless=self.headlessness) as sb:
                for url in urls:
                    sb.uc_open_with_reconnect(url, 4)
                    price = sb.find_elements(".m1q_28")
                    i = 0
                    while not price:
                        if i == 3:
                            break
                        price = sb.find_elements(".m1q_28")
                        sb.sleep(1)
                        i += 1
                    price = price[0].text
                    price = int("".join(price[:-1].split("\u2009")))
                    prices.append(price)
                return prices
        except Exception as e:
            print(e)
            return [None] * len(urls)

    def _get_info_for_product(self, url: str) -> (str | None, int | None, str | None):
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
            with seleniumbase.SB(undetectable=True, headless=self.headlessness) as sb:
                sb.uc_open_with_reconnect(url, 4)
                for i in range(3):
                    name = sb.find_elements(".m1q_28")
                    if not name:
                        name = sb.find_elements(".m1q_28")

                    if not name:
                        if self.keepFailure:
                            sb.save_page_source("failureName")
                        # print("No name found")
                        name = None
                    if name is not None:
                        name = name[0].text
                        break

                    sb.sleep(1)
                # print(name)

                for i in range(3):
                    seller = sb.find_elements(".tsCompactControl500Medium > span:nth-child(1)")
                    if not seller:
                        seller = sb.find_elements("div.tsCompactControl500Medium > span:nth-child(1)")
                    if not seller:
                        seller = sb.find_elements("div.sk4_28:nth-child(2) > a:nth-child(1)")
                    if not seller:
                        seller = sb.find_elements(".m5p_28")

                    if not seller:
                        if self.keepFailure:
                            sb.save_page_source("failureSeller")
                        # print("No seller found")
                        seller = None
                    if seller is not None:
                        seller = seller[0].text
                        break

                    sb.sleep(1)  # Does not improve much
                # print(seller)

                for i in range(3):
                    price = sb.find_elements(".m5p_28")
                    if not price:
                        price = sb.find_elements("div.m5p_28")

                    if not price:
                        if self.keepFailure:
                            sb.save_page_source("failurePrice")
                        # print("No price found")
                        price = None
                    if price is not None:
                        price = price[0].text
                        price = int("".join(price[:-1].split("\u2009")))
                        break

                    sb.sleep(1)

                price = sb.find_elements(".m5p_28")[0].text
                # print(price)
                price = int("".join(price[:-1].split("\u2009")))

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


if __name__ == '__main__':
    database = Database()
    scraper = OzonScraper(database, TelegramWrapper(database, "123"), headlessness=True, keepfailure=True, update_time=60)

    url1 = "https://www.ozon.ru/product/spalnyy-meshok-rsp-sleep-450-big-225-90-sm-molniya-sprava-1711093999/"
    url2 = "https://www.ozon.ru/product/palatka-4-mestnaya-2031340268/"
    url3 = ("https://www.ozon.ru/product/arbuznyy-instrument-iz-nerzhaveyushchey-stali-dlya-narezki-iskusstvennyh"
            "-priborov-nozh-instrumenty-1691927723/")

    url11 = "https://www.ozon.ru/product/spalnyy-meshok-turisticheskiy-golden-shark-elbe-450-xl-pravaya-molniya-1950697799/?at=jYtZoW3qgfRmpMwgC6NjPA5c4Q2j7EtXY392WU77N8wn"

    url = scraper._check_url(url1)
    print(scraper._check_url(url1))
    print(scraper.scrape_product(url=url1))
    print(scraper.scrape_product(url=url2))
    print(scraper.scrape_product(url=url3))
    print(scraper.scrape_product(url=url11))
