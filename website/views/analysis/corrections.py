"""
Edit panels for cost items and transactions (Feature 91, spec sections 3-5 and 8-10).

Selection transport: a bulk action POSTs the selected ids to ``CorrectionSelectionCreate``, which
stores them in the session under a token and answers with the panel URL to open; a Select All can
be thousands of ids and would not fit a query string. Single-row actions pass one id directly.

Two-phase save: a POST is previewed first. When the preview needs a confirmation (allocations
would be cleared) the panel shows that step and applies only on a confirming POST whose
fingerprint still matches a fresh preview.
"""

from __future__ import annotations

import uuid
from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _, gettext_lazy as _l
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin

from ombucore.admin import panel_commands
from ombucore.admin.buttons import CancelButton, SubmitButton
from ombucore.admin.views.base import FormView as PanelsFormView
from ombucore.admin.views.mixins import PanelUIMixin
from website.corrections import (
    COST_ITEM,
    TRANSACTION,
    CorrectionError,
    apply_cost_item_correction,
    apply_transaction_correction,
    field_labels,
    log_correction,
    plan_cost_item_correction,
    plan_transaction_correction,
)
from website.corrections.fields import cost_item_prefill, transaction_prefill
from website.corrections.labels import BUDGET_CUSTOM_FIELDS, STEP_LABELS, TRANSACTION_CUSTOM_FIELDS
from website.forms.corrections import CorrectionForm
from website.models import Analysis, Transaction
from website.views.mixins import AnalysisPermissionRequiredMixin

SELECTION_SESSION_KEY = "correction_selections"
SELECTION_LIMIT = 5  # Selections kept per session; older ones are dropped.
SELECTION_KINDS = {
    "transactions": "analysis-correct-transactions",
    "cost_items": "analysis-correct-cost-items",
}


def correction_urls(analysis: Analysis, step: str, cost_type=None) -> dict[str, str]:
    """
    Template context for a step page's edit entry points: the single-row panel URLs (the row
    appends its own id), the selection endpoint, and which kind of record a bulk selection is
    (section 4: transactions on a transaction-based analysis, cost items on a budget analysis).
    """
    query = f"?cost_type={cost_type.pk}" if cost_type is not None else ""
    return {
        "transaction_edit_url": reverse(
            "analysis-correct-transactions", kwargs={"pk": analysis.pk, "step": step}
        )
        + query,
        "cost_item_edit_url": reverse("analysis-correct-cost-items", kwargs={"pk": analysis.pk, "step": step})
        + query,
        "selection_url": reverse("analysis-correction-selection", kwargs={"pk": analysis.pk}),
        "unsaved_prompt_url": reverse("analysis-correction-unsaved-prompt", kwargs={"pk": analysis.pk}),
        "selection_kind": "transactions" if analysis.has_transactions() else "cost_items",
        "selection_step": step,
        "selection_cost_type": cost_type.pk if cost_type is not None else "",
    }


def _parse_ids(values) -> list[int]:
    ids = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                ids.append(int(part))
    return ids


class CorrectionSelectionCreate(AnalysisPermissionRequiredMixin, LoginRequiredMixin, View):
    """
    POST ``kind``, ``step``, ``ids`` (and optionally ``cost_type``) -> ``{"url": panel_url}``.

    For ``kind=transactions`` a selected cost-item row is sent as ``cost_line_item_ids`` and
    expanded here to every transaction it contains, including transactions that are collapsed or
    were never rendered (section 4).
    """

    permission_required = "website.change_analysis"
    http_method_names = ["post"]

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.analysis = get_object_or_404(Analysis, pk=kwargs["pk"])

    def post(self, request, *args, **kwargs):
        kind = request.POST.get("kind")
        step = request.POST.get("step")
        if kind not in SELECTION_KINDS or step not in STEP_LABELS:
            return HttpResponseBadRequest("Unknown selection kind or step.")
        try:
            ids = _parse_ids(request.POST.getlist("ids"))
            cost_line_item_ids = _parse_ids(request.POST.getlist("cost_line_item_ids"))
        except ValueError:
            return HttpResponseBadRequest("Selected ids must be integers.")
        if kind == "transactions" and cost_line_item_ids:
            contained = Transaction.objects.filter(
                analysis=self.analysis, cost_line_item_id__in=cost_line_item_ids
            ).values_list("id", flat=True)
            ids = list(dict.fromkeys([*ids, *contained]))
        if not ids:
            return HttpResponseBadRequest("Nothing selected.")

        token = uuid.uuid4().hex
        selections = dict(request.session.get(SELECTION_SESSION_KEY, {}))
        selections[token] = {"analysis": self.analysis.pk, "kind": kind, "ids": ids}
        for stale in list(selections)[:-SELECTION_LIMIT]:
            del selections[stale]
        request.session[SELECTION_SESSION_KEY] = selections

        query = {"selection": token}
        if request.POST.get("cost_type"):
            query["cost_type"] = request.POST["cost_type"]
        url = reverse(SELECTION_KINDS[kind], kwargs={"pk": self.analysis.pk, "step": step})
        return JsonResponse({"url": f"{url}?{urlencode(query)}", "count": len(ids)})


class AllocationChangesPromptPanel(
    AnalysisPermissionRequiredMixin, LoginRequiredMixin, PanelUIMixin, SingleObjectMixin, TemplateView
):
    """
    Shown before an edit action on Allocate while the allocation form has unsaved changes
    (spec section 3). A standard confirmation panel: the page script acts on the resolved choice
    ("save" saves the form first and reopens the edit panel; "discard" opens it straight away).
    """

    model = Analysis
    permission_required = "website.change_analysis"
    template_name = "panel-form-correction-unsaved.html"
    # As the other confirmation panels: the question is the supertitle (the h1 is truncated at 40).
    supertitle = _l("Save or discard your allocation changes before editing")
    title = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.object = self.get_object()
        self.analysis = self.object


class CorrectionPanelBase(
    AnalysisPermissionRequiredMixin, LoginRequiredMixin, PanelsFormView, SingleObjectMixin
):
    model = Analysis
    form_class = CorrectionForm
    template_name = "panel-form-correction.html"
    permission_required = "website.change_analysis"
    help_text = ""

    # Subclasses.
    selection_kind = None
    single_param = None
    record_kind = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.object = self.get_object()
        self.analysis = self.object
        self.step = kwargs["step"]
        self.cost_type_pk = request.GET.get("cost_type")
        self.selection_ids = []
        self.records = []
        self.patch = None
        self.result = None

    def dispatch(self, request, *args, **kwargs):
        # Resolve the selection only for a permitted user, so an anonymous request is sent to log
        # in and a forbidden one gets 403 rather than a 404 about the selection.
        if not self.has_permission():
            return self.handle_no_permission()
        if self.step not in STEP_LABELS:
            raise Http404(_("Unknown step."))
        self.selection_ids = self._resolve_selection(request)
        self.records = self.load_records()
        if not self.records:
            raise Http404(_("Nothing to edit."))
        return super().dispatch(request, *args, **kwargs)

    def _resolve_selection(self, request) -> list[int]:
        token = request.GET.get("selection")
        if token:
            entry = request.session.get(SELECTION_SESSION_KEY, {}).get(token)
            if (
                not entry
                or entry.get("analysis") != self.analysis.pk
                or entry.get("kind") != self.selection_kind
            ):
                raise Http404(_("This selection has expired. Select the rows again."))
            return list(entry["ids"])
        single = request.GET.get(self.single_param)
        if single:
            try:
                return [int(single)]
            except ValueError:
                raise Http404(_("Invalid id."))
        raise Http404(_("Nothing selected."))

    # --- subclass hooks -----------------------------------------------------------------------

    def load_records(self) -> list:
        raise NotImplementedError

    @property
    def custom_family(self) -> str:
        raise NotImplementedError

    @property
    def amount_editable(self) -> bool:
        return True

    @property
    def log_record_kind(self) -> str:
        return self.record_kind

    def initial_values(self) -> dict:
        raise NotImplementedError

    def build_plan(self, patch):
        raise NotImplementedError

    def apply_plan(self, plan):
        raise NotImplementedError

    @property
    def is_bulk(self) -> bool:
        return len(self.records) > 1

    # --- form ---------------------------------------------------------------------------------

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "analysis": self.analysis,
                "record_kind": self.record_kind,
                "step": self.step,
                "custom_family": self.custom_family,
                "amount_editable": self.amount_editable,
                "initial_values": self.initial_values(),
            }
        )
        return kwargs

    @property
    def labels(self):
        return field_labels(self.record_kind, self.custom_family)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if request.POST.get("stage") == "edit":
            # "Back" from the confirmation step: show the form again with the entered values.
            return self.render_to_response(self.get_context_data(form=form))
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        self.patch = form.to_patch()
        try:
            plan = self.build_plan(self.patch)
        except CorrectionError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)

        submitted = self.request.POST.get("confirm_fingerprint")
        if submitted is None:
            if plan.needs_confirmation:
                return self.render_confirmation(form, plan)
        elif submitted != plan.fingerprint():
            return self.render_confirmation(form, plan, stale=True)

        try:
            self.result = self.apply_plan(plan)
        except CorrectionError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        log_correction(
            self.analysis, self.result, self.step, self.log_record_kind, self.labels, self.request.user
        )
        return super().form_valid(form)

    def render_confirmation(self, form, plan, stale=False):
        hidden_fields = [
            (form.add_prefix(name), form.data.get(form.add_prefix(name), ""))
            for name in form.fields
            if not form.fields[name].disabled
        ]
        context = self.get_context_data(
            form=form,
            stage="confirm",
            stale=stale,
            needs_allocation_warning=plan.needs_allocation_warning,
            hidden_fields=hidden_fields,
            confirm_fingerprint=plan.fingerprint(),
            buttons=self.confirmation_buttons(plan),
        )
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        kwargs.setdefault("stage", "edit")
        kwargs.setdefault("buttons", self.buttons)
        context = super().get_context_data(**kwargs)
        context["analysis"] = self.analysis
        context["record_count"] = len(self.records)
        return context

    @property
    def buttons(self):
        return [SubmitButton(text=_l("Save")), CancelButton()]

    def confirmation_buttons(self, plan):
        # Only a stale preview can reach this step without the warning still applying.
        text = _("Continue and clear allocations") if plan.needs_allocation_warning else _("Continue")
        return [
            SubmitButton(
                text=text,
                disable_when_form_unchanged=False,
                attrs={"name": "stage", "value": "confirm"},
            ),
            SubmitButton(
                text=_("Back"),
                style="cancel",
                disable_when_form_unchanged=False,
                attrs={"name": "stage", "value": "edit"},
            ),
            CancelButton(),
        ]

    # --- outcome ------------------------------------------------------------------------------

    def get_success_commands(self):
        if (
            self.step == "categorize"
            and self.cost_type_pk
            and not self.analysis.cost_type_categories.filter(cost_type_id=self.cost_type_pk).exists()
        ):
            # The table being viewed emptied: go to the destination Cost Type's page (section 10).
            return [panel_commands.Resolve({"redirect_to": self.destination_url()})]
        return [panel_commands.Resolve({"operation": "saved"})]

    def destination_url(self) -> str:
        cost_type = self.patch.cost_type if self.patch else None
        if cost_type and self.analysis.cost_type_categories.filter(cost_type=cost_type).exists():
            return reverse(
                "analysis-categorize-cost_type",
                kwargs={"pk": self.analysis.pk, "cost_type_pk": cost_type.pk},
            )
        return reverse("analysis-categorize", kwargs={"pk": self.analysis.pk})


class TransactionCorrectionPanel(CorrectionPanelBase):
    selection_kind = "transactions"
    single_param = "transaction_id"
    record_kind = TRANSACTION

    def load_records(self):
        return list(
            Transaction.objects.filter(
                analysis=self.analysis,
                id__in=self.selection_ids,
                cost_line_item__isnull=False,
                cost_line_item__is_special_lump_sum=False,
                cost_line_item__config__analysis_cost_type__isnull=True,
            )
            .select_related("cost_line_item", "cost_line_item__config")
            .order_by("id")
        )

    @property
    def custom_family(self):
        return TRANSACTION_CUSTOM_FIELDS

    def get_supertitle(self):
        return _("Selected Transactions") if self.is_bulk else _("Transaction")

    def get_title(self):
        return _("Edit Transactions") if self.is_bulk else _("Edit Transaction")

    def initial_values(self):
        return transaction_prefill(self.load_records())

    def build_plan(self, patch):
        return plan_transaction_correction(self.analysis, self.selection_ids, patch)

    def apply_plan(self, plan):
        return apply_transaction_correction(plan)

    def get_success_message(self, cleaned_data):
        count = self.result.record_count if self.result else len(self.records)
        return _("{count} transactions updated").format(count=count)


class CostItemCorrectionPanel(CorrectionPanelBase):
    """
    Edit Cost Item. On a budget analysis the cost item is edited directly; on a transaction-based
    analysis the panel is a scoped batch edit of every transaction that makes up the item, Amount
    is derived and shown disabled, and the custom fields are the transaction family (section 7).
    """

    selection_kind = "cost_items"
    single_param = "cost_line_item_id"
    record_kind = COST_ITEM

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.transaction_based = self.analysis.has_transactions()

    def load_records(self):
        return list(
            self.analysis.cost_line_items.cost_type_category_items()
            .filter(id__in=self.selection_ids)
            .select_related("config")
            .order_by("id")
        )

    def scoped_transactions(self):
        return list(
            Transaction.objects.filter(cost_line_item__in=self.records)
            .select_related("cost_line_item", "cost_line_item__config")
            .order_by("id")
        )

    @property
    def custom_family(self):
        return TRANSACTION_CUSTOM_FIELDS if self.transaction_based else BUDGET_CUSTOM_FIELDS

    @property
    def amount_editable(self):
        return not self.transaction_based

    @property
    def log_record_kind(self):
        return TRANSACTION if self.transaction_based else COST_ITEM

    def get_supertitle(self):
        return _("Selected Cost Items") if self.is_bulk else _("Cost Item")

    def get_title(self):
        return _("Edit Cost Items") if self.is_bulk else _("Edit Cost Item")

    def initial_values(self):
        records = self.load_records()
        if self.transaction_based:
            return cost_item_prefill(records, transactions=self.scoped_transactions())
        return cost_item_prefill(records)

    def build_plan(self, patch):
        if self.transaction_based:
            transaction_ids = [t.id for t in self.scoped_transactions()]
            return plan_transaction_correction(self.analysis, transaction_ids, patch)
        return plan_cost_item_correction(self.analysis, self.selection_ids, patch)

    def apply_plan(self, plan):
        if self.transaction_based:
            return apply_transaction_correction(plan)
        return apply_cost_item_correction(plan)

    def get_success_message(self, cleaned_data):
        return _("{count} cost items updated").format(count=len(self.records))
