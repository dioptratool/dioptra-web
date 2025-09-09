from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django_filters.views import FilterView

from ombucore.admin.views import FilterMixin
from website.filters import AnalysisFilterSet
from website.models import Analysis, Settings

User = get_user_model()


class DashboardView(LoginRequiredMixin, FilterMixin, FilterView):
    model = Analysis
    template_name = "dashboard.html"

    slug_field = "id"
    slug_url_kwarg = "id"
    filterset_class = AnalysisFilterSet

    def get_paginate_by(self, queryset):
        dioptra_settings = Settings.objects.first()
        return dioptra_settings.paginate_by

    def get_queryset(self):
        qs = self.request.user.all_analyses()
        filtered_list = AnalysisFilterSet(self.request.GET, queryset=qs)

        return filtered_list.qs.select_related(
            "country",
            "owner",
        ).prefetch_related(
            "unfiltered_cost_line_items",
            "interventioninstance_set",
            "interventioninstance_set__intervention",
        )
