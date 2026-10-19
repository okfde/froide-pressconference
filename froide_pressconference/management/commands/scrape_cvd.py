import asyncio
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from ...sources.cvd_scraper import DummyHandler, download_cvd


class Command(BaseCommand):
    help = "Scrape pages"

    def handle(self, *args, **options):
        username, password = settings.CVD_CREDENTIALS.split(",", 1)
        chrome_path = os.environ.get("CHROME_PATH", settings.CHROME_BINARY_PATH)
        headless = bool(os.environ.get("CHROME_HEADLESS", False))
        handler = DummyHandler()
        asyncio.run(
            download_cvd(
                username,
                password,
                handler,
                chrome_binary_path=chrome_path,
                headless=headless,
            )
        )
