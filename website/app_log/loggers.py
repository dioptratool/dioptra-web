from app_log.logger import log


def log_analysis_created(analysis, user=None):
    log(user, "Created", analysis, f"Created analysis {analysis.title}.")


def log_analysis_updated(analysis, user=None):
    log(
        user,
        "Properties updated",
        analysis,
        f"Updated properties of analysis {analysis.title}.",
    )


def log_analysis_deleted(analysis, user=None):
    log(user, "Deleted", analysis, f"Deleted analysis {analysis.title}.")


def log_analysis_transactions_imported(analysis, transaction_count, cost_item_count, user=None):
    log(
        user,
        "Transactions Imported",
        analysis,
        f"Imported {transaction_count} transactions into {cost_item_count} cost items into {analysis.title} "
        f"from the transaction data store.",
    )


def log_analysis_budget_uploaded(analysis, cost_item_count, user=None):
    log(
        user,
        "Budget Upload Imported",
        analysis,
        f"Imported {cost_item_count} cost items into {analysis.title} from a budget upload.",
    )


def log_analysis_cost_model_download(analysis, cost_item_count, user=None):
    log(
        user,
        "Cost Model Download",
        analysis,
        f"Cost model downloaded for {analysis.title}.",
    )


def log_intervention_created(intervention, user=None):
    log(user, "Created", intervention, f"Created intervention {intervention.name}.")


def log_intervention_updated(intervention, user=None):
    log(
        user,
        "Properties updated",
        intervention,
        f"Updated properties of intervention {intervention.name}.",
    )


def log_intervention_deleted(intervention, user=None):
    log(user, "Deleted", intervention, f"Deleted intervention {intervention.name}.")


def log_intervention_group_created(intervention_groupd, user=None):
    log(
        user,
        "Created",
        intervention_groupd,
        f"Created intervention group {intervention_groupd.name}.",
    )


def log_intervention_group_updated(intervention_groupd, user=None):
    log(
        user,
        "Properties updated",
        intervention_groupd,
        f"Updated properties of intervention group {intervention_groupd.name}.",
    )


def log_intervention_group_deleted(intervention_groupd, user=None):
    log(
        user,
        "Deleted",
        intervention_groupd,
        f"Deleted intervention group {intervention_groupd.name}.",
    )


def log_cost_type_created(cost_type, user=None):
    log(user, "Created", cost_type, f"Created cost type group {cost_type.name}.")


def log_cost_type_updated(cost_type, user=None):
    log(
        user,
        "Properties updated",
        cost_type,
        f"Updated properties of cost type {cost_type.name}.",
    )


def log_cost_type_deleted(cost_type, user=None):
    log(user, "Deleted", cost_type, f"Deleted cost type {cost_type.name}.")


def log_category_created(category, user=None):
    log(user, "Created", category, f"Created category {category.name}.")


def log_category_updated(category, user=None):
    log(
        user,
        "Properties updated",
        category,
        f"Updated properties of category {category.name}.",
    )


def log_category_deleted(category, user=None):
    log(user, "Deleted", category, f"Deleted category {category.name}.")


def log_category_cost_type_mapping_created(category_cost_type, user=None):
    log(
        user,
        "Created",
        category_cost_type,
        f"Created cost type & category mapping for {category_cost_type.cost_type.name} - {category_cost_type.category.name} .",
    )


def log_category_cost_type_updated(category_cost_type, user=None):
    log(
        user,
        "Properties updated",
        category_cost_type,
        f"Updated properties of cost type & category mapping for "
        f"{category_cost_type.cost_type.name} - {category_cost_type.category.name} .",
    )


def log_category_cost_type_deleted(category_cost_type, user=None):
    log(
        user,
        "Deleted",
        category_cost_type,
        f"Deleted cost type & category mapping for {category_cost_type.cost_type.name} - {category_cost_type.category.name} .",
    )


def log_country_created(country, user=None):
    log(user, "Created", country, f"Created country {country.name}.")


def log_country_updated(country, user=None):
    log(
        user,
        "Properties updated",
        country,
        f"Updated properties of country {country.name}.",
    )


def log_country_deleted(country, user=None):
    log(user, "Deleted", country, f"Deleted country {country.name}.")


def log_region_created(region, user=None):
    log(user, "Created", region, f"Created region {region.name}.")


def log_region_updated(region, user=None):
    log(
        user,
        "Properties updated",
        region,
        f"Updated properties of region {region.name}.",
    )


def log_region_deleted(region, user=None):
    log(user, "Deleted", region, f"Deleted region {region.name}.")


def log_insight_comparison_created(insight_comparison, user=None):
    log(
        user,
        "Created",
        insight_comparison,
        f"Created insight comparison data point {insight_comparison.name}.",
    )


def log_insight_comparison_updated(insight_comparison, user=None):
    log(
        user,
        "Properties updated",
        insight_comparison,
        f"Updated properties of insight comparison data point {insight_comparison.name}.",
    )


def log_insight_comparison_deleted(insight_comparison, user=None):
    log(
        user,
        "Deleted",
        insight_comparison,
        f"Deleted insight comparison data point {insight_comparison.name}.",
    )


def log_cost_efficiency_strategy_created(cost_efficiency_strategy, user=None):
    log(
        user,
        "Created",
        cost_efficiency_strategy,
        f"Created insight comparison data point {cost_efficiency_strategy.title}.",
    )


def log_cost_efficiency_strategy_updated(cost_efficiency_strategy, user=None):
    log(
        user,
        "Properties updated",
        cost_efficiency_strategy,
        f"Updated properties of insight comparison data point {cost_efficiency_strategy.title}.",
    )


def log_cost_efficiency_strategy_deleted(cost_efficiency_strategy, user=None):
    log(
        user,
        "Deleted",
        cost_efficiency_strategy,
        f"Deleted insight comparison data point {cost_efficiency_strategy.title}.",
    )


def log_account_code_created(account_code, user=None):
    log(
        user,
        "Created",
        account_code,
        f"Created account code description {account_code.account_code}.",
    )


def log_account_code_updated(account_code, user=None):
    log(
        user,
        "Properties updated",
        account_code,
        f"Updated properties of account code description {account_code.account_code}.",
    )


def log_account_code_deleted(account_code, user=None):
    log(
        user,
        "Deleted",
        account_code,
        f"Deleted account code description {account_code.account_code}.",
    )


def log_help_item_created(help_item, user=None):
    log("system", "Created", help_item, f"Created contextual help {help_item.title}.")


def log_help_item_updated(help_item, user=None):
    log(
        "system",
        "Properties updated",
        help_item,
        f"Updated contextual help {help_item.title}.",
    )


def log_help_item_deleted(help_item, user=None):
    log("system", "Deleted", help_item, f"Deleted contextual help {help_item.title}.")


def log_help_page_created(help_page, user=None):
    log(user, "Created", help_page, f"Created help page {help_page.title}.")


def log_help_page_updated(help_page, user=None):
    log(user, "Properties updated", help_page, f"Updated help page {help_page.title}.")


def log_help_page_deleted(help_page, user=None):
    log(user, "Deleted", help_page, f"Deleted help page {help_page.title}.")


def log_updated_cost_item_field_label_overrides(overrides, user=None):
    log(
        user,
        "Properties updated",
        overrides,
        f"Updated field label overrides for Cost Item fields.",
    )


def log_updated_transaction_field_label_overrides(help_page, user=None):
    log(
        user,
        "Properties updated",
        help_page,
        f"Updated field label overrides for Transaction Item fields.",
    )


def log_image_created(image, user=None):
    log(user, "Created", image, f"Created image {image.title}.")


def log_image_updated(image, user=None):
    log(user, "Properties updated", image, f"Updated image {image.title}.")


def log_image_deleted(image, user=None):
    log(user, "Deleted", image, f"Deleted image {image.title}.")


def log_asset_folder_created(asset_folder, user=None):
    log(user, "Created", asset_folder, f"Created asset folder {asset_folder.title}.")


def log_asset_folder_updated(asset_folder, user=None):
    log(
        user,
        "Properties updated",
        asset_folder,
        f"Updated asset folder {asset_folder.title}.",
    )


def log_asset_folder_deleted(asset_folder, user=None):
    log(user, "Deleted", asset_folder, f"Deleted asset folder {asset_folder.title}.")


def log_asset_tag_created(asset_tag, user=None):
    log(user, "Created", asset_tag, f"Created asset tag {asset_tag.title}.")


def log_asset_tag_updated(asset_tag, user=None):
    log(user, "Properties updated", asset_tag, f"Updated asset tag {asset_tag.title}.")


def log_asset_tag_deleted(asset_tag, user=None):
    log(user, "Deleted", asset_tag, f"Deleted asset tag {asset_tag.title}.")


def log_user_made_active(active_user, user=None):
    log(user, "Made active", active_user, f"{active_user} was marked as active.")


def log_user_made_inactive(active_user, user=None):
    log(user, "Made active", active_user, f"{active_user} was marked as inactive.")


def log_user_password_reset(user):
    log(user, "Password reset", user, f"Password reset for user {user}.")
