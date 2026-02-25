from froide.foirequest.models import FoiRequest

from .models import PressConference, Section

FOIREQUEST_TAGS = "Regierungspressekonferenz"


def create_link(sender: FoiRequest, **kwargs):
    reference = kwargs.get("reference")
    if not reference:
        reference = sender.reference
    if not reference:
        return
    if not reference.startswith("pressconference:"):
        return
    namespace, pc_section_value = reference.split(":", 1)
    try:
        section_id, pc_id = pc_section_value.split("@", 1)
    except (ValueError, IndexError):
        return

    if not section_id or not pc_id:
        return

    try:
        pc_id = int(pc_id)
    except ValueError:
        return
    try:
        section_id = int(section_id)
    except ValueError:
        return

    try:
        pc = PressConference.objects.get(pk=pc_id)
    except PressConference.DoesNotExist:
        return

    try:
        section = Section.objects.get(press_conference=pc, pk=section_id)
    except Section.DoesNotExist:
        return

    section.foirequests.add(sender)
    sender.tags.add(FOIREQUEST_TAGS)
