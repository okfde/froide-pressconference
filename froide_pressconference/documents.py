from django.db.models import Exists, OuterRef

from django_elasticsearch_dsl import Document, fields

from froide.helper.search import (
    get_index,
    get_search_analyzer,
    get_search_quote_analyzer,
    get_text_analyzer,
)

from .models import PressConference, Speaker, Speech

press_conference_index = get_index("pressconference")
analyzer = get_text_analyzer()
search_analyzer = get_search_analyzer()
search_quote_analyzer = get_search_quote_analyzer()


@press_conference_index.document
class PressConferenceDocument(Document):
    date = fields.DateField(attr="date")
    category = fields.IntegerField(attr="category_id")
    speakers = fields.ListField(field=fields.KeywordField())
    topics = fields.ListField(field=fields.TextField())

    content = fields.TextField(
        analyzer=analyzer,
        search_analyzer=search_analyzer,
        search_quote_analyzer=search_quote_analyzer,
        index_options="offsets",
    )

    class Django:
        model = PressConference

    def get_queryset(self):
        return super().get_queryset().prefetch_related("sections", "sections__speeches")

    def prepare_speakers(self, obj):
        return list(
            Speaker.objects.filter(
                Exists(
                    Speech.objects.filter(
                        speaker=OuterRef("id"), section__press_conference_id=obj.id
                    )
                )
            ).values_list("name", flat=True)
        )

    def prepare_topics(self, obj):
        return obj.description.splitlines()

    def prepare_content(self, obj):
        def get_section_content(section):
            texts = []
            for speech in section.speeches.all():
                texts.append(speech.text)
            return "\n\n".join(texts)

        return (
            obj.description
            + "\n\n"
            + "\n\n".join(
                get_section_content(section) for section in obj.sections.all()
            )
        )
