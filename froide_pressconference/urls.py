from django.urls import path
from django.utils.translation import pgettext_lazy

from .views import PressConferenceDetailView, PressConferenceListView

urlpatterns = [
    path(
        "",
        PressConferenceListView.as_view(),
        name="pressconference-home",
    ),
    path(
        "facet.json",
        PressConferenceListView.as_view(api=True),
        name="pressconference-facet",
    ),
    path(
        pgettext_lazy("url part", "search/"),
        PressConferenceListView.as_view(),
        name="pressconference-list",
    ),
    path(
        pgettext_lazy("url part", "<slug:pc_slug>/"),
        PressConferenceDetailView.as_view(),
        name="pressconference-detail",
    ),
]
