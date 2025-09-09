import logging

from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext as _, gettext_lazy as _l
from django.views.generic import DetailView

from website.app_log import loggers as app_loggers
from website.data_loading.transactions import get_transactions_data_store_count
from website.models import Settings
from website.views.mixins import (
    AnalysisPermissionRequiredMixin,
    AnalysisStepMixin,
    PostActionHandlerMixin,
)


class LoadData(
    AnalysisPermissionRequiredMixin,
    PostActionHandlerMixin,
    AnalysisStepMixin,
    DetailView,
):
    step_name = "load-data"
    title = _l("Load cost data")
    help_text = _("")
    template_name = "analysis/load-data.html"
    actions = [
        "import_data",
        "upload_budget",
        "upload_transactions",
        "reset_data",
        "transaction_resync",
    ]
    permission_required = "website.change_analysis"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = Settings.objects.first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["import_transaction_limit"] = settings.IMPORTED_TRANSACTION_LIMIT
        context["transaction_country_filter"] = self.settings.transaction_country_filter
        analysis = self.analysis

        if not self.step.is_complete:
            context["transactions_count"] = None
            analysis_country_code = None
            special_country_codes = None
            if self.settings.transaction_country_filter:
                analysis_country_code = [analysis.country.code]
                special_country_codes = analysis.get_special_countries_values("code")
            try:
                # First get count of all Standard transactions
                context["transactions_count"] = get_transactions_data_store_count(
                    analysis.grants,
                    analysis.start_date,
                    analysis.end_date,
                    country_codes=analysis_country_code,
                )
                # Then get count of all transactions corresponding only to special countries, if any exist
                if special_country_codes:
                    context["special_count"] = get_transactions_data_store_count(
                        analysis.grants,
                        analysis.start_date,
                        analysis.end_date,
                        country_codes=special_country_codes,
                    )
            except Exception as e:
                logging.exception(e)
                context["import_errors"] = [_("There was an error querying transactions.")]
        return context

    def handle_import_data(self, request, *args, **kwargs):
        succeeded, result = self.step.load_transactions(
            filter_by_country=self.settings.transaction_country_filter,
            from_datastore=True,
        )
        if (not succeeded) and ("errors" in result):
            context = self.get_context_data(object=self.object)
            context["import_errors"] = result["errors"]
            return self.render_to_response(context)
        else:
            try:
                t_count = get_transactions_data_store_count(
                    self.analysis.grants,
                    self.analysis.start_date,
                    self.analysis.end_date,
                )
            except Exception as e:
                logging.exception(e)
                t_count = "n/a"
            app_loggers.log_analysis_transactions_imported(
                self.analysis, t_count, result.get("imported_count"), self.request.user
            )
            messages.success(
                request,
                _("%(imported_count)s transactions imported successfully.") % result,
            )

        return None  # Normal routing.

    def handle_upload_budget(self, request, *args, **kwargs):
        f = request.FILES.get("file", None)
        errors = []
        if not f:
            errors.append(_("Please select a file."))

        succeeded, result = self.step.load_cost_line_items_from_file(f)
        if (not succeeded) and ("errors" in result):
            errors += result["errors"]

        if len(errors) > 0:
            context = self.get_context_data(object=self.object)
            context["upload_budget_errors"] = errors
            return self.render_to_response(context)
        else:
            app_loggers.log_analysis_budget_uploaded(
                self.analysis, result.get("imported_count"), self.request.user
            )
            messages.success(
                request,
                _("{imported_count} cost line items loaded successfully.").format(
                    imported_count=result["imported_count"]
                ),
            )

        if request.POST.get("currency_code"):
            self.object.currency_code = request.POST.get("currency_code")
            self.object.save()

        return None  # Normal routing.

    def handle_upload_transactions(self, request, *args, **kwargs):
        f = request.FILES.get("file", None)
        errors = []
        if not f:
            errors.append(_("Please select a file."))

        succeeded, result = self.step.load_transactions(
            filter_by_country=self.settings.transaction_country_filter,
            f=f,
        )
        if (not succeeded) and ("errors" in result):
            errors += result["errors"]

        if len(errors) > 0:
            context = self.get_context_data(object=self.object)
            context["upload_transactions_errors"] = errors
            return self.render_to_response(context)
        else:
            try:
                t_count = result.get("imported_count")
            except Exception as e:
                logging.exception(e)
                t_count = "n/a"
            app_loggers.log_analysis_transactions_imported(
                self.analysis, t_count, result.get("imported_count"), self.request.user
            )
            messages.success(
                request,
                _("%(imported_count)s transactions imported successfully.") % result,
            )

        return None  # Normal routing.

    def handle_reset_data(self, request, *args, **kwargs):
        # Clear the currency code if it was set by a file upload.
        self.object.currency_code = ""
        self.object.save()

        self.step.invalidate()
        return None  # Normal routing.

    def handle_transaction_resync(self, request, *args, **kwargs):
        # Clear the currency code if it was set by a file upload.
        succeeded, result = self.step.resync_transactions_from_data_store(
            filter_by_country=self.settings.transaction_country_filter
        )
        if (not succeeded) and ("errors" in result):
            context = self.get_context_data(object=self.object)
            context["import_errors"] = result["errors"]
            return self.render_to_response(context)
        self.object.output_costs = {}
        self.object.needs_transaction_resync = False
        self.object.save()
        messages.success(self.request, _("Transactions have been synced successfully."))
