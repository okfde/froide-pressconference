from django import forms
from django.utils import timezone

from .models import Flag, FlagKind


class FlagForm(forms.Form):
    kind = forms.ChoiceField(choices=FlagKind.choices)

    def save(self, user, section):
        Flag.objects.update_or_create(
            section=section,
            user=user,
            kind=self.cleaned_data["kind"],
            defaults={"timestamp": timezone.now()},
        )

    def delete(self, user, section):
        Flag.objects.filter(
            user=user, section=section, kind=self.cleaned_data["kind"]
        ).delete()
