from django.contrib import admin

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


@admin.register(PressConference)
class PressConferenceAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "category")
    list_filter = ("category",)
    search_fields = ("title", "description")
    date_hierarchy = "date"
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "organization", "publicbody")
    search_fields = ("name", "organization", "title")
    list_filter = ("organization", "publicbody")
    raw_id_fields = ("publicbody",)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("press_conference", "order")
    list_filter = ("press_conference",)
    search_fields = ("press_conference__title",)
    ordering = ("press_conference", "order")
    filter_horizontal = ("topics",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("press_conference")


@admin.register(Speech)
class SpeechAdmin(admin.ModelAdmin):
    list_display = ("section", "kind", "order", "speaker")
    list_filter = ("kind", "section__press_conference")
    search_fields = ("text", "speaker__name")
    raw_id_fields = ("speaker", "section")
    ordering = ("section", "order")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("section", "section__press_conference", "speaker")
        )
