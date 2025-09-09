from typing import AnyStr, IO, TextIO

from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _l

from website import betterdb, stopwatch
from website.data_loading.cost_line_items import load_cost_line_items_from_file
from website.data_loading.transactions import load_transactions
from website.models import CostLineItemConfig, Transaction
from website.workflows._steps_base import Step


class LoadData(Step):
    name: str = "load-data"
    nav_title: str = _l("Load Data")

    @cached_property
    def dependencies_met(self) -> bool:
        return self.workflow.get_step("define").is_complete

    @cached_property
    def is_complete(self) -> bool:
        if not self.dependencies_met:
            return False
        if getattr(self.analysis, "needs_transaction_resync", None):
            return False
        if self.analysis and getattr(self.analysis, "pk", None):
            return self.analysis.cost_line_items.count() > 0
        return False

    def get_href(self) -> str:
        return reverse("analysis-load-data", kwargs={"pk": self.analysis.pk})

    @betterdb.transaction()
    def load_transactions(
        self,
        filter_by_country: bool = False,
        from_datastore: bool = False,
        f: IO[AnyStr] | None = None,
    ) -> tuple[bool, dict]:
        succeeded, result = load_transactions(
            self.analysis,
            filter_by_country=filter_by_country,
            from_datastore=from_datastore,
            f=f,
        )
        if succeeded:
            self.analysis.create_cost_line_items_from_transactions(result["imported_transactions"])
            self.analysis.auto_categorize_cost_line_items()
            self.analysis.ensure_cost_type_category_objects()
        return succeeded, result

    @betterdb.transaction()
    def resync_transactions_from_data_store(self, filter_by_country: bool = False) -> tuple[bool, dict]:
        betterdb.delete(self.analysis.transactions.all())
        succeeded, result = load_transactions(
            self.analysis, filter_by_country=filter_by_country, from_datastore=True
        )
        if succeeded:
            self.analysis.sync_cost_line_items(result["imported_transactions"])
            self.analysis.auto_categorize_cost_line_items()
            self.analysis.ensure_cost_type_category_objects()
        return succeeded, result

    @betterdb.transaction()
    def load_cost_line_items_from_file(self, f: TextIO) -> tuple[bool, dict]:
        succeeded, result = load_cost_line_items_from_file(self.analysis, f)
        if succeeded:
            self.analysis.auto_categorize_cost_line_items()
            self.analysis.ensure_cost_type_category_objects()
        return succeeded, result

    @stopwatch.trace()
    @betterdb.transaction()
    def invalidate(self) -> None:
        self.workflow.invalidate_step("insights")
        self.workflow.invalidate_step("allocate")
        # Handle these 'cascades' manually, we don't want Django pulling this into Python.
        # Ideally the database would handle it though!
        Transaction.objects.filter(cloned_from__analysis=self.analysis).update(cloned_from=None)
        betterdb.delete(self.analysis.transactions.all())

        self.analysis.cost_type_categories.all().delete()

        CostLineItemConfig.objects.filter(cloned_from__cost_line_item__analysis=self.analysis).update(
            cloned_from=None
        )
        betterdb.delete(CostLineItemConfig.objects.filter(cost_line_item__analysis=self.analysis))

        self.analysis.cost_line_items.all().delete()
        self.analysis.source = None
        self.analysis.save()
