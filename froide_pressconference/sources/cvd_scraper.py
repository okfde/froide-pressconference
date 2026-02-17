import asyncio
import logging
from zoneinfo import ZoneInfo

from lxml import html as etree
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab

logger = logging.getLogger(__name__)


DOMAIN = "https://cvd.bundesregierung.de"

BERLIN = ZoneInfo("Europe/Berlin")


async def get_dom(tab: Tab):
    content = await tab.page_source
    return etree.fromstring(content)


async def login(tab: Tab, username, password):
    await tab.go_to(f"{DOMAIN}/cvd-de/login")
    input_username = await tab.find(tag_name="input", name="userName", timeout=20)
    await input_username.insert_text(username)
    input_password = await tab.find(tag_name="input", name="password")
    await input_password.insert_text(password)
    login_button = await tab.find(tag_name="input", name="submit")
    await login_button.click()

    await tab.find(text="Willkommen", tag_name="h1", timeout=20)


async def start_search(tab: Tab):
    await tab.go_to(f"{DOMAIN}/cvd-de/pressekonferenzen-briefings")
    form = await tab.find(tag_name="form", name="SuchFormular", timeout=20)
    search_action = form.attributes.get("action") or ""
    form_state_input = await tab.find(tag_name="input", name="formState")
    form_state = form_state_input.attributes["value"]

    search_url = (
        search_action if search_action.startswith("http") else (DOMAIN + search_action)
    )
    query = (
        f"?formState={form_state}&query=Regierungspressekonferenz&facets%5B71432%5D=71424"
        "&dateRanges%5B71432%5D.from=&dateRanges%5B71432%5D.to=&submit=suchen"
    )
    await tab.go_to(search_url + query)
    dom = await get_dom(tab)

    # paging: pick second-to-last <li> inside .paging
    lis = dom.xpath("//div[contains(@class, 'paging')]//ul//li")
    target_li = lis[-2]
    last_a = target_li.xpath(".//a")[0]
    last_href = last_a.attrib["href"]
    result_path, max_page = last_href.rsplit("&page=", 1)
    max_page = int(max_page)

    return result_path, max_page


async def download_listing(tab, result_path, page_num=1):
    if page_num > 1:
        url = f"{DOMAIN}{result_path}&page={page_num}"
        await tab.go_to(url)

    root = await get_dom(tab)

    rows = root.xpath("//table/tbody/tr")
    results = []
    for row in rows:
        date_cell, link_cell = row.xpath("./td")

        date_text = date_cell.text_content()
        link_node = link_cell.xpath("a")[0]
        link = link_node.attrib["href"]
        title = link_node.text_content()
        results.append(
            {
                "url": f"{DOMAIN}{link}",
                "title": title.strip(),
                "date": date_text.strip(),
            }
        )
    return results


class DummyHandler:
    def should_download(self, url: str) -> bool:
        return True

    def store_html(self, url: str, file_path: str, content: str): ...


async def download_pages(tab: Tab, handler: DummyHandler):
    rss_path, max_page = await start_search(tab)
    logger.debug("Found %s pages", max_page)

    for pnum in range(1, max_page + 1):
        logger.debug("Trying page %s", pnum)
        items = await download_listing(tab, rss_path, page_num=pnum)
        for item in items:
            if not item["title"].startswith("Regierungspressekonferenz"):
                continue
            logger.debug(item["title"])
            item_url = item["url"]
            if not (await handler.should_download(item_url)):
                continue
            await tab.go_to(item_url)
            html = await tab.page_source
            name = item_url.rstrip("/").rsplit("/", 1)[-1] or "index"
            file_path = f"cvd/{name}.html"
            await handler.store_html(item_url, file_path, html)


async def download_cvd(username, password, handler, chrome_binary_path=None):
    options = ChromiumOptions()
    if chrome_binary_path:
        options.binary_location = chrome_binary_path

    options.headless = False
    options.block_notifications = True
    options.block_popups = True

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await login(tab, username, password)
        await download_pages(tab, handler)


if __name__ == "__main__":
    import os

    username, password = os.environ["CVD_CREDENTIALS"].split(",", 1)
    handler = DummyHandler()
    asyncio.run(download_cvd(username, password, handler))
