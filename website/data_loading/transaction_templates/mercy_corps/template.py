from website.data_loading.transaction_templates import TransactionTemplate


class Template(TransactionTemplate):
    id = "mercy_corps"
    label = "Mercy Corps"
    download_headers = [
        "dwh_data_source",
        "company",
        "posting_date",
        "posting_period",
        "calendar_quarter",
        "fiscal_year",
        "document_date",
        "processing_date",
        "document_no",
        "external_document_no",
        "g_l_account_no",
        "g_l_account_name",
        "g_l_account_category",
        "fund_no",
        "fund_name",
        "dept_code",
        "dept_name",
        "office_code",
        "office_name",
        "lin_code",
        "lin_name",
        "activity_code",
        "activity_name",
        "employee_id_code",
        "employee_name",
        "hcm_component_company",
        "ee_job_title",
        "subaward_code",
        "subaward_name",
        "dimension_codes_key",
        "description",
        "original_currency_ocy_code",
        "original_currency_ocy_amount",
        "ledger_currency_lcy_code",
        "ledger_currency_lcy_amount",
        "usd_amount",
        "gbp_amount",
        "eur_amount",
        "donor_reporting_currency_drcy_code",
        "donor_reporting_currency_drcy_amount",
        "subaward_currency_code",
        "subaward_currency_amount",
        "subaward_original_currency_code",
        "subaward_original_currency_amount",
        "journal_batch_name",
        "transaction_type",
        "mc_pr_no",
        "mc_po_no",
        "source_code",
        "source_type",
        "source_no",
        "vendor_name",
        "customer_name",
        "document_type",
        "user_id",
        "entry_no",
    ]
    download_date_fields = (
        "posting_date",
        "document_date",
        "processing_date",
    )
    download_decimal_fields = (
        "original_currency_ocy_amount",
        "ledger_currency_lcy_amount",
        "usd_amount",
        "gbp_amount",
        "eur_amount",
        "donor_reporting_currency_drcy_amount",
        "subaward_currency_amount",
        "subaward_original_currency_amount",
    )
    download_integer_fields = (
        "dept_code",
        "entry_no",
    )
    source_date_formats = {
        "posting_date": ("%Y-%m-%d",),
    }
    canonical_field_sources = {
        "transaction_date": "posting_date",
        "country_code": None,
        "grant_code": "fund_no",
        "budget_line_code": "lin_code",
        "account_code": "g_l_account_no",
        "site_code": "office_code",
        "sector_code": "activity_code",
        "transaction_code": "document_no",
        "transaction_description": "description",
        "currency_code": None,
        "budget_line_description": "lin_name",
        "amount": "usd_amount",
        "dummy_field_1": None,
        "dummy_field_2": None,
        "dummy_field_3": None,
        "dummy_field_4": None,
        "dummy_field_5": None,
    }

    required_source_fields = {
        "posting_date": "posting_date",
        "fund_no": "fund_no",
        "g_l_account_no": "g_l_account_no",
        "g_l_account_name": "g_l_account_name",
        "lin_name": "lin_name",
        "usd_amount": "usd_amount",
    }

    def rows_with_source_headers(self, rows):
        rows = list(rows)
        while rows and self._is_blank_row(rows[-1]):
            rows.pop()

        if len(rows) > 1 and self._is_total_footer_row(rows[-1]):
            rows.pop()

        return rows

    def normalize_rows(self, rows, analysis):
        return [
            {
                "transaction_date": row.get("posting_date", ""),
                "country_code": analysis.country.code,
                "grant_code": row.get("fund_no", ""),
                "budget_line_code": row.get("lin_code", ""),
                "account_code": row.get("g_l_account_no", ""),
                "site_code": row.get("office_code", ""),
                "sector_code": row.get("activity_code", ""),
                "transaction_code": row.get("document_no", ""),
                "transaction_description": row.get("description", ""),
                "currency_code": "USD",
                "budget_line_description": self._budget_line_description(row),
                "amount": row.get("usd_amount", ""),
                "dummy_field_1": "",
                "dummy_field_2": "",
                "dummy_field_3": "",
                "dummy_field_4": "",
                "dummy_field_5": "",
            }
            for row in rows
        ]

    @staticmethod
    def _budget_line_description(row):
        if row.get("lin_code", "") == "ICR":
            return "ICR"
        return row.get("lin_name", "") or row.get("g_l_account_name", "")

    @staticmethod
    def _is_blank_row(row):
        return not any(str(cell).strip() for cell in row if cell is not None)

    @staticmethod
    def _is_total_footer_row(row):
        return bool(row) and str(row[0]).strip().casefold() == "total"
