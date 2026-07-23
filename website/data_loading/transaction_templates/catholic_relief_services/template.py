from website.data_loading.transaction_templates import TransactionTemplate


class Template(TransactionTemplate):
    id = "catholic_relief_services"
    label = "Catholic Relief Services"
    download_headers = [
        "Date",
        "Country_code",
        "Grant_code",
        "Budget_line_code",
        "Account_code",
        "Site_code",
        "Sector_code",
        "Transaction_code",
        "Transaction_description",
        "Currency_code",
        "Budget_line_description",
        "Amount",
        "Dummy_field_1",
        "Dummy_field_2",
        "Dummy_field_3",
        "Dummy_field_4",
        "Dummy_field_5",
    ]
    download_date_fields = ("Date",)
    download_decimal_fields = ("Amount",)
    source_date_formats = {"date": ("%Y-%m-%d",)}
    canonical_field_sources = {
        "transaction_date": "date",
        "country_code": "country_code",
        "grant_code": "grant_code",
        "budget_line_code": "budget_line_code",
        "account_code": "account_code",
        "site_code": "site_code",
        "sector_code": "sector_code",
        "transaction_code": "transaction_code",
        "transaction_description": "transaction_description",
        "currency_code": "currency_code",
        "budget_line_description": "budget_line_description",
        "amount": "amount",
        "dummy_field_1": "dummy_field_1",
        "dummy_field_2": "dummy_field_2",
        "dummy_field_3": "dummy_field_3",
        "dummy_field_4": "dummy_field_4",
        "dummy_field_5": "dummy_field_5",
    }

    required_source_fields = {
        "date": "Date",
        "country_code": "Country_code",
        "grant_code": "Grant_code",
        "account_code": "Account_code",
        "currency_code": "Currency_code",
        "budget_line_description": "Budget_line_description",
        "amount": "Amount",
    }

    def normalize_rows(self, rows, analysis):
        return [
            {
                "transaction_date": row.get("date", ""),
                "country_code": row.get("country_code", ""),
                "grant_code": row.get("grant_code", ""),
                "budget_line_code": row.get("budget_line_code", ""),
                "account_code": row.get("account_code", ""),
                "site_code": row.get("site_code", ""),
                "sector_code": row.get("sector_code", ""),
                "transaction_code": row.get("transaction_code", ""),
                "transaction_description": row.get("transaction_description", ""),
                "currency_code": row.get("currency_code", ""),
                "budget_line_description": row.get("budget_line_description", ""),
                "amount": row.get("amount", ""),
                "dummy_field_1": row.get("dummy_field_1", ""),
                "dummy_field_2": row.get("dummy_field_2", ""),
                "dummy_field_3": row.get("dummy_field_3", ""),
                "dummy_field_4": row.get("dummy_field_4", ""),
                "dummy_field_5": row.get("dummy_field_5", ""),
            }
            for row in rows
        ]
