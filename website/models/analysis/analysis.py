import logging
import warnings
from decimal import Decimal

from ckeditor.fields import RichTextField
from django.conf import settings
from django.db import connection, models
from django.db.models import F, JSONField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from ombucore.admin.fields import ForeignKey
from website import betterdb, stopwatch
from website.models.intervention_instance import InterventionInstance
from website.models.cost_line_item import (
    AnalysisCostType,
    CostLineItem,
    CostLineItemInterventionAllocation,
)
from website.models.cost_type import CostType, ProgramCost
from website.models.cost_type_category_mapping import CostTypeCategoryMapping
from website.models.intervention import Intervention
from website.models.query_utils import require_prefetch
from website.models.region import Country
from website.models.settings import Settings
from website.models.transaction import TransactionLike
from .analysis_cost_type_category import AnalysisCostTypeCategory
from .analysis_cost_type_category_grant import AnalysisCostTypeCategoryGrant
from .analysis_cost_type_category_grant_intervention import (
    AnalysisCostTypeCategoryGrantIntervention,
)
from .analysis_type import AnalysisType

logger = logging.getLogger(__name__)


class Analysis(models.Model):
    CURRENCY_CHOICES = (
        ("USD", "US dollars"),
        ("GBP", "British Pound sterling"),
        ("EUR", "Euros"),
    )

    DATA_STORE_NAME = "Data store"

    app_log_entry_link_name = "analysis"
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    owner = ForeignKey(
        settings.AUTH_USER_MODEL,
        # see here: https://docs.djangoproject.com/en/dev/topics/auth/customizing/#django.contrib.auth.get_user_model
        null=True,
        on_delete=models.SET_NULL,
        related_name="analyses",
    )
    source = models.CharField(
        verbose_name=_("Source"),
        max_length=255,
        blank=True,
        null=True,
    )
    analysis_type = models.ForeignKey(
        AnalysisType,
        verbose_name=_("What data is this analysis based on?"),
        on_delete=models.PROTECT,
        related_name="+",
        blank=True,
        null=True,
    )
    interventions = models.ManyToManyField(
        "website.Intervention",
        through="website.InterventionInstance",
        related_name="analyses",
        verbose_name=_("Intervention Being Analyzed"),
    )
    title = models.CharField(
        verbose_name=_("Title"),
        max_length=255,
    )
    description = models.TextField(
        verbose_name=_("Description"),
        blank=True,
        null=True,
    )
    start_date = models.DateField(
        verbose_name=_("Start Date"),
    )
    end_date = models.DateField(
        verbose_name=_("End Date"),
    )
    country = models.ForeignKey(
        "website.Country",
        verbose_name=_("Country"),
        on_delete=models.PROTECT,
        related_name="+",
    )
    grants = models.CharField(max_length=255)
    output_costs = JSONField(default=dict)
    cloned_from = models.ForeignKey(
        "website.Analysis",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    currency_code = models.CharField(
        verbose_name=_("Currency code"),
        max_length=255,
        choices=CURRENCY_CHOICES,
        null=False,
        blank=True,
        default="",
    )
    output_count_source = models.CharField(
        verbose_name=_("Output count data source"),
        max_length=255,
        null=True,
        blank=True,
    )
    needs_transaction_resync = models.BooleanField(default=False, editable=False)

    efficiency_lesson = RichTextField(
        blank=True,
        null=True,
        help_text="What did we learn about the cost-efficiency of this intervention?",
    )

    breakdown_lesson = RichTextField(
        blank=True,
        null=True,
        help_text="Do the proportion of these cost categories look reasonable?",
    )

    # Each corresponds to a type of "additional cost" allowed by an Analysis
    # Note: Considered using a separate One-to-One config model for this information,
    # but it added unnecessary complexities to the Define step, as well as legacy migrations
    other_hq_costs = models.BooleanField(
        verbose_name=_("Other HQ Costs"),
        default=False,
        help_text="HQ costs that were not captured in the finance data",
    )
    in_kind_contributions = models.BooleanField(
        verbose_name=_("In-Kind Contributions"),
        default=False,
        help_text="Goods and services donated by other actors",
    )
    client_time = models.BooleanField(
        verbose_name=_("Client Time"),
        default=False,
        help_text="Time spent by people participating in the program",
    )

    # Populated on load-data step
    # This is a comma separated list, similar to grant, where the index of the value here matches up with the index
    # of its corresponding Grant in "grants"
    all_transactions_total_cost = models.CharField(
        verbose_name=_("All Transactions Total Cost, Comma separated by Grant"),
        max_length=512,
        blank=True,
        null=True,
        help_text="The Total Cost of every transaction corresponding to this Analysis, regardless of Country",
    )

    class Meta:
        verbose_name = _("Analysis")
        verbose_name_plural = _("Analyses")

    def __str__(self) -> str:
        return self.title

    @property
    def cost_line_items(self):
        return self.unfiltered_cost_line_items

    def query_grants(self) -> list[str]:
        """
        The list of grants used to query transactions.
        """
        return [grant.strip() for grant in self.grants.split(",")]

    def grants_list(self) -> list[str]:
        """
        The list of grants in the analysis' cost line items.
        """
        clis = require_prefetch(self, "unfiltered_cost_line_items")
        codes = {cli.grant_code for cli in clis if cli.grant_code}
        return sorted(codes)

    def get_all_transactions_total_cost(self, grant_code=None):
        if not (self.all_transactions_total_cost and self.grants):
            return None

        total_costs_list = [Decimal(cost_str) for cost_str in self.all_transactions_total_cost.split(",")]
        if not grant_code:
            return sum(total_costs_list)

        grants_list = self.grants.split(",")
        try:
            list_index = grants_list.index(grant_code)
        except ValueError:
            return None

        return total_costs_list[list_index]

    def get_all_countries_qs(self):
        if Settings.country_filtering_enabled():
            return Country.objects.filter(Q(always_include_costs=True) | Q(id=self.country_id))
        else:
            return Country.objects.filter(id=self.country_id)

    def get_all_countries_values(self, country_value):
        if not Settings.country_filtering_enabled():
            return None
        return list(self.get_all_countries_qs().order_by(country_value).values_list(country_value, flat=True))

    def get_special_countries_qs(self):
        if not Settings.country_filtering_enabled():
            return Country.objects.none()
        return Country.objects.filter(always_include_costs=True).exclude(id=self.country_id)

    def get_special_countries_values(self, country_value):
        if not Settings.country_filtering_enabled():
            return None
        return list(
            self.get_special_countries_qs().order_by(country_value).values_list(country_value, flat=True)
        )

    def is_complete(self) -> bool:
        for each_interventioninstance in self.interventioninstance_set.all():
            first_metric_id = next(
                iter(each_interventioninstance.intervention.output_metrics), None
            )  # Get first output metric or None.

            if not first_metric_id:
                return False
            if first_metric_id not in self.output_costs.get(str(each_interventioninstance.id), {}):
                return False
        return True

    def get_first_cost_per_output_all(self) -> Decimal | None:
        """
        Returns the first output cost including shared.
        """
        # Get the first intervention and its first output metric
        interventions = require_prefetch(self, "interventioninstance_set")
        if interventions:
            first_intervention = interventions[0]
        else:
            first_intervention = None
        first_metric_id = None
        if first_intervention and first_intervention.intervention.output_metrics:
            first_metric_id = first_intervention.intervention.output_metrics[0]

        # If metric id exists and is in output_costs, get its costs
        if first_metric_id and first_metric_id in self.output_costs.get(str(first_intervention.id), []):
            return self.output_costs[str(first_intervention.id)][first_metric_id].get("all")

        # Return None if either the first metric id does not exist or is not in output_costs
        return None

    def has_transactions(self) -> bool:
        return self.transactions.count() > 0

    def allows_other_costs(self) -> bool:
        return any([self.other_hq_costs, self.in_kind_contributions, self.client_time])

    @stopwatch.trace()
    def create_cost_line_items_from_transactions(self, transactions=None) -> None:
        self._create_cost_line_items_fast(transactions)

    def _create_cost_line_items_fast(self, transactions: list[TransactionLike] | None):
        special_cli_key_fields = [
            "country_code",
            "grant_code",
        ]

        def special_cli_key(tr):
            return tuple(getattr(tr, f) for f in special_cli_key_fields)

        cli_key_fields = [
            "country_code",
            "grant_code",
            "budget_line_code",
            "account_code",
            "site_code",
            "sector_code",
        ]

        def cli_key(tr):
            return tuple(getattr(tr, f) for f in cli_key_fields)

        # Transactions can be 'grouped' by some fields, and each of them in the group point to the same CostLineItem.
        # We increment the total cost of the Transactions the CostLineItem points to,
        # and keep track of the CostLineItem a Transaction points to.
        # Then at the end, we do a bulk insert of our CostLineItems.
        #
        # The problem however is that we have already inserted our transactions,
        # so we need to update them with the CLI ids.
        #
        # The trick to this is that:
        # - The transaction objects have their ID
        # - We can use the 'manual sequence lock' pattern to assign CLIs their own IDs in Python
        # - We can build up a CLI ID/Transaction ID mapping as we go.
        #   We eventually write this data to a temp 'staging' table.
        # - After we insert CLIs, we use this temp table to assign the transaction.cost_line_item_id FK value.
        #
        # In theory, we don't need this 'staging' table; we can use an UPDATE with a subselect or JOIN.
        # In practice, this performed very unreliably, and the manual ID assignment with the temp table
        # performed much faster and more reliably.
        #
        # If this is still insufficient, we need to rewrite the transaction importer to:
        # - Load transactions into memory
        # - Build and insert CLIs from the transactions, using the 'manual sequence lock', or INSERT RETURNING,
        #     to get their IDs
        # - Update the in-memory transactions with the CLI id, and then bulk insert them.
        # This is needed because right now we have a parent/child relationship but
        # end up inserting the child first; then we need a bulk update to associate it with its parent.
        if transactions is None:
            transactions = self.transactions.all()

        cost_line_items_by_key = {}
        special_cost_line_items_by_key = {}
        country_filtering_enabled = Settings.country_filtering_enabled()
        country_cache = {}

        with connection.cursor() as cursor:
            with betterdb.manual_sequence_lock(cursor, CostLineItem._meta.db_table) as seq:
                transaction_ids_for_cli_ids = {}
                for t in transactions:
                    if country_filtering_enabled and t.country_code != self.country.code:
                        key = special_cli_key(t)
                        cli = special_cost_line_items_by_key.get(key)
                        if cli is None:
                            if t.country_code in country_cache:
                                country_obj = country_cache[t.country_code]
                            else:
                                country_obj = Country.objects.filter(code=t.country_code).first()
                                country_cache[t.country_code] = country_obj
                            country_name = country_obj.name if country_obj else t.country_code

                            cli = dict(
                                id=seq.nextval(),
                                analysis_id=self.id,
                                country_code=t.country_code,
                                grant_code=t.grant_code,
                                budget_line_code="",
                                account_code="",
                                site_code="",
                                sector_code="",
                                budget_line_description=country_name,
                                total_cost=0,
                                dummy_field_1="",
                                dummy_field_2="",
                                note="",
                                is_special_lump_sum=True,
                            )
                            special_cost_line_items_by_key[key] = cli
                    else:
                        key = cli_key(t)
                        cli = cost_line_items_by_key.get(key)
                        if cli is None:
                            cli = dict(
                                id=seq.nextval(),
                                analysis_id=self.id,
                                country_code=t.country_code,
                                grant_code=t.grant_code,
                                budget_line_code=t.budget_line_code,
                                account_code=t.account_code,
                                site_code=t.site_code,
                                sector_code=t.sector_code,
                                budget_line_description=t.budget_line_description,
                                total_cost=0,
                                dummy_field_1="",
                                dummy_field_2="",
                                note="",
                                is_special_lump_sum=False,
                            )
                            cost_line_items_by_key[key] = cli
                    cli["total_cost"] += t.amount_in_instance_currency
                    transaction_ids_for_cli_ids.setdefault(cli["id"], []).append(t.id)

                all_line_items_by_key = {
                    **cost_line_items_by_key,
                    **special_cost_line_items_by_key,
                }
                cli_dicts = []
                for li in all_line_items_by_key.values():
                    close_to_zero = -0.01 < li["total_cost"] < 0.01
                    if close_to_zero:
                        transaction_ids_for_cli_ids.pop(li["id"])
                    else:
                        cli_dicts.append(li)

                betterdb.bulk_insert(CostLineItem, cli_dicts)

            cursor.execute(
                "CREATE TEMP TABLE transaction_id_cli_id_staging(t INTEGER, c INTEGER) ON COMMIT DROP;\n"
                "CREATE INDEX transaction_id_idx ON transaction_id_cli_id_staging(t)"
            )
            with betterdb.BulkInserter(cursor, "transaction_id_cli_id_staging") as bi:
                for cid, tids in transaction_ids_for_cli_ids.items():
                    for tid in tids:
                        bi.add_row({"t": tid, "c": cid})
            q = (
                "UPDATE website_transaction "
                "SET cost_line_item_id = transaction_id_cli_id_staging.c "
                "FROM transaction_id_cli_id_staging "
                "WHERE website_transaction.id = transaction_id_cli_id_staging.t"
            )
            cursor.execute(q)
            # For some reason ON COMMIT DROP doesn't work reliably in tests
            cursor.execute("DROP TABLE transaction_id_cli_id_staging")

        # We have a lot of items in this set, so this is MUCH faster.
        betterdb.delete(self.transactions.filter(cost_line_item_id__isnull=True))

    @stopwatch.trace()
    def sync_cost_line_items(self, transactions=None):
        if transactions is None:
            transactions = self.transactions.all()

        special_cli_key_fields = [
            "country_code",
            "grant_code",
        ]

        def special_cli_key(tr):
            return tuple(getattr(tr, f) for f in special_cli_key_fields)

        cli_key_fields = [
            "country_code",
            "grant_code",
            "budget_line_code",
            "account_code",
            "site_code",
            "sector_code",
        ]

        def cli_key(tr):
            return tuple(getattr(tr, f) for f in cli_key_fields)

        cost_line_items_by_key = {}
        special_cost_line_items_by_key = {}
        for cli in self.cost_line_items.all():
            cli.total_cost = 0
            if cli.is_special_lump_sum:
                special_cost_line_items_by_key[special_cli_key(cli)] = cli
            else:
                cost_line_items_by_key[cli_key(cli)] = cli

        country_filtering_enabled = Settings.country_filtering_enabled()
        for t in transactions:
            if country_filtering_enabled and t.country_code != self.country.code:
                key = special_cli_key(t)
                cli = special_cost_line_items_by_key.get(key)
                if cli is None:
                    country_obj = Country.objects.filter(code=t.country_code).first()
                    country_name = country_obj.name if country_obj else t.country_code
                    cli = CostLineItem(
                        analysis_id=self.id,
                        country_code=t.country_code,
                        grant_code=t.grant_code,
                        budget_line_code="",
                        account_code="",
                        site_code="",
                        sector_code="",
                        budget_line_description=country_name,
                        total_cost=0,
                        note="",
                        is_special_lump_sum=True,
                    )
                    special_cost_line_items_by_key[key] = cli
            else:
                key = cli_key(t)
                cli = cost_line_items_by_key.get(key)
                if cli is None:
                    cli = CostLineItem(
                        analysis=self,
                        country_code=t.country_code,
                        grant_code=t.grant_code,
                        budget_line_code=t.budget_line_code,
                        account_code=t.account_code,
                        site_code=t.site_code,
                        sector_code=t.sector_code,
                        budget_line_description=t.budget_line_description,
                        total_cost=0,
                        is_special_lump_sum=False,
                    )
                    cost_line_items_by_key[key] = cli
            cli.total_cost += t.amount_in_instance_currency

        clis = []
        all_line_items_by_key = {
            **cost_line_items_by_key,
            **special_cost_line_items_by_key,
        }
        for cli in all_line_items_by_key.values():
            if not -0.01 < cli.total_cost < 0.01:
                clis.append(cli)
            else:
                if cli.id:
                    cli.delete()

        betterdb.bulk_insert(CostLineItem, [cli for cli in clis if not cli.id])
        betterdb.bulk_update_dicts(
            CostLineItem,
            [{"id": cli.id, "total_cost": cli.total_cost} for cli in clis if cli.id],
        )

        # See above for why we do this
        # (match CLIs and Transactions on the common fields, as defined by `cli_key` above).
        #
        # We need a line like this for each field:
        #   (cli.account_code = website_transaction.account_code)
        # These fields cannot be null, so we do not need to worry about null comparisons.
        # Also, because we aren't interpolating any actual row values, this should be safe without escaping.
        filters = [f"cli.{f} = website_transaction.{f}" for f in cli_key_fields]
        # Security Note (07/16/2025) [B608]: No portion of the raw SQL string is user-provided
        # None of the interpolated values are user-provided,
        # and assembling this statement through psycopg is sufficiently inconvenient.
        if special_cost_line_items_by_key:
            # If special countries are included, there update WHERE logic is different and must also be included
            special_filters = [f"cli.{f} = website_transaction.{f}" for f in special_cli_key_fields]
            filter_statement = (
                f"({' AND '.join(filters)}) "
                f"OR (is_special_lump_sum = TRUE "
                f"AND {' AND '.join(special_filters)})"
            )
        else:
            filter_statement = " AND ".join(filters)
        q = f"""
        UPDATE website_transaction
        SET cost_line_item_id = (
            SELECT cli.id
            FROM website_costlineitem cli
            WHERE analysis_id = {self.id}
            AND ({filter_statement})
            LIMIT 1)
        WHERE analysis_id = {self.id}
        """  # nosec: B608
        with connection.cursor() as cursor:
            cursor.execute(q)

        betterdb.delete(self.transactions.filter(cost_line_item_id__isnull=True))

    def _create_cost_line_items_slow(self):
        """
        DEPRECATED, DO NOT USE!!!
        NEEDS TO BE UPDATED WITH special_country LOGIC FOR LUMP SUM COST ITEMS, AS IN _create_cost_line_items_fast
        """
        warnings.warn(
            "Do not use!  This NEEDS TO BE UPDATED WITH special_country "
            "LOGIC FOR LUMP SUM COST ITEMS, AS IN _create_cost_line_items_fast ",
            DeprecationWarning,
        )

        def cost_line_item_from_transactions(tqs):
            first_transaction = tqs.first()
            if not first_transaction:
                return None
            total_cost = tqs.aggregate(models.Sum("amount_in_instance_currency"))[
                "amount_in_instance_currency__sum"
            ]
            if not -0.01 < total_cost < 0.01:
                return CostLineItem.objects.create(
                    analysis=self,
                    country_code=first_transaction.country_code,
                    grant_code=first_transaction.grant_code,
                    budget_line_code=first_transaction.budget_line_code,
                    account_code=first_transaction.account_code,
                    site_code=first_transaction.site_code,
                    sector_code=first_transaction.sector_code,
                    budget_line_description=first_transaction.budget_line_description,
                    total_cost=total_cost,
                )

        fields = [
            "country_code",
            "grant_code",
            "budget_line_code",
            "account_code",
            "site_code",
            "sector_code",
        ]
        combinations = self.transactions.values_list(*fields).distinct()
        cost_line_items = []
        for combination_list in combinations:
            filter_kwargs = {field: combination_list[i] for i, field in enumerate(fields)}
            transactions_qs = self.transactions.filter(**filter_kwargs)
            cost_line_item = cost_line_item_from_transactions(transactions_qs)
            if cost_line_item:
                cost_line_items.append(cost_line_item)
                transactions_qs.update(cost_line_item_id=cost_line_item.id)
        self.transactions.filter(cost_line_item_id__isnull=True).delete()

    def auto_categorize_cost_line_items(self) -> None:
        cost_line_items = self.cost_line_items.prefetch_related(
            "config",
            "config__category",
            "config__cost_type",
        ).all()
        CostTypeCategoryMapping.auto_categorize_cost_line_items(cost_line_items)

    @stopwatch.trace()
    def ensure_cost_type_category_objects(self) -> list[int]:
        """
        Creates AnalysisCostTypeCategory objects for each combination of
        CostType and Category used by cost line items if they don't already exist.
        Removes AnalysisCostTypeCategory objects if they're no longer used by
        cost line items.
        """
        # Get cost_type_id, category_id tuples from the cost line items.
        cost_types_categories = list(
            self.cost_line_items.exclude(Q(config__cost_type__isnull=True) | Q(config__category__isnull=True))
            .order_by("config__cost_type__order", "config__category__order")
            .values_list("config__cost_type", "config__category")
            .distinct()
        )

        # If we have no cost_type categories, there's nothing to create or delete.
        # Return an empty list (created ids).
        if len(cost_types_categories) == 0:
            return []

        cost_type_ids, category_ids = zip(*cost_types_categories)
        cost_types_categories_set = set(cost_types_categories)

        used_ids = []
        existing = AnalysisCostTypeCategory.objects.filter(
            analysis=self,
            cost_type_id__in=cost_type_ids,
            category_id__in=category_ids,
        )
        for o in existing:
            cost_type_category_id = (o.cost_type_id, o.category_id)
            if cost_type_category_id in cost_types_categories_set:
                cost_types_categories_set.remove(cost_type_category_id)
                used_ids.append(o.id)
        to_create = [
            AnalysisCostTypeCategory(
                analysis=self,
                cost_type_id=cost_type_id,
                category_id=category_id,
            )
            for (cost_type_id, category_id) in cost_types_categories_set
        ]
        AnalysisCostTypeCategory.objects.bulk_create(to_create)

        created_ids = [o.id for o in to_create]
        used_ids.extend(created_ids)

        # Delete any cost_type categories that are no longer used by cost line items.
        self.cost_type_categories.exclude(id__in=used_ids).delete()

        self.ensure_cost_type_category_grant_objects()

        return created_ids

    def ensure_cost_type_category_grant_objects(self) -> list[int]:
        grants_list = self.grants_list()
        cost_type_categories = list(self.cost_type_categories.prefetch_related("cost_type").all())

        # If we have no cost_type categories, we have no grants to create.
        # Return an empty list (created ids).
        if len(cost_type_categories) == 0:
            return []

        cost_type_ids, category_ids = zip(*[(sc.cost_type_id, sc.category_id) for sc in cost_type_categories])

        relevant_cost_line_items = (
            self.cost_line_items.prefetch_related("config")
            .filter(
                config__cost_type_id__in=cost_type_ids,
                config__category_id__in=category_ids,
                grant_code__in=grants_list,
            )
            .all()
        )

        cost_type_category_grants_with_cost_line_items = set()
        for each_cost_line_item in relevant_cost_line_items:
            cost_type_category_grant = (
                each_cost_line_item.config.cost_type_id,
                each_cost_line_item.config.category_id,
                each_cost_line_item.grant_code,
            )
            cost_type_category_grants_with_cost_line_items.add(cost_type_category_grant)

        relevant_scgs = AnalysisCostTypeCategoryGrant.objects.filter(
            cost_type_category__in=cost_type_categories,
            grant__in=grants_list,
        ).all()

        analysis_scgrants_by_key = {}
        for o in relevant_scgs:
            analysis_scgrants_by_key[(o.cost_type_category_id, o.grant)] = o

        used_ids = []
        scg_to_create = []
        scga_to_create = []
        to_update = []
        for cost_type_category in cost_type_categories:
            for grant_code in grants_list:
                used_key = (
                    cost_type_category.cost_type_id,
                    cost_type_category.category_id,
                    grant_code,
                )
                if used_key not in cost_type_category_grants_with_cost_line_items:
                    continue

                existing_scg = analysis_scgrants_by_key.get((cost_type_category.id, grant_code))
                if existing_scg is None:
                    new_scg = AnalysisCostTypeCategoryGrant(
                        cost_type_category=cost_type_category,
                        grant=grant_code,
                    )
                    scg_to_create.append(new_scg)
                    for each_intervention_instance in self.interventioninstance_set.all():
                        scga_to_create.append(
                            AnalysisCostTypeCategoryGrantIntervention(
                                cost_type_grant=new_scg,
                                intervention_instance=each_intervention_instance,
                            )
                        )
                else:
                    used_ids.append(existing_scg.id)

        AnalysisCostTypeCategoryGrant.objects.bulk_create(scg_to_create)
        AnalysisCostTypeCategoryGrantIntervention.objects.bulk_create(scga_to_create)

        created_ids = [o.id for o in scg_to_create]
        used_ids.extend([o.id for o in to_update])
        used_ids.extend(created_ids)
        AnalysisCostTypeCategoryGrant.objects.filter(
            cost_type_category_id__in=self.cost_type_categories.values_list("id", flat=True),
        ).exclude(
            id__in=used_ids,
        ).delete()
        return created_ids

    def get_cost_types_used(self):
        return CostType.objects.filter(
            id__in=self.cost_type_categories.values_list("cost_type", flat=True).distinct()
        )

    @property
    def cost_type_category_grants(self):
        return AnalysisCostTypeCategoryGrant.objects.filter(
            cost_type_category__analysis_id=self.id,
        )

    def has_parameters(self) -> bool:
        for each_intervention_instance in self.interventioninstance_set.all():
            if not each_intervention_instance.has_parameters():
                return False
        return True

    def has_uncategorized_cost_line_items(self) -> bool:
        return self.get_uncategorized_cost_line_items().count() > 0

    def get_uncategorized_cost_line_items(self):
        return (
            self.cost_line_items.cost_type_category_items()
            .filter(Q(config__cost_type__isnull=True) | Q(config__category__isnull=True))
            .order_by("config__cost_type__order", "config__category__order")
        )

    def special_country_allocation_complete(self, grant_code=None):
        items = self.special_country_cost_line_items

        # narrow to just the provided grant_code
        if grant_code is not None:
            items = [item for item in items if item.grant_code == grant_code]

        # bail out on the first missing allocation
        for item in items:
            for alloc in item.config.allocations.all():
                if alloc.allocation is None:
                    return False
        return True

    def site_codes_choices_from_cost_line_items(self):
        return [
            (p, p)
            for p in self.cost_line_items.order_by("site_code").values_list("site_code", flat=True).distinct()
            if p
        ]

    def grant_codes_choices_from_cost_line_items(self):
        return [
            (p, p)
            for p in self.cost_line_items.order_by("grant_code")
            .values_list("grant_code", flat=True)
            .distinct()
            if p
        ]

    @property
    def special_country_cost_line_items(self):
        clis = require_prefetch(self, "unfiltered_cost_line_items")
        return [c for c in clis if c.is_special_lump_sum]

    @property
    def other_hq_costs_cost_line_items(self):
        return self.cost_line_items.filter(config__analysis_cost_type=AnalysisCostType.OTHER_HQ)

    @property
    def in_kind_contributions_cost_line_items(self):
        return self.cost_line_items.filter(config__analysis_cost_type=AnalysisCostType.IN_KIND)

    @property
    def client_time_cost_line_items(self):
        return self.cost_line_items.filter(config__analysis_cost_type=AnalysisCostType.CLIENT_TIME)

    def cost_line_items_with_no_subcomponent_allocation(
        self, cost_type: CostType | None = None, grant: str | None = None
    ):
        cost_line_items = self.cost_line_items.filter(
            Q(config__subcomponent_analysis_allocations={})
            | Q(config__subcomponent_analysis_allocations__isnull=True)
        )
        if cost_type:
            cost_line_items = cost_line_items.filter(config__cost_type=cost_type)
        if grant:
            cost_line_items = cost_line_items.filter(grant_code=grant)
        return cost_line_items.all()

    def cost_line_items_with_subcomponent_allocation_skipped(self, cost_type=None):
        if not cost_type:
            return self.cost_line_items.filter(
                Q(config__subcomponent_analysis_allocations_skipped=True)
            ).all()
        else:
            return self.cost_line_items.filter(
                Q(config__subcomponent_analysis_allocations_skipped=True) & Q(config__cost_type=cost_type)
            ).all()

    def get_cost_output_sums_all(self) -> dict[int, float]:
        """
        Get the Sum of the Total * Allocations for the Cost Line Items by their Intervention Allocation in this Analysis

        Float are used to maintain compatibility with the JSON fields in the database

        Output looks like this:
         {<intervention_instance_id1> : 123.45,
          <intervention_instance_id2> : 123.45,
          ...
        }
        """
        relevant_configs: set[int] = set(self.cost_line_items.values_list("config__id", flat=True))
        allocation_sums_by_intervention = {}
        for each_intervention_instance in self.interventioninstance_set.all():
            allocations_sums = dict(
                CostLineItemInterventionAllocation.objects.filter(
                    cli_config__id__in=relevant_configs,
                    intervention_instance=each_intervention_instance,
                )
                .values("cli_config__id")
                .annotate(
                    allocation_sum=Coalesce(
                        Sum("allocation") / Value(100),
                        Decimal(0),
                    )
                )
                .values_list("cli_config__id", "allocation_sum")
            )
            allocation_sums_by_intervention[each_intervention_instance] = allocations_sums

        cost_output_sum_all = {}
        for (
            each_intervention_instance,
            allocations_sums,
        ) in allocation_sums_by_intervention.items():
            cost_output_sum_all[each_intervention_instance.id] = 0
            for each_cli in (
                self.cost_line_items.all()
                .exclude(config__analysis_cost_type=AnalysisCostType.CLIENT_TIME)
                .exclude(config__analysis_cost_type=AnalysisCostType.IN_KIND)
            ):
                cost_output_sum_all[
                    each_intervention_instance.id
                ] += each_cli.total_cost * allocations_sums.get(each_cli.config.id, 0)

        # Map float to all of these to simplify code downstream (they were previously Decimal)
        cost_output_sum_all = {k: float(v) for k, v in cost_output_sum_all.items()}
        return cost_output_sum_all

    def get_cost_output_sum_direct_only(self) -> dict[int, float]:
        """
        Get the Sum of the Total * Allocations for the Cost Line Items that are Direct Program Costs
        by their Intervention Allocation in this Analysis

        Float are used to maintain compatibility with the JSON fields in the database

        Output looks like this:
         {<intervention_instance_id1> : 123.45,
          <intervention_instance_id2> : 123.45,
          ...
        }
        """
        relevant_configs: set[int] = set(
            self.cost_line_items.filter(
                config__cost_type__type=ProgramCost.id,
            ).values_list("config__id", flat=True)
        )
        allocation_sums_by_intervention = {}
        for each_intervention_instance in self.interventioninstance_set.all():
            allocations_sums = dict(
                CostLineItemInterventionAllocation.objects.filter(
                    cli_config__id__in=relevant_configs,
                    cli_config__cost_type__type=ProgramCost.id,
                    intervention_instance=each_intervention_instance,
                )
                .values("cli_config__id")
                .annotate(allocation_sum=Sum("allocation") / Value(100))
                .values_list("cli_config__id", "allocation_sum")
            )
            allocation_sums_by_intervention[each_intervention_instance] = allocations_sums

        cost_output_sums_direct_only = {}
        for (
            each_intervention_instance,
            allocations_sums,
        ) in allocation_sums_by_intervention.items():
            cost_output_sums_direct_only[each_intervention_instance.id] = 0

            for each_cli in (
                self.cost_line_items.all()
                .exclude(config__analysis_cost_type=AnalysisCostType.CLIENT_TIME)
                .exclude(config__analysis_cost_type=AnalysisCostType.IN_KIND)
            ):
                cost_output_sums_direct_only[
                    each_intervention_instance.id
                ] += each_cli.total_cost * allocations_sums.get(each_cli.config.id, 0)

        # Map float to all of these to simplify code downstream (they were previously Decimal)
        cost_output_sums_direct_only = {k: float(v) for k, v in cost_output_sums_direct_only.items()}
        return cost_output_sums_direct_only

    def get_cost_total_client_time(self) -> dict[int, float]:
        """
        Get the Sum of the Total * Allocations for the Cost Line Items that are Client Time
        by their Intervention Allocation in this Analysis

        Float are used to maintain compatibility with the JSON fields in the database

        Output looks like this:
         {<intervention_instance_id1> : 123.45,
          <intervention_instance_id2> : 123.45,
          ...
        }
        """

        if not self.client_time:
            return {}

        relevant_configs: set[int] = set(
            self.client_time_cost_line_items.values_list(
                "config__id",
                flat=True,
            )
        )

        allocation_sums_by_intervention = {}
        for each_intervention_instance in self.interventioninstance_set.all():
            allocations_sums = dict(
                CostLineItemInterventionAllocation.objects.filter(
                    cli_config__id__in=relevant_configs,
                    intervention_instance=each_intervention_instance,
                )
                .values("cli_config__id")
                .annotate(allocation_sum=Sum("allocation") / Value(100))
                .values_list("cli_config__id", "allocation_sum")
            )
            allocation_sums_by_intervention[each_intervention_instance] = allocations_sums
        cost_output_sums_client_time = {}
        for (
            each_intervention_instance,
            allocations_sums,
        ) in allocation_sums_by_intervention.items():
            cost_output_sums_client_time[each_intervention_instance.id] = 0

            for each_cli in self.client_time_cost_line_items:
                cost_output_sums_client_time[
                    each_intervention_instance.id
                ] += each_cli.total_cost * allocations_sums.get(each_cli.config.id, 0)
        # Map float to all of these to simplify code downstream (they were previously Decimal)
        cost_output_sums_client_time = {k: float(v) for k, v in cost_output_sums_client_time.items()}

        return cost_output_sums_client_time

    def get_cost_total_client_hours(self) -> float:
        if not self.client_time:
            return 0
        return (
            self.client_time_cost_line_items.annotate(
                total_client_hours=F("loe_or_unit") * F("quantity")
            ).aggregate(Sum("total_client_hours"))["total_client_hours__sum"]
            or 0
        )

    def get_cost_total_in_kind(self) -> dict[int, float]:
        """
        Get the Sum of the Total * Allocations for the Cost Line Items that are In Kind Contributions
        by their Intervention Allocation in this Analysis

        Float are used to maintain compatibility with the JSON fields in the database

        Output looks like this:
         {<intervention_instance_id1> : 123.45,
          <intervention_instance_id2> : 123.45,
          ...
        }
        """

        if not self.in_kind_contributions:
            return {}
        relevant_configs: set[int] = set(
            self.in_kind_contributions_cost_line_items.values_list(
                "config__id",
                flat=True,
            )
        )
        allocation_sums_by_intervention = {}

        for each_intervention_instance in self.interventioninstance_set.all():
            allocations_sums = dict(
                CostLineItemInterventionAllocation.objects.filter(
                    cli_config__id__in=relevant_configs,
                    intervention_instance=each_intervention_instance,
                )
                .values("cli_config__id")
                .annotate(allocation_sum=Sum("allocation") / Value(100))
                .values_list("cli_config__id", "allocation_sum")
            )
            allocation_sums_by_intervention[each_intervention_instance] = allocations_sums

        cost_output_sums_in_kind = {}
        for (
            each_intervention_instance,
            allocations_sums,
        ) in allocation_sums_by_intervention.items():
            cost_output_sums_in_kind[each_intervention_instance.id] = 0

            for each_cli in self.in_kind_contributions_cost_line_items:
                cost_output_sums_in_kind[
                    each_intervention_instance.id
                ] += each_cli.total_cost * allocations_sums.get(each_cli.config.id, 0)
        # Map float to all of these to simplify code downstream (they were previously Decimal)
        cost_output_sums_in_kind = {k: float(v) for k, v in cost_output_sums_in_kind.items()}
        return cost_output_sums_in_kind

    def calculate_output_costs(self) -> None:
        cost_output_sums_all = self.get_cost_output_sums_all()
        cost_output_sums_direct_only = self.get_cost_output_sum_direct_only()
        cost_output_sums_in_kind = self.get_cost_total_in_kind()
        cost_output_sums_client = self.get_cost_total_client_time()
        self.output_costs = {}

        for each_intervention_instance in self.interventioninstance_set.all():
            self.output_costs[str(each_intervention_instance.id)] = {}
            params = each_intervention_instance.parameters.copy()
            for output_metric in each_intervention_instance.intervention.output_metric_objects():
                try:
                    params["cost_output_sum"] = cost_output_sums_all[each_intervention_instance.id]

                    output_cost_all = output_metric.calculate(**params)

                    params["cost_output_sum"] = cost_output_sums_direct_only[each_intervention_instance.id]

                    output_cost_direct_only = output_metric.calculate(**params)

                    params.update(
                        {"cost_output_sum": cost_output_sums_in_kind.get(each_intervention_instance.id, 0)}
                    )
                    output_cost_in_kind = output_metric.calculate(**params)

                    self.output_costs[str(each_intervention_instance.id)][output_metric.id] = {
                        "all": float(round(output_cost_all, 2)),
                        "direct_only": float(round(output_cost_direct_only, 2)),
                        "in_kind": float(round(output_cost_in_kind, 2)),
                        "client": float(round(cost_output_sums_client.get(each_intervention_instance.id, 0))),
                    }
                except Exception as e:
                    # If we get an error it is likely just some shenanigans with the Output Metric
                    #   Parameters changing.  Leaving this here with the expectation that we'll
                    #   have an opportunity to make Output Metric Parameters more robust in the future.
                    pass
        self.save()

    def has_confirmed_subcomponent(self) -> bool:
        return (
            hasattr(self, "subcomponent_cost_analysis")
            and self.subcomponent_cost_analysis.subcomponent_labels_confirmed
        )

    def add_intervention(
        self,
        intervention: Intervention,
        label: str | None = None,
        order: int | None = None,
        parameters: dict | None = None,
    ) -> InterventionInstance:
        if parameters is None:
            parameters = {}

        intervention.check_parameters(parameters.keys())
        return InterventionInstance.objects.create(
            analysis=self,
            intervention=intervention,
            label=label,
            order=order,
            parameters=parameters,
        )

    def remove_intervention(self, intervention_id: int):
        InterventionInstance.objects.filter(
            analysis=self,
            intervention_id=intervention_id,
        ).delete()

    def get_suggested_allocations(self):
        """
        This returns all the suggested allocations for this analysis indexed by cost_type_id and grant.
        This replaces the previous method of computing these on an as needed basis for a cost_type because
        with the addition of the multiple interventions there are numerous edge cases where the final
        suggested allocation will exceed 100% by a tiny amount.

        This is obviously less performant than computing a single cost_type and if there are complaints we
        should optimize the SQL or cache the results.
        """
        data = {}
        for cost_type_category_grant in self.cost_type_category_grants:
            cost_type = cost_type_category_grant.cost_type_category.cost_type

            if isinstance(cost_type.type_obj(), ProgramCost):  # We don't ever suggest for this type of Sector
                continue

            grant = cost_type_category_grant.grant
            if cost_type.id not in data:
                data[cost_type.id] = {}
            data[cost_type.id][grant] = {}
            for intervention_instance in self.interventioninstance_set.all():
                data[cost_type.id][grant][
                    intervention_instance
                ] = cost_type.type_obj().get_suggested_allocation(
                    self,
                    intervention_instance,
                    cost_type_category_grant.grant,
                )
        data = self._adjust_allocations(data)
        return data

    def _adjust_allocations(self, data: dict) -> dict:
        """
        Adjust the allocation percentage based on the supplied data to not exceed 100%.  This
          leaves the numerator/denominator alone.  This value should always be a very small amount (i.e. 0.01 and
          effectively a rounding error.)

        This will always trim the value from the last Intervention Instance.   Order is ensured by the
          InterventionInstanceManager and Python3's dicts maintaining insertion order
        """
        grant_allocations: dict[str, dict]
        cost_type_id: int
        for cost_type_id, grant_allocations in data.items():
            grant: str
            intervention_instance_allocations: dict[InterventionInstance, tuple[float, float, Decimal]]
            for grant, intervention_instance_allocations in grant_allocations.items():
                cost_type_grant_total = sum(a[2] for a in intervention_instance_allocations.values())
                if cost_type_grant_total > Decimal(100):
                    delta = cost_type_grant_total - Decimal(100)

                    last_intervention_instance: InterventionInstance = list(
                        intervention_instance_allocations.keys()
                    )[-1]
                    intervention_instance_allocations[last_intervention_instance] = (
                        intervention_instance_allocations[last_intervention_instance][0],
                        intervention_instance_allocations[last_intervention_instance][1],
                        intervention_instance_allocations[last_intervention_instance][2] - delta,
                    )
        return data
