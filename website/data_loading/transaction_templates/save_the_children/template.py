from website.data_loading.transaction_templates.positional import PositionalTransactionTemplate

CUSTOM_FIELD_COLUMNS = {
    "dummy_field_1": "column_8",
    "dummy_field_2": "column_9",
    "dummy_field_3": "column_10",
    "dummy_field_4": "column_11",
    "dummy_field_5": "column_12",
}


class Template(PositionalTransactionTemplate):
    """Save the Children positional 12-column transaction export.

    ``country_code`` and ``currency_code`` have no source column in this layout:
    the analysis supplies the country, and the instance currency supplies the currency.
    """

    id = "save_the_children"
    label = "Save the Children"
    download_headers = [f"column_{column_number}" for column_number in range(1, 13)]
    download_date_fields = ("column_5",)
    download_decimal_fields = ("column_6",)
    source_date_formats = {
        "column_5": ("%Y%m", "%d/%m/%Y", "%Y-%m-%d"),
    }
    canonical_field_sources = {
        "transaction_date": "column_5",
        "country_code": None,
        "grant_code": "column_1",
        "budget_line_code": "column_2",
        "account_code": "column_4",
        "site_code": None,
        "sector_code": "column_7",
        "transaction_code": None,
        "transaction_description": None,
        "currency_code": None,
        "budget_line_description": "column_3",
        "amount": "column_6",
        **CUSTOM_FIELD_COLUMNS,
    }

    required_source_fields = {
        "column_1": "column_1",
        "column_3": "column_3",
        "column_4": "column_4",
        "column_5": "column_5",
        "column_6": "column_6",
    }

    def normalize_rows(self, rows, analysis):
        return [
            {
                "transaction_date": row.get("column_5", ""),
                "country_code": analysis.country.code,
                "grant_code": row.get("column_1", ""),
                "budget_line_code": row.get("column_2", ""),
                "account_code": row.get("column_4", ""),
                "site_code": "",
                "sector_code": row.get("column_7", ""),
                "transaction_code": "",
                "transaction_description": "",
                "currency_code": "",
                "budget_line_description": row.get("column_3", ""),
                "amount": row.get("column_6", ""),
                **{
                    canonical_field: row.get(source_column, "")
                    for canonical_field, source_column in CUSTOM_FIELD_COLUMNS.items()
                },
            }
            for row in rows
        ]
