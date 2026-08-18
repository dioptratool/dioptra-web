Save the Children transaction template.

Select `Save the Children` in the admin panel under
`Settings > Analysis > Transaction Import Template`. The stored template ID is
`save_the_children`.

The source file is positional, 12 columns wide. Raw uploads that do not include
headers are treated as `column_1` through `column_12` before the normal mapping
step. If an uploaded file already includes `column_N` headers, those headers are
used directly.

Mapped fields:

| Save the Children position | Dioptra field               |
|----------------------------|-----------------------------|
| column_1                   | grant_code                  |
| column_2                   | budget_line_code            |
| column_3                   | budget_line_description     |
| column_4                   | account_code                |
| column_5                   | transaction_date            |
| column_6                   | amount                      |
| column_7                   | sector_code                 |
| column_8                   | dummy_field_1 (Transaction Custom Field 1) |
| column_9                   | dummy_field_2 (Transaction Custom Field 2) |
| column_10                  | dummy_field_3 (Transaction Custom Field 3) |
| column_11                  | dummy_field_4 (Transaction Custom Field 4) |
| column_12                  | dummy_field_5 (Transaction Custom Field 5) |

Required source columns:

- column_1
- column_3
- column_4
- column_5
- column_6

Two canonical fields have no source column in this layout:

- `country_code` is taken from the analysis's country.
- `currency_code` is set to `USD`; `column_6` is reported in USD.

`site_code`, `transaction_code` and `transaction_description` are not mapped.

`column_5` accepts `%Y%m` (e.g. `202306`), `%d/%m/%Y` and `%Y-%m-%d`. The
transaction date is normalized to Dioptra's canonical `YYYY-MM-DD`. Amounts must
be numeric strings without currency symbols; standard thousands separators are
allowed.

The five custom columns are surfaced as Transaction Custom Field 1-5 wherever
transactions are shown, and can be renamed under
`Settings > Manage Field Label Overrides > Transaction Custom Fields`. Custom
field values do not take part in grouping transactions into cost items.
