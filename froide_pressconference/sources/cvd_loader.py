import re
import zoneinfo
from datetime import datetime as dt
from functools import cache
from pathlib import Path

from lxml import html as etree
from lxml.html import Element
from slugify import slugify

from froide.helper.db_utils import save_obj_with_slug
from froide.publicbody.models import PublicBody

from ..models import (
    PressConference,
    Section,
    Speaker,
    Speech,
    SpeechKind,
)
from .cvd_grammar import (
    QuestionItem,
    SideNoteItem,
    SpeakerItem,
    SpeechItem,
    bpk_grammar,
    function_speaker,
    ministry_speaker,
)

DATE_PATTERN = re.compile(r"\s*(\d{1,2})\.\s*(\d{1,2}|[a-zä]+)\.?\s*(\d{4})\s*")
DE_MONTH_MAPPING = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

COLLAPSE_WS = re.compile(r" +")
COLLAPSE_2NL = re.compile(r"\n\n\n+")

BERLIN_TZ = zoneinfo.ZoneInfo("Europe/Berlin")


def clean_text(text):
    text = text.replace("\xa0", " ")
    return COLLAPSE_WS.sub(" ", text).strip()


def extract_text(el):
    result = []

    # Handle element's direct text
    if el.text:
        text = el.text
        result.append(text)

    # Handle child els
    for child in el:
        child_text = extract_text(child)
        result.append(child_text)

        if child.tag in ("p", "br", "li"):
            result.append("\n")
        # Handle tail text
        if child.tail:
            tail = child.tail
            result.append(tail)

    return clean_text("".join(result))


def parse_date(date_str: str) -> dt:
    date_str = date_str.strip().lower()
    if match := DATE_PATTERN.search(date_str):
        day, month_or_num, year = match.groups()
        try:
            month_int = int(month_or_num)
        except ValueError:
            month_int = DE_MONTH_MAPPING[month_or_num]
        return dt(int(year), month_int, int(day)).astimezone(BERLIN_TZ)
    raise ValueError(f"Could not parse date from '{date_str}'")


def upper_first(s):
    return s[0].upper() + s[1:]


@cache
def get_publicbody_from_abbr(abbr: str):
    try:
        pb = (
            PublicBody.objects.filter(
                other_names__contains=abbr, jurisdiction__slug="bund"
            )
            .order_by("id")
            .first()
        )
        return pb
    except PublicBody.DoesNotExist:
        return None


class CVDLoader:
    first_paragraph_has_topic = False

    def __init__(self, content: str):
        self.doc = etree.fromstring(content)

    def get_text(self, xpath):
        if (el := self.get_el(xpath)) is not None:
            return extract_text(el)

    def get_el(self, xpath):
        els = self.doc.xpath(xpath)
        if not len(els):
            return None
        if len(els) > 1:
            print("Warning: more than one match for ", xpath)
        return els[0]

    def get_date(self):
        # Implementation for detecting date
        if text := self.get_text("//p[@class='date']"):
            return parse_date(text)

    def get_main(self):
        return self.get_el("//div[@class='basepage_pages']")

    def get_paragraphs(self) -> list[Element]:
        return self.get_main().xpath("./*[local-name()='p' or local-name()='ul']")

    def get_abstract(self):
        return self.get_main().xpath("./div[@class='abstract']")

    TOPIC_MARKER = re.compile(r"^Themen:?")

    def get_topics(self):
        abstract = self.get_abstract()
        text = None
        if len(abstract):
            text = extract_text(abstract[0])

        if not text:
            first_paragraph = self.get_main().xpath("./p")[0]
            text = clean_text(first_paragraph.text_content())
            if self.TOPIC_MARKER.search(text.strip()) is None:
                return []
            self.first_paragraph_has_topic = True
        return self.parse_topics(text)

    def parse_topics(self, text):
        topics = [
            t for line in text.splitlines() if (t := clean_text(line.replace("•", "")))
        ]
        if len(topics) == 0:
            return
        topics[0] = self.TOPIC_MARKER.sub("", topics[0]).strip()
        if not topics[0]:
            topics = topics[1:]
        if len(topics) == 1:
            return [t for part in topics[0].split(", ") if (t := upper_first(part))]
        return topics

    def extract_paragraphs(self):
        paras = self.get_paragraphs()
        for i, p in enumerate(paras):
            if i == 0 and self.first_paragraph_has_topic:
                continue
            meta = {"css_class": p.attrib.get("class", ""), "tag": p.tag}
            full_text = extract_text(p)
            for text in full_text.split("\n\n"):
                yield text, meta
                meta = None

    def get_as_text(self):
        content = "\n\n".join(
            content for content, meta in self.extract_paragraphs()
        ).strip()
        return COLLAPSE_2NL.sub("\n\n", content).strip() + "\n\n"

    def parse_with_grammar(self, text):
        return bpk_grammar.parse_string(text, parse_all=True)

    def create_and_load(self, category_slug):
        date = self.get_date()
        try:
            pc, _created = PressConference.objects.get_or_create(
                category__slug=category_slug,
                date=date,
            )
        except PressConference.DoesNotExist:
            pass
        self.parse_and_load(pc)

    def parse_and_load(self, pc: PressConference):
        date = self.get_date()
        topics = self.get_topics()
        description = "\n".join(topics)
        title = f"Regierungspressekonferenz vom {date.strftime('%d.%m.%Y')}"

        pc.date = date
        pc.title = title
        pc.slug = slugify(title)
        pc.description = description
        save_obj_with_slug(pc)
        updating = pc.sections.all().count() > 0
        if updating:
            pc.sections.all().delete()

        text = self.get_as_text()
        parse_result = self.parse_with_grammar(text)
        parse_types = (SideNoteItem, QuestionItem, SpeakerItem, SpeechItem)
        section = None
        question_label = None
        section_order = 0
        speech_order = 0
        last_speech = None
        speech_kind = None
        speaker = None

        def is_same_speech(kind, speaker=None):
            if last_speech is None:
                return False
            if last_speech.kind != kind:
                return False
            if speaker and last_speech.speaker != speaker:
                return False
            return True

        def is_continued_question(label):
            lower_label = label.lower()
            return (
                "zusatz" in lower_label
                or "folge" in lower_label
                or "nachfrage" in lower_label
            )

        def new_section():
            nonlocal section_order
            section, _created = Section.objects.get_or_create(
                press_conference=pc,
                order=section_order,
            )
            section_order += 1
            return section

        def parse_speaker(speaker_name):
            if match := ministry_speaker.re_match(speaker_name):
                name, ministry_abbr = match.groups()
                pb = get_publicbody_from_abbr(ministry_abbr)
                speaker, _created = Speaker.objects.get_or_create(
                    name=name, publicbody=pb
                )
                return speaker
            if match := function_speaker.re_match(speaker_name):
                function, name = match.groups()
                speaker, _created = Speaker.objects.get_or_create(
                    name=name.strip(),
                    title=function.strip(),
                )
                return speaker
            speaker = Speaker.objects.filter(
                name=speaker_name,
            ).first()
            if not speaker:
                speaker, _created = Speaker.objects.get_or_create(
                    name=speaker_name,
                )
            return speaker

        section = new_section()
        for item in parse_result.as_list():
            if not isinstance(item, parse_types):
                continue
            if isinstance(item, SideNoteItem):
                Speech.objects.update_or_create(
                    section=section,
                    order=speech_order,
                    defaults={
                        "kind": SpeechKind.SIDENOTE,
                        "text": str(item).strip(),
                    },
                )
                speech_order += 1
            elif isinstance(item, QuestionItem):
                question_label = str(item)
                continued = is_continued_question(question_label)
                if continued:
                    speech_kind = SpeechKind.FOLLOWUP
                else:
                    speech_kind = SpeechKind.QUESTION
                    section = new_section()
                speaker = None
            elif isinstance(item, SpeakerItem):
                speaker_name = str(item)
                speaker = parse_speaker(speaker_name)
                speech_kind = SpeechKind.SPEECH
                question_label = ""
            elif isinstance(item, SpeechItem):
                if is_same_speech(speech_kind, speaker):
                    last_speech.text += f"\n\n{str(item)}"
                    last_speech.text = last_speech.text.strip()
                    last_speech.save()
                else:
                    last_speech, _created = Speech.objects.update_or_create(
                        section=section,
                        order=speech_order,
                        defaults={
                            "kind": speech_kind or SpeechKind.SPEECH,
                            "speaker": speaker,
                            "label": question_label or "",
                            "text": str(item).strip(),
                        },
                    )
                    speech_order += 1

        if updating:
            Section.objects.filter(
                press_conference=pc, order__gte=section_order
            ).delete()
            Speech.objects.filter(
                section__press_conference=pc, order__gte=speech_order
            ).delete()
        return pc


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        filenames = sys.argv[1:]
    else:
        filenames = list(Path("./data_cvd/").glob("*.html"))
    for filename in filenames:
        try:
            with open(filename) as f:
                content = f.read()
            loader = CVDLoader(content)
            text = loader.get_as_text()
            try:
                result = loader.parse()
            except Exception:
                with open("current.txt", "w") as f:
                    f.write(text)
                raise

            print(result)
            # for part in parts:
            #     print(part)
            # for t in topics:
            #     print(t)
        except Exception as e:
            print("Failed to load", filename, e)
            raise e
