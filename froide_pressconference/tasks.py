import asyncio
import logging

from django.conf import settings
from django.core.files.base import ContentFile

from celery import shared_task

from .models import PressConference, PressConferenceCategory

logger = logging.getLogger(__name__)


class CvdHandler:
    def __init__(self, pc_category):
        self.pc_category = pc_category

    async def should_download(self, url: str) -> bool:
        try:
            pc = await PressConference.objects.aget(
                source_url=url,
            )
        except PressConference.DoesNotExist:
            return True
        return not pc.source_file

    async def store_html(self, url: str, file_path: str, content: str):
        pc, _created = await PressConference.objects.aget_or_create(
            source_url=url, category=self.pc_category
        )
        pc.source_file.save(file_path, ContentFile(content), save=False)
        await pc.asave()


@shared_task
def update_cvd_task():
    from .sources.cvd_scraper import download_cvd

    pc_category = PressConferenceCategory.objects.get(slug="bpk")
    handler = CvdHandler(pc_category)
    username, password = settings.CVD_CREDENTIALS.split(",", 1)
    asyncio.run(
        download_cvd(
            username, password, handler, chrome_binary_path=settings.CHROME_BINARY_PATH
        )
    )
    pcs = PressConference.objects.filter(slug="", category=pc_category)
    for pc in pcs:
        parse_pressconference_task.delay(pc.id)


def parse_pressconference(pc):
    from .sources.cvd_loader import CVDLoader

    with pc.source_file.open() as f:
        content = f.read()
    loader = CVDLoader(content)
    loader.parse_and_load(pc)


@shared_task
def parse_pressconference_task(pc_id):
    try:
        pc = PressConference.objects.get(id=pc_id)
    except PressConference.DoesNotExist:
        return

    parse_pressconference(pc)
