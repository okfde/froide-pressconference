from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import DetailView

from django_comments import get_model

from froide.helper.breadcrumbs import Breadcrumbs, BreadcrumbView
from froide.helper.search.views import BaseSearchView

from .documents import PressConferenceDocument
from .filters import PressConferenceFilterSet
from .models import PressConference, Section


def get_base_breadcrumb():
    return Breadcrumbs(
        items=[
            (_("Press Conferences"), reverse("pressconference:pressconference-home"))
        ],
        color="blue-500",
    )


# class PressConferenceListView(ListView, BreadcrumbView):
#     model = PressConference
#     template_name = "froide_pressconference/pressconference_list.html"
#     paginate_by = 10
#     ordering = ["-date"]

#     def get_breadcrumbs(self, context):
#         breadcrumbs = get_base_breadcrumb()
#         return breadcrumbs


class PressConferenceListView(BaseSearchView, BreadcrumbView):
    search_name = "pressconference"
    template_name = "froide_pressconference/pressconference_list.html"
    filterset = PressConferenceFilterSet
    document = PressConferenceDocument
    model = PressConference
    search_url_name = "pressconference:pressconference-list"
    default_sort = "-date"
    facet_config = {
        "date": {"type": "date_histogram", "interval": "year", "format": "yyyy"}
    }
    api = False

    def get_breadcrumbs(self, context):
        breadcrumbs = get_base_breadcrumb()
        return breadcrumbs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = context["facets"]
        date_facet_totals = list(
            PressConference.objects.all()
            .values_list("date__year")
            .annotate(year_count=Count("*"))
            .order_by("date__year")
        )

        facet_data_map = {
            d["key_as_string"]: d["doc_count"] for d in data["date"]["buckets"]
        }

        data = {
            "baseline": date_facet_totals,
            "facets": [
                {
                    "term": context["form"].cleaned_data.get("q", ""),
                    "date": [
                        {"key": str(year), "count": facet_data_map.get(str(year), 0)}
                        for year, _year_count in date_facet_totals
                    ],
                }
            ],
        }
        context["facet_data"] = data
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.api:
            return JsonResponse(context["facet_data"])
        return super().render_to_response(context, **response_kwargs)


class PressConferenceDetailView(DetailView, BreadcrumbView):
    model = PressConference
    slug_url_kwarg = "pc_slug"
    context_object_name = "press_conference"
    template_name = "froide_pressconference/pressconference_detail.html"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(
                "sections", "sections__speeches", "sections__speeches__speaker"
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = self.object.sections.all()
        self.attach_comments(context["sections"])
        return context

    def attach_comments(self, sections):
        if sections and not hasattr(sections[0], "comment_list"):
            Comment = get_model()
            ct = ContentType.objects.get_for_model(Section)
            section_ids = [s.id for s in sections]
            comments = (
                Comment.objects.filter(
                    content_type=ct,
                    object_pk__in=section_ids,
                )
                .order_by("-submit_date")
                .select_related("user")
            )
            comment_mapping = defaultdict(list)
            for c in comments:
                comment_mapping[c.object_pk].append(c)
            for section in sections:
                section.comment_list = comment_mapping[str(section.pk)]

    def get_breadcrumbs(self, context):
        breadcrumbs = get_base_breadcrumb()
        obj = self.get_object()

        breadcrumbs.items += [
            (
                obj.title,
                self.request.path,
            )
        ]

        return breadcrumbs
