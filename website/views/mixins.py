from collections import defaultdict
from decimal import Decimal, DecimalException

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic.base import ContextMixin, TemplateView
from django_filters import filters

from ombucore.admin.filterset import FilterSet
from ombucore.admin.views.base import search_field_for_model
from website.models import Analysis, CostLineItem, Settings
from website.models.cost_line_item import CostLineItemInterventionAllocation
from website.workflows import AnalysisWorkflow


class AnalysisPermissionRequiredMixin(PermissionRequiredMixin):
    def has_permission(self):
        perms = self.get_permission_required()
        return self.request.user.has_perms(perms, self.analysis)


class AnalysisStepMixin:
    step_name: str  # The name of the step in the workflow.
    title: str
    help_text: str
    model = Analysis

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.dioptra_settings = Settings.objects.first()
        self.setup_step()

    def setup_step(self):
        self.object = self.get_object()
        self.analysis = self.object
        self.workflow = AnalysisWorkflow(self.analysis)
        self.step = self.workflow.get_step(self.step_name)
        self.parent_step = self.workflow.get_step(self.step_name)

    def dispatch(self, request, *args, **kwargs):
        if not self.step or not self.step.dependencies_met:
            return redirect(reverse("analysis", kwargs={"pk": self.analysis.pk}))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.title:
            context["title"] = self.title
        if self.help_text:
            context["help_text"] = self.help_text

        context["dioptra_settings"] = self.dioptra_settings
        context["analysis"] = getattr(self, "analysis", None)
        context["workflow"] = self.workflow
        context["step"] = self.step

        return context


class AnalysisObjectMixin(ContextMixin):
    context_object_name = None

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = Analysis.objects
        pk = self.kwargs.get("pk")
        if pk is not None:
            queryset = queryset.filter(pk=pk)
            queryset = queryset.prefetch_related(
                "cost_type_categories",
                "interventioninstance_set",
                "interventioninstance_set__intervention",
                "unfiltered_cost_line_items",
                "unfiltered_cost_line_items__config",
                "unfiltered_cost_line_items__config__allocations",
            )

        if pk is None:
            raise AttributeError(
                f"Generic detail view {self.__class__.__name__} must be called with "
                f"either an object pk or a slug in the URLconf."
            )

        try:
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            verbose_name = queryset.model._meta.verbose_name

            raise Http404(_("No {verbose_name} found matching the query").format(verbose_name=verbose_name))
        return obj

    def get_context_object_name(self, obj):
        if self.context_object_name:
            return self.context_object_name
        elif isinstance(obj, models.Model):
            return obj._meta.model_name
        else:
            return None


class AnalysisStepDetailMixin(AnalysisStepMixin, AnalysisObjectMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class AnalysisStepFiltersetMixin(AnalysisStepMixin, AnalysisObjectMixin, TemplateView):
    def get_filterset_kwargs(self, filterset_class):
        """
        Pass Analysis data to `AnalysisStepFilterSet` in order to filter CostLineItems
        """
        kwargs = super().get_filterset_kwargs(filterset_class)
        kwargs["analysis"] = self.analysis
        return kwargs

    def get_filterset_class(self):
        if self.filterset_class:
            return self.filterset_class
        elif self.model:
            meta_dict = {"model": self.model}
            filterset_class_dict = {}
            search_field = search_field_for_model(self.model)
            if search_field:
                meta_dict["fields"] = ["search"]
                filterset_class_dict["search"] = filters.CharFilter(
                    field_name=search_field,
                    lookup_expr="icontains",
                    help_text="",
                )
            filterset_class_dict["Meta"] = type("Meta", (object,), meta_dict)
            filterset_class = type(
                f"{self.model._meta.object_name}FilterSet",
                (FilterSet,),
                filterset_class_dict,
            )
            return filterset_class
        else:
            raise ImproperlyConfigured(
                f"'{self.__class__.__name__}' must define 'filterset_class' or 'model'"
            )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)
        self.object_list = self.modify_queryset(self.filterset.qs)
        context = self.get_context_data(
            object=self.object, filter=self.filterset, object_list=self.object_list
        )
        return self.render_to_response(context)

    def modify_queryset(self, queryset):
        return queryset


class AllocateMixin:
    def _get_cost_line_item_ids_and_allocations_from_post(self, request):
        data = {}
        for input_name, allocation in request.POST.items():
            if input_name.startswith("cost_line_item_allocation_"):
                cost_line_item_id, intervention_id = input_name.replace(
                    "cost_line_item_allocation_", ""
                ).split("_")
                cost_line_item_id = int(cost_line_item_id)
                intervention_id = int(intervention_id)
                allocation = allocation.strip()

                if cost_line_item_id not in data:
                    data[cost_line_item_id] = {}

                if allocation != "":
                    data[cost_line_item_id][intervention_id] = allocation
                elif allocation == "":
                    data[cost_line_item_id][intervention_id] = None
        return data

    def _validate_data(self, data):
        errors = defaultdict(dict)
        for cost_line_item_id, intervention_allocations in data.items():
            allocation_total = Decimal(0)

            for intervention_id, allocation in intervention_allocations.items():
                if allocation is not None:
                    try:
                        allocation = allocation.strip().replace("%", "")
                        allocation = Decimal(allocation)
                        data[cost_line_item_id][intervention_id] = allocation
                        allocation_total += allocation
                        if allocation < 0 or allocation > 100:
                            errors[cost_line_item_id][intervention_id] = _("Invalid allocation (0-100)")
                    except DecimalException:
                        errors[cost_line_item_id][intervention_id] = _("Not a number")

                if allocation_total < 0 or allocation_total > 100:
                    errors[cost_line_item_id]["all"] = _(
                        "Invalid allocation total. Cost line item Allocation must be between 0 and 100"
                    )
        return data, errors

    def _clear_fields_needing_help(self, errors):
        for cost_line_item_id, intervention_allocation_error_messages in errors.items():
            for (
                intervention_id,
                error_message,
            ) in intervention_allocation_error_messages.items():
                if error_message == "Not a number":
                    c = CostLineItem.objects.get(id=cost_line_item_id)
                    CostLineItemInterventionAllocation.objects.filter(cli_config=c.config).delete()


class PostActionHandlerMixin:
    def post(self, request, *args, **kwargs):
        if "action" in request.POST and request.POST["action"] in self.actions:
            handler = f"handle_{request.POST['action']}"
            if hasattr(self, handler):
                response = getattr(self, handler)(request, *args, **kwargs)
                if response:
                    return response
        query = f"?{request.GET.urlencode()}" if request.GET else ""
        return redirect(self.request.path + query)
