from website.data_loading.transaction_templates import TransactionTemplate


class Template(TransactionTemplate):
    id = "cooperative_for_assistance_and_relief_everywhere"
    label = "Cooperative for Assistance and Relief Everywhere (CARE)"
    download_headers = [
        "journal_date",
        "country_code",
        "grant_code",
        "budget_line_code",
        "account",
        "site_code",
        "project_id",
        "journal_id",
        "transaction_description",
        "currency_cd",
        "budget_line_description",
        "bu_amount",
        "book_code",
        "voucher_line_description",
    ]
    download_date_fields = ("journal_date",)
    download_decimal_fields = ("bu_amount",)
    source_date_formats = {
        "journal_date": ("%m/%d/%Y",),
    }
    canonical_field_sources = {
        "transaction_date": "journal_date",
        "country_code": "country_code",
        "grant_code": "grant_code",
        "budget_line_code": "budget_line_code",
        "account_code": "account",
        "site_code": "site_code",
        "sector_code": None,
        "transaction_code": "journal_id",
        "transaction_description": "transaction_description",
        "currency_code": "currency_cd",
        "budget_line_description": "budget_line_description",
        "amount": "bu_amount",
        "dummy_field_1": None,
        "dummy_field_2": None,
        "dummy_field_3": None,
        "dummy_field_4": None,
        "dummy_field_5": None,
    }

    required_source_fields = {
        "journal_date": "journal_date",
        "country_code": "country_code",
        "grant_code": "grant_code",
        "account": "account",
        "currency_cd": "currency_cd",
        "budget_line_description": "budget_line_description",
        "bu_amount": "bu_amount",
    }

    def normalize_rows(self, rows, analysis):
        return [
            {
                "transaction_date": row.get("journal_date", ""),
                "country_code": row.get("country_code", ""),
                "grant_code": row.get("grant_code", ""),
                "budget_line_code": row.get("budget_line_code", ""),
                "account_code": row.get("account", ""),
                "site_code": row.get("site_code", ""),
                "sector_code": "",
                "transaction_code": row.get("journal_id", ""),
                "transaction_description": row.get("transaction_description", ""),
                "currency_code": row.get("currency_cd", ""),
                "budget_line_description": row.get("budget_line_description", ""),
                "amount": row.get("bu_amount", ""),
                "dummy_field_1": "",
                "dummy_field_2": "",
                "dummy_field_3": "",
                "dummy_field_4": "",
                "dummy_field_5": "",
            }
            for row in rows
        ]
