from django.utils.translation import gettext_lazy as _

from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from froide.helper.search.queryset import SearchQuerySetWrapper

from .documents import PressConferenceDocument
from .filters import PressConferenceFilterSet
from .models import PressConference, PressConferenceFacetsCMSPlugin
from .views import PressConferenceListView, get_facet_data


@plugin_pool.register_plugin
class PressConferenceListPlugin(CMSPluginBase):
    module = _("Press Conference")
    name = _("Press Conference List")
    cache = True
    render_template = "froide_pressconference/plugins/pressconference_list.html"

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        context["plugin"] = instance
        context["object_list"] = PressConference.objects.all()[:5]
        return context


@plugin_pool.register_plugin
class PressConferenceFacetGraphPlugin(CMSPluginBase):
    module = _("Press Conference")
    name = _("Press Conference Facet Graph")
    cache = True
    model = PressConferenceFacetsCMSPlugin
    render_template = "froide_pressconference/plugins/pressconference_facetgraph.html"

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        terms = instance.get_terms()
        context["facet_data"] = get_facet_data(
            terms, [self.get_facet(term) for term in terms]
        )
        context["facet_data_id"] = f"facet-data-{instance.id}"
        context["terms"] = instance.get_terms_joined()
        context["show_input"] = True
        return context

    def get_facet(self, term):
        s = PressConferenceDocument.search()
        sqs = SearchQuerySetWrapper(s, PressConference)

        filtered = PressConferenceFilterSet(
            {"q": term},
            view=PressConferenceListView,
            queryset=sqs,
        )
        sqs = filtered.qs
        data = sqs.get_facet_data()
        return data
