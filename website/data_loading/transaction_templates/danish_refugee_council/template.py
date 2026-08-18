from website.data_loading.transaction_templates.positional import PositionalTransactionTemplate


class Template(PositionalTransactionTemplate):
    id = "danish_refugee_council"
    label = "Danish Refugee Council"
    download_headers = [f"column_{column_number}" for column_number in range(1, 20)]
    download_date_fields = ("column_6", "column_7")
    download_decimal_fields = ("column_18",)
    source_date_formats = {
        "column_6": ("%Y-%m-%d",),
        "column_7": ("%Y-%m-%d",),
    }
    canonical_field_sources = {
        "transaction_date": "column_6",
        "country_code": "column_8",
        "grant_code": "column_9",
        "budget_line_code": "column_10",
        "account_code": "column_11",
        "site_code": None,
        "sector_code": None,
        "transaction_code": None,
        "transaction_description": "column_15",
        "currency_code": "column_16",
        "budget_line_description": "column_17",
        "amount": "column_18",
        "dummy_field_1": None,
        "dummy_field_2": None,
        "dummy_field_3": None,
        "dummy_field_4": None,
        "dummy_field_5": None,
    }

    required_source_fields = {
        "column_6": "column_6",
        "column_8": "column_8",
        "column_9": "column_9",
        "column_11": "column_11",
        "column_16": "column_16",
        "column_17": "column_17",
        "column_18": "column_18",
    }

    def normalize_rows(self, rows, analysis):
        return [
            {
                "transaction_date": row.get("column_6", ""),
                "country_code": row.get("column_8", ""),
                "grant_code": row.get("column_9", ""),
                "budget_line_code": row.get("column_10", ""),
                "account_code": row.get("column_11", ""),
                "site_code": "",
                "sector_code": "",
                "transaction_code": "",
                "transaction_description": row.get("column_15", ""),
                "currency_code": row.get("column_16", ""),
                "budget_line_description": row.get("column_17", ""),
                "amount": row.get("column_18", ""),
                "dummy_field_1": "",
                "dummy_field_2": "",
                "dummy_field_3": "",
                "dummy_field_4": "",
                "dummy_field_5": "",
            }
            for row in rows
        ]
