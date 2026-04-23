from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from froide.helper.search.queryset import SearchQuerySetWrapper
from froide.helper.utils import update_query_params
from froide.searchalert.configuration import AlertConfiguration, AlertEvent


class PressConferenceAlertConfiguration(AlertConfiguration):
    key = "pressconference"
    title = _("Press conferences")

    @classmethod
    def search(
        cls, query, start_date, item_count=5, user=None, **kwargs
    ) -> list[AlertEvent]:
        from .documents import PressConferenceDocument
        from .filters import PressConferenceFilterSet
        from .models import PressConference

        s = PressConferenceDocument.search()
        s = s.highlight_options(encoder="html", number_of_fragments=10).highlight(
            "content"
        )
        s = s.sort("-date")
        sqs = SearchQuerySetWrapper(s, PressConference)

        filtered = PressConferenceFilterSet(
            {"q": query, "date_after": start_date.date().strftime("%Y-%m-%d")},
            queryset=sqs,
        )
        sqs = filtered.qs
        count = sqs.count()
        qs = sqs.to_queryset()
        qs = qs[:item_count]
        queryset = sqs.wrap_queryset(qs)

        return (
            count,
            [
                AlertEvent(
                    title=e.title,
                    url=e.get_absolute_domain_url(),
                    content=e.query_highlight,
                )
                for e in queryset
            ],
        )

    @classmethod
    def get_search_link(cls, query, start_date) -> str:
        base_url = settings.SITE_URL + reverse("pressconference:pressconference-list")
        return update_query_params(
            base_url,
            {
                "q": query,
                "date_after": start_date.date().strftime("%Y-%m-%d"),
                "sort": "-date",
            },
        )
