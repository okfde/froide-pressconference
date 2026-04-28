from urllib.parse import quote, urlencode

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join, mark_safe
from django.utils.translation import gettext_lazy as _

from cms.models.pluginmodel import CMSPlugin

from froide.foirequest.models import FoiRequest
from froide.publicbody.models import PublicBody


class PressConferenceCategory(models.Model):
    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), unique=True)
    host = models.ForeignKey(
        PublicBody, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = _("Press Conference Category")
        verbose_name_plural = _("Press Conference Categories")

    def __str__(self):
        return self.name


class PressConference(models.Model):
    category = models.ForeignKey(
        PressConferenceCategory,
        verbose_name=_("category"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField(_("title"), max_length=255, blank=True)
    slug = models.SlugField(_("slug"), blank=True)
    description = models.TextField(_("description"), blank=True)
    source_url = models.URLField(_("source URL"), blank=True)
    source_file = models.FileField(blank=True, upload_to="pressconferences")
    date = models.DateTimeField(_("date"), default=timezone.now)

    class Meta:
        verbose_name = _("press conference")
        verbose_name_plural = _("press conferences")
        ordering = ["-date"]
        get_latest_by = "date"
        constraints = [
            models.UniqueConstraint(
                name="pressconference_unqique_slug",
                fields=["slug"],
                condition=~models.Q(slug=""),
            )
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        if not self.slug:
            return ""
        return reverse(
            "pressconference:pressconference-detail", kwargs={"pc_slug": self.slug}
        )

    def description_as_li(self):
        return format_html_join(
            "\n", "<li>{}</li>", ((line,) for line in self.description.splitlines())
        )


class Topic(models.Model):
    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), unique=True)
    description = models.TextField(_("description"), blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("topic")
        verbose_name_plural = _("topics")


class Speaker(models.Model):
    name = models.CharField(_("name"), max_length=255)
    title = models.CharField(_("title"), max_length=255, blank=True)
    organization = models.CharField(_("organization"), max_length=255, blank=True)
    publicbody = models.ForeignKey(
        PublicBody,
        verbose_name=_("public body"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("speaker")
        verbose_name_plural = _("speakers")

    def __str__(self):
        return f"{self.title + ' ' if self.title else ''}{self.name}"

    def display_name(self):
        parts = []
        if self.title:
            parts.append(format_html("{} ", self.title))
        parts.append(format_html("{}", self.name))
        return mark_safe("".join(parts))


class Section(models.Model):
    press_conference = models.ForeignKey(
        PressConference,
        verbose_name=_("press conference"),
        on_delete=models.CASCADE,
        related_name="sections",
    )
    order = models.PositiveIntegerField(_("order"))
    topics = models.ManyToManyField(Topic, blank=True, verbose_name=_("topics"))
    foirequests = models.ManyToManyField(
        FoiRequest, blank=True, verbose_name=_("related FOI requests")
    )

    class Meta:
        verbose_name = _("section")
        verbose_name_plural = _("sections")
        ordering = ["order"]

    def __str__(self):
        return _("Section %(order)s in %(press_conference)s") % {
            "order": self.order,
            "press_conference": self.press_conference,
        }

    def get_absolute_url(self):
        return f"{self.press_conference.get_absolute_url()}#section-{self.order}"


class FlagKind(models.TextChoices):
    UNANSWERED = "unanswered", _("unanswered")


class Flag(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(choices=FlagKind.choices)

    class Meta:
        verbose_name = _("Flag")
        verbose_name_plural = _("Flag")


class SpeechKind(models.TextChoices):
    SIDENOTE = "sidenote", _("Sidenote")
    QUESTION = "question", _("Question")
    SPEECH = "speech", _("Speech")
    FOLLOWUP = "followup", _("Follow-up")
    INTERJECTION = "interjection", _("Interjection")


class Speech(models.Model):
    section = models.ForeignKey(
        Section,
        verbose_name=_("section"),
        on_delete=models.CASCADE,
        related_name="speeches",
    )
    kind = models.CharField(_("kind"), max_length=50, choices=SpeechKind.choices)
    order = models.PositiveIntegerField(_("order"))
    speaker = models.ForeignKey(
        Speaker,
        verbose_name=_("speaker"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="speeches",
    )
    label = models.TextField(_("label"), blank=True)
    text = models.TextField(_("text"), blank=True)

    class Meta:
        verbose_name = _("speech")
        verbose_name_plural = _("speeches")
        ordering = ["order", "id"]
        permissions = (("can_use_presslaw", _("Can use press law")),)

    def __str__(self):
        return self.text[:50]

    @property
    def is_sidenote(self):
        return self.kind == SpeechKind.SIDENOTE

    @property
    def is_question(self):
        return self.kind in (SpeechKind.QUESTION, SpeechKind.FOLLOWUP)

    def make_request_url(self, law_type=""):
        if self.speaker and self.speaker.publicbody_id:
            path = reverse(
                "foirequest-make_request",
                kwargs={"publicbody_ids": self.speaker.publicbody_id},
            )
            date = date_format(self.section.press_conference.date)
            query = {
                "ref": f"pressconference:{self.section.pk}@{self.section.press_conference.pk}",
                "body": _(
                    "In a press conference on {date}, {speaker} said:\n\n“{text}”\n\n[…write request here…]"
                ).format(date=date, speaker=self.speaker.name, text=self.text),
            }
            if law_type:
                query["law_type"] = law_type
            query = urlencode(query, quote_via=quote)
            return f"{path}?{query}"
        return ""

    def make_press_request_url(self):
        return self.make_request_url(law_type="Presserecht")


class PressConferenceFacetsCMSPlugin(CMSPlugin):
    """
    CMS Plugin for displaying search terms
    """

    terms = models.CharField(max_length=255)
    interval = models.CharField(
        max_length=50,
        default="year",
        choices=(
            ("year", _("Year")),
            (
                "month",
                _("Month"),
            ),
            ("week", _("Week")),
        ),
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return _("Facet graph for: %s") % self.terms

    def get_terms(self):
        return [t.strip() for t in self.terms.split(",")]

    def get_terms_joined(self):
        return ",".join(self.get_terms())
