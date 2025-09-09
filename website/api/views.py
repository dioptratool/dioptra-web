import json

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from website.models import CostLineItem, CostLineItemConfig
from .forms import CostLineItemCostTypeCategoryForm, CostLineItemNoteForm
from ..views.mixins import AnalysisPermissionRequiredMixin


@method_decorator(require_POST, name="dispatch")
class CostLineItemAddNoteView(AnalysisPermissionRequiredMixin, View):
    permission_required = "website.change_analysis"

    def dispatch(self, request, *args, **kwargs):
        self.cost_line_item = self._get_object(kwargs["pk"])
        if not self.cost_line_item:
            return HttpResponse(status=404)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        try:
            payload = json.loads(request.body.decode())
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Body must be valid JSON.")

        form = CostLineItemNoteForm(payload, instance=self.cost_line_item)
        if form.is_valid():
            obj = form.save()
            return JsonResponse({"id": obj.id, "note": obj.note})
        return JsonResponse(form.errors, status=400)

    @staticmethod
    def _get_object(pk):
        try:
            return CostLineItem.objects.select_related("analysis").get(pk=pk)
        except CostLineItem.DoesNotExist:
            return None


@method_decorator(require_POST, name="dispatch")
class CostLineItemUpdateCostTypeCategoryView(AnalysisPermissionRequiredMixin, View):
    permission_required = "website.change_analysis"

    def dispatch(self, request, *args, **kwargs):
        self.cost_line_item = self._get_object(kwargs["pk"])
        self.analysis = self.cost_line_item.analysis

        if not self.cost_line_item:
            return HttpResponse(status=404)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):

        try:
            payload = json.loads(request.body.decode())
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Body must be valid JSON.")

        form = CostLineItemCostTypeCategoryForm(payload)
        if not form.is_valid():
            return JsonResponse(form.errors, status=400)

        cost_type_id = form.cleaned_data["cost_type_id"]
        category_id = form.cleaned_data["category_id"]

        CostLineItemConfig.objects.filter(cost_line_item=self.cost_line_item).update(
            cost_type_id=cost_type_id,
            category_id=category_id,
        )

        analysis = self.cost_line_item.analysis
        analysis.ensure_cost_type_category_objects()
        analysis.cost_type_categories.filter(
            cost_type=cost_type_id,
            category=category_id,
        ).update(confirmed=False)

        return JsonResponse(
            {
                "id": self.cost_line_item.id,
                "cost_type_id": cost_type_id,
                "category_id": category_id,
            }
        )

    @staticmethod
    def _get_object(pk):
        try:
            return CostLineItem.objects.select_related("analysis").get(pk=pk)
        except CostLineItem.DoesNotExist:
            return None
