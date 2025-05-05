import time

import seleniumbase

from api_models import TrackedProductModel
from database import Database
from tgwrapper import TelegramWrapper

class OzonScraper:
    database: Database

    def __init__(self, database: Database, tgwrapper: TelegramWrapper, headlessness: bool = False):
        self.database = database
        self.headlessness = headlessness
        self.tgwrapper = tgwrapper

    # Should run every so often, implementation and other details are up to you lmao
    # Use Database.get_products, Database.update_products, Database.get_users_by_products
    # TelegramWrapper.push_notifications, Database.add_to_price_history
    def update_offers_job(self) -> None:
        products = self.database.get_products()
        urls = []
        for product in products:
            if product.url == "https://www.ozon.ru/product/" + product.sku:
                urls.append(product.sku)
            else:
                urls.append(product.url)

        newPrices = self._get_info_for_products(urls)
        productsToSend = []
        for product, newPrice in zip(products, newPrices):
            if newPrice is None:
                continue

            if product.price < newPrice:
                productsToSend.append(product)

            product.price = newPrice


        self.database.update_products(products)
        usersToSend = self.database.get_users_by_products(productsToSend)




    # Should return product info by sku or url
    # use sku or url to find everything else
    def scrape_product(self, sku: str | None = None, url: str | None = None) -> TrackedProductModel | None:
        if sku is not None and url is not None:
            return None  # Why are you having both?

        if sku is None and url is None:
            return None  # Nothing inputted

        if sku is None:
            correctUrl = self._check_url(url)
        else:
            correctUrl = self._check_url("https://www.ozon.ru/product/" + sku)
        nameLasting = None
        priceLasting = None
        sellerLasting = None
        if correctUrl is None:
            return None  # Failure to parse url

        nameLasting, priceLasting, sellerLasting = self._get_info_for_product(correctUrl)
        name = None
        price = None
        seller = None
        if sellerLasting is None or priceLasting is None or nameLasting is None:
            for i in range(3):
                name, price, seller = self._get_info_for_product(correctUrl)
                if sellerLasting is None:
                    sellerLasting = seller
                if priceLasting is None:
                    priceLasting = price
                if nameLasting is None:
                    nameLasting = name

        if sellerLasting is None:
            sellerLasting = ""
        if nameLasting is None:
            nameLasting = ""

        if priceLasting is None:
            return None

        if sku is None:
            sku = ""

        if url is None:
            url = correctUrl

        return TrackedProductModel(id=None, url=url, sku=sku, name=nameLasting, price=str(priceLasting),
                                   seller=sellerLasting, tracking_price=None)

    def _get_info_for_products(self, urls: list[str]) -> list[int | None]:
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
                name = sb.find_elements(".m1q_28")[0].text
                # print(name)

                for i in range(3):
                    seller = sb.find_elements(".tsCompactControl500Medium > span:nth-child(1)")
                    if not seller:
                        seller = sb.find_elements("div.tsCompactControl500Medium > span:nth-child(1)")

                    if not seller:
                        # sb.save_page_source("failure")
                        # print("No seller found")
                        seller = None
                    if seller is not None:
                        seller = seller[0].text
                        break

                    seller = sb.sleep(1)  # Does not improve much
                # print(seller)

                price = sb.find_elements(".m5p_28")[0].text
                # print(price)
                price = int("".join(price[:-1].split("\u2009")))

            return name, price, seller
        except Exception as e:
            print(e)

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
    scraper = OzonScraper("")

    url1 = "https://www.ozon.ru/product/spalnyy-meshok-rsp-sleep-450-big-225-90-sm-molniya-sprava-1711093999/"
    url2 = "https://www.ozon.ru/product/palatka-4-mestnaya-2031340268/"
    url3 = ("https://www.ozon.ru/product/arbuznyy-instrument-iz-nerzhaveyushchey-stali-dlya-narezki-iskusstvennyh"
            "-priborov-nozh-instrumenty-1691927723/")

    url11 = "https://www.ozon.ru/product/spalnyy-meshok-turisticheskiy-golden-shark-elbe-450-xl-pravaya-molniya-1950697799/?at=jYtZoW3qgfRmpMwgC6NjPA5c4Q2j7EtXY392WU77N8wn"

    url = scraper._check_url(url1)
    print(scraper.scrape_product(url1))
    print(scraper.scrape_product(url2))
    print(scraper.scrape_product(url3))
    print(scraper.scrape_product(url11))
