from django.utils.translation import gettext_lazy as _

import django_filters
from elasticsearch_dsl.query import Q as ESQ

from froide.helper.search.filters import BaseSearchFilterSet
from froide.helper.widgets import BootstrapSelect, DateRangeWidget

from .models import PressConference


def override_field_default(cls, field, overrides=None, extra=None):
    res = {**cls.FILTER_DEFAULTS[field]}

    if overrides is not None:
        res.update(overrides)
    if extra is not None:
        old_extra = res.get("extra", lambda f: {})
        res["extra"] = lambda f: {**old_extra(f), **extra(f)}
    return res


class PressConferenceFilterSet(BaseSearchFilterSet):
    date = django_filters.DateFromToRangeFilter(
        widget=DateRangeWidget, method="filter_date_range"
    )

    sort = django_filters.ChoiceFilter(
        choices=[
            ("date", _("date (oldest first)")),
            ("-date", _("date (newest first)")),
        ],
        label=_("sort"),
        empty_label=_("default sort"),
        widget=BootstrapSelect,
        method="add_sort",
    )
    query_fields = ["content", "description"]

    class Meta:
        model = PressConference
        fields = [
            "q",
            "date",
        ]

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        facet_config = self.view.facet_config
        for key, facet in facet_config.items():
            if facet["type"] == "term":
                qs = qs.add_aggregation([key])
            elif facet["type"] == "date_histogram":
                facet_kwargs = {
                    k: v for k, v in facet.items() if k in ("interval", "format")
                }
                qs = qs.add_date_histogram(key, **facet_kwargs)
        return qs

    def filter_date_range(self, qs, name, value):
        range_kwargs = {}
        if value.start is not None:
            range_kwargs["gte"] = value.start
        if value.stop is not None:
            range_kwargs["lte"] = value.stop

        return self.apply_filter(qs, name, ESQ("range", **{name: range_kwargs}))

    def add_sort(self, qs, name, value):
        if value:
            return qs.add_sort(value)
        return qs
