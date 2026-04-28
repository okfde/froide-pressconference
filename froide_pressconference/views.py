from collections import defaultdict
from dataclasses import dataclass

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.db.models.functions import TruncMonth, TruncWeek, TruncYear
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import DetailView

from django_comments import get_model

from froide.helper.breadcrumbs import Breadcrumbs, BreadcrumbView
from froide.helper.search.views import BaseSearchView
from froide.helper.utils import is_ajax

from .documents import PressConferenceDocument
from .filters import PressConferenceFilterSet
from .forms import FlagForm
from .models import Flag, FlagKind, PressConference, Section


def get_base_breadcrumb():
    return Breadcrumbs(
        items=[
            (_("Press Conferences"), reverse("pressconference:pressconference-home"))
        ],
        color="blue-500",
    )


def get_facet_data(
    terms: list[str], facet_list, interval="year", start_date=None, end_date=None
):
    annotation_func = TruncYear
    if interval == "month":
        annotation_func = TruncMonth
    elif interval == "week":
        annotation_func = TruncWeek

    base_qs = PressConference.objects.exclude(slug="")
    if start_date:
        base_qs = base_qs.filter(date__gte=start_date)
    if end_date:
        base_qs = base_qs.filter(date__lte=end_date)

    date_facet_totals = list(
        base_qs.annotate(date_trunc=annotation_func("date"))
        .values_list("date_trunc")
        .annotate(year_count=Count("*"))
        .order_by("date_trunc")
    )
    date_facet_totals = [
        (date_trunc.strftime("%Y-%m-%d"), year_count)
        for date_trunc, year_count in date_facet_totals
    ]

    facet_map_list = [
        {d["key_as_string"]: d["doc_count"] for d in facet["date"]["buckets"]}
        for facet in facet_list
    ]

    return {
        "baseline": date_facet_totals,
        "facets": [
            {
                "term": term,
                "date": [
                    {"key": date_trunc, "count": facet_map.get(date_trunc, 0)}
                    for date_trunc, _year_count in date_facet_totals
                ],
            }
            for term, facet_map in zip(terms, facet_map_list, strict=True)
        ],
    }


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
        facets = context["facets"]
        cleaned_data = context["form"].cleaned_data
        context["facet_interval"] = cleaned_data.get("facet_interval", "year") or "year"
        context["facet_data"] = get_facet_data(
            [cleaned_data.get("q", "")],
            [facets],
            interval=context["facet_interval"],
            start_date=cleaned_data.get("date_after"),
            end_date=cleaned_data.get("date_before"),
        )
        context["facet_data_id"] = "facet-data"
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.api:
            return JsonResponse(context["facet_data"])
        return super().render_to_response(context, **response_kwargs)


@dataclass
class FlagValue:
    kind: str
    count: int = 0
    can_delete: bool = False

    def get_kind_display(self):
        return dict(FlagKind.choices)[self.kind]


def attach_flags(request, sections):
    if sections and not hasattr(sections[0], "flag_dict"):
        section_ids = [s.id for s in sections]
        user_flags = defaultdict(set)
        if request.user.is_authenticated:
            flag_pairs = Flag.objects.filter(
                section__in=section_ids, user=request.user
            ).values_list("section_id", "kind")
            for key, value in flag_pairs:
                user_flags[key].add(value)

        flags = (
            Flag.objects.filter(section__in=section_ids)
            .values("section_id", "kind")
            .annotate(count=Count("*"))
            .order_by("section_id", "kind", "-count")
        )

        flag_mapping = {}
        for section in sections:
            flag_mapping[section.id] = {k: FlagValue(kind=k) for k in FlagKind.values}
        for fl in flags:
            can_delete = fl["kind"] in user_flags.get(fl["section_id"], set())
            flag_mapping[fl["section_id"]][fl["kind"]] = FlagValue(
                kind=fl["kind"], count=fl["count"], can_delete=can_delete
            )
        for section in sections:
            section.flag_dict = flag_mapping[section.id]


class PressConferenceDetailView(DetailView, BreadcrumbView):
    model = PressConference
    slug_url_kwarg = "pc_slug"
    context_object_name = "press_conference"
    template_name = "froide_pressconference/pressconference_detail.html"

    def get_queryset(self):
        return super().get_queryset().exclude(slug="")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = self.object.sections.all().prefetch_related(
            "foirequests",
            "speeches",
            "speeches__speaker",
            "speeches__speaker__publicbody",
        )
        self.attach_comments(context["sections"])
        self.attach_flags(context["sections"])
        return context

    def attach_flags(self, sections):
        attach_flags(self.request, sections)

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


@login_required
@require_POST
def add_flag(request, section_id):
    section = get_object_or_404(Section, id=int(section_id))
    form = FlagForm(request.POST)
    if form.is_valid():
        form.save(request.user, section)
    if is_ajax(request):
        attach_flags(request, [section])
        return render(
            request, "froide_pressconference/includes/_flag.html", {"section": section}
        )
    return redirect(section)


@login_required
@require_POST
def remove_flag(request, section_id):
    section = get_object_or_404(Section, id=int(section_id))
    form = FlagForm(request.POST)
    if form.is_valid():
        form.delete(request.user, section)
    if is_ajax(request):
        attach_flags(request, [section])
        return render(
            request, "froide_pressconference/includes/_flag.html", {"section": section}
        )
    return redirect(section)
