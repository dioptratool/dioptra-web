import json

from django.contrib.auth import get_user_model
from django.db import connection, models, transaction as db_transaction

from website.data_loading.utils import BulkInserter
from website.models import (
    Analysis,
    AnalysisCostTypeCategory,
    AnalysisCostTypeCategoryGrant,
    CostLineItem,
    CostLineItemConfig,
    InterventionInstance,
    SubcomponentCostAnalysis,
    Transaction,
)
from website.models.analysis import AnalysisCostTypeCategoryGrantIntervention
from website.models.cost_line_item import CostLineItemInterventionAllocation

User = get_user_model()


def cloneable_row(row, **attrs):
    row["cloned_from_id"] = row.pop("id")
    row.update(attrs)
    for k, v in row.items():
        if v is None:
            row[k] = "\u0001"
        if isinstance(v, dict) or isinstance(v, list):
            row[k] = json.dumps(v)
    return row


def old_to_new_id_map(model, **filters) -> dict:
    values = model.objects.filter(**filters).values_list("cloned_from_id", "id").all()
    return {old: new for old, new in values}


@db_transaction.atomic
def clone_analysis(analysis_id: int, owner: User, **values) -> Analysis:
    """Clone an analysis, and all of its:

    - transactions
    - cost line items
    - cost line item configs
    - cost_type categories
    - cost_type category grants
    - subcomponent analyses

    All cloning is done through the bulk CSV loader, so it's fast.

    Each clone has a 'cloned_from_id' set to the model it was cloned from.
    It is used by this cloning method (other parts of the app can also use it if desired).

    When we clone a nested model, like CostLineItemConfig <- CostLineItem <- Analysis,
    we build a map of "old id to new id" for the intermediate model (CostLineItem).
    Then when we build up the rows of Configs to insert, we can grab the new 'parent' ID from that map.
    """
    og_analysis = Analysis.objects.get(pk=analysis_id)
    new_dates = {}
    if "start_date" in values and "end_date" in values:
        new_dates["start_date"] = values["start_date"]
        new_dates["end_date"] = values["end_date"]

    if new_dates:
        new_title = og_analysis.title + " (DUPLICATE, NEW DATES)"
    else:
        new_title = og_analysis.title + " (DUPLICATE)"

    new_analysis: Analysis = simple_clone(
        og_analysis,
        title=new_title,
        owner_id=owner.id,
        **new_dates,
    )

    with BulkInserter(connection, InterventionInstance._meta.db_table) as inserter:
        for ai in InterventionInstance.objects.filter(analysis=og_analysis).values().all():
            inserter.add_row(cloneable_row(ai, analysis_id=new_analysis.pk))
    old_to_new_intervention_instances = old_to_new_id_map(InterventionInstance, analysis=new_analysis)

    with BulkInserter(connection, CostLineItem._meta.db_table) as inserter:
        for cli in CostLineItem.objects.filter(analysis=og_analysis).values().all():
            inserter.add_row(cloneable_row(cli, analysis_id=new_analysis.pk))

    old_to_new_clis = old_to_new_id_map(CostLineItem, analysis=new_analysis)
    with BulkInserter(connection, CostLineItemConfig._meta.db_table) as inserter:
        for clic in (
            CostLineItemConfig.objects.filter(cost_line_item__in=old_to_new_clis.keys()).values().all()
        ):
            inserter.add_row(
                cloneable_row(
                    clic,
                    cost_line_item_id=old_to_new_clis[clic["cost_line_item_id"]],
                )
            )

    old_to_new_cli_configs = {}
    for cli in CostLineItem.objects.filter(analysis=new_analysis).all():
        old_to_new_cli_configs.update(old_to_new_id_map(CostLineItemConfig, cost_line_item=cli))

    with BulkInserter(connection, CostLineItemInterventionAllocation._meta.db_table) as inserter:
        for cli_allocation in (
            CostLineItemInterventionAllocation.objects.filter(cli_config__in=old_to_new_cli_configs.keys())
            .values()
            .all()
        ):
            cli_allocation["intervention_instance_id"] = old_to_new_intervention_instances[
                cli_allocation["intervention_instance_id"]
            ]
            inserter.add_row(
                cloneable_row(
                    cli_allocation,
                    cli_config_id=old_to_new_cli_configs[cli_allocation["cli_config_id"]],
                )
            )
    # We must import transactions once we have the new cost line item they point to.
    # Updating after-the-fact is extremely slow (or would require some indices on cloned_from_id
    # which we don't want, as this is a large table that receives bulk imports).
    with BulkInserter(connection, Transaction._meta.db_table) as inserter:
        for txn in Transaction.objects.filter(analysis=og_analysis).values().all():
            inserter.add_row(
                cloneable_row(
                    txn,
                    analysis_id=new_analysis.pk,
                    cost_line_item_id=old_to_new_clis[txn["cost_line_item_id"]],
                )
            )

    with BulkInserter(connection, AnalysisCostTypeCategory._meta.db_table) as inserter:
        for asc in AnalysisCostTypeCategory.objects.filter(analysis=og_analysis).values().all():
            inserter.add_row(cloneable_row(asc, analysis_id=new_analysis.pk))

    old_to_new_ascs = old_to_new_id_map(AnalysisCostTypeCategory, analysis=new_analysis)

    with BulkInserter(connection, AnalysisCostTypeCategoryGrant._meta.db_table) as inserter:
        grants = AnalysisCostTypeCategoryGrant.objects.filter(cost_type_category__in=old_to_new_ascs.keys())
        for ascg in grants.values().all():
            inserter.add_row(
                cloneable_row(
                    ascg,
                    cost_type_category_id=old_to_new_ascs[ascg["cost_type_category_id"]],
                )
            )

    old_to_new_ascgs = {}
    for asc in AnalysisCostTypeCategory.objects.filter(id__in=old_to_new_ascs.values()).all():
        old_to_new_ascgs.update(old_to_new_id_map(AnalysisCostTypeCategoryGrant, cost_type_category=asc))

    with BulkInserter(connection, AnalysisCostTypeCategoryGrantIntervention._meta.db_table) as inserter:
        for ascga in (
            AnalysisCostTypeCategoryGrantIntervention.objects.filter(
                cost_type_grant__in=old_to_new_ascgs.keys()
            )
            .values()
            .all()
        ):
            inserter.add_row(
                cloneable_row(
                    ascga,
                    cost_type_grant_id=old_to_new_ascgs[ascga["cost_type_grant_id"]],
                    intervention_instance_id=old_to_new_intervention_instances[
                        ascga["intervention_instance_id"]
                    ],
                )
            )

    if hasattr(og_analysis, "subcomponent_cost_analysis") and og_analysis.subcomponent_cost_analysis:
        with BulkInserter(connection, SubcomponentCostAnalysis._meta.db_table) as inserter:
            subcomponent_analysis = (
                SubcomponentCostAnalysis.objects.filter(analysis=og_analysis).values().first()
            )

            inserter.add_row(cloneable_row(subcomponent_analysis, analysis_id=new_analysis.pk))
    new_analysis.output_costs = {}
    new_analysis.save()
    return new_analysis


def simple_clone(obj: models.Model, **attrs) -> models.Model:
    model = type(obj)
    values = model.objects.filter(pk=obj.pk).values().first()
    values.pop(model._meta.pk.name)
    values["cloned_from_id"] = obj.pk
    values.update(**attrs)
    clone = model(**values)
    clone.save()
    return clone
