from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from froide.helper.admin_utils import (
    ForeignKeyFilter,
    make_choose_object_action,
)

from .models import (
    PressConference,
    PressConferenceCategory,
    Section,
    Speaker,
    Speech,
    Topic,
)


@admin.register(PressConferenceCategory)
class PressConferenceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ("host",)


@admin.register(PressConference)
class PressConferenceAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "category")
    list_filter = ("category",)
    search_fields = ("title", "description")
    date_hierarchy = "date"
    prepopulated_fields = {"slug": ("title",)}
    actions = ["parse_press_conference"]

    @admin.action(description=_("Parse press conference"))
    def parse_press_conference(self, request, queryset):
        from .tasks import parse_pressconference_task

        for pc in queryset:
            parse_pressconference_task.delay(pc.id)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


def execute_replace_speakers(admin, request, queryset, action_obj):
    Speech.objects.filter(speaker__in=queryset).update(speaker=action_obj)


@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "organization", "publicbody", "count_speeches")
    search_fields = ("name", "organization", "title")
    list_filter = ("organization", ("publicbody", ForeignKeyFilter))
    raw_id_fields = ("publicbody",)

    actions = ["replace_speakers"]

    replace_speakers = make_choose_object_action(
        Speaker, execute_replace_speakers, _("Replace speakers with...")
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("publicbody")
            .annotate(speech_count=Count("speeches"))
        )

    @admin.display(description=_("speech count"), ordering="speech_count")
    def count_speeches(self, obj):
        return obj.speech_count


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("press_conference", "order")
    list_filter = ("press_conference",)
    search_fields = ("press_conference__title",)
    ordering = ("press_conference", "order")
    filter_horizontal = ("topics",)
    raw_id_fields = ("press_conference", "foirequests")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("press_conference")


@admin.register(Speech)
class SpeechAdmin(admin.ModelAdmin):
    list_display = ("section", "kind", "order", "speaker")
    list_filter = ("kind", ("section__press_conference", ForeignKeyFilter))
    search_fields = ("text", "speaker__name")
    raw_id_fields = ("speaker", "section")
    ordering = ("section", "order")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("section", "section__press_conference", "speaker")
        )
