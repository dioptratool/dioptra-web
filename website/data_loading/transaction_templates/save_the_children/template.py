from website.data_loading.transaction_templates import TransactionTemplate


class Template(TransactionTemplate):
    id = "save_the_children"
    label = "Save the Children"
    download_headers = [
        "Country Office",
        "Country Office Description",
        "Programme Office",
        "Programme Office Description",
        "Costc",
        "Costc Description",
        "Function",
        "Function Description",
        "Project",
        "Project Name",
        "SOF",
        "SOF Name",
        "Budget Chapter",
        "Budget Chapter Description",
        "DRC Short Code",
        "DRC Long Code",
        "DRC Description",
        "Standard Activity",
        "Standard Activity Description",
        "Activity Code",
        "Activity Name",
        "Proxy Account Code",
        "Proxy Account Description",
        "Account",
        "Account Description",
        "Analysis Type",
        "Analysis",
        "Analysis Description",
        "Job Name Code",
        "Job Name Description",
        "Subaward Code",
        "Subaward Description",
        "International / National",
        "Transaction Date",
        "Supplier ID - AP/AR ID",
        "Supplier/Cust (T)",
        "OrderNo",
        "InvoiceNo",
        "Trans No",
        "Transaction Desc (Text)",
        "Period",
        "Transaction Currency",
        "Amount in Transaction Currency",
        "Donor Currency",
        "Donor Cur Amount",
        "Amount in USD",
        "User",
    ]
    download_date_fields = ("Period",)
    download_decimal_fields = (
        "Amount in Transaction Currency",
        "Donor Cur Amount",
        "Amount in USD",
    )
    source_date_formats = {
        "period": ("%Y%m", "%d/%m/%Y", "%Y-%m-%d"),
    }
    source_header_aliases = {
        "costc_description": ("costc_t",),
    }
    canonical_field_sources = {
        "transaction_date": "period",
        "country_code": "costc_description",
        "grant_code": "subaward_code",
        "budget_line_code": "budget_chapter",
        "account_code": "account",
        "site_code": None,
        "sector_code": None,
        "transaction_code": None,
        "transaction_description": None,
        "currency_code": None,
        "budget_line_description": "budget_chapter_description",
        "amount": "amount_in_usd",
        "dummy_field_1": None,
        "dummy_field_2": None,
        "dummy_field_3": None,
        "dummy_field_4": None,
        "dummy_field_5": None,
    }

    required_source_fields = {
        "costc_description": "Costc Description or CostC (T)",
        "subaward_code": "Subaward Code",
        "budget_chapter_description": "Budget Chapter Description",
        "account": "Account",
        "period": "Period",
        "amount_in_usd": "Amount in USD",
    }

    def normalize_rows(self, rows, analysis):
        normalized_rows = [
            {
                canonical_field: row.get(source_field, "") if source_field else ""
                for canonical_field, source_field in self.canonical_field_sources.items()
            }
            for row in rows
        ]
        for row in normalized_rows:
            row["currency_code"] = "USD"
        return normalized_rows
