Cooperative for Assistance and Relief Everywhere (CARE) transaction template.

Select `Cooperative for Assistance and Relief Everywhere (CARE)` in the admin panel
under `Settings > Analysis > Transaction Import Template`. The stored template
ID is `cooperative_for_assistance_and_relief_everywhere`.

The upload file is expected to include the headers returned by the transaction
template download. Unmapped headers are accepted as no-op fields so users can
upload the CARE report shape without reducing it to only Dioptra fields first.

Mapped fields:

| CARE header                 | Dioptra field           |
|-----------------------------|-------------------------|
| journal_date                | transaction_date        |
| country_code                | country_code            |
| grant_code                  | grant_code              |
| budget_line_code            | budget_line_code        |
| account                     | account_code            |
| site_code                   | site_code               |
| journal_id                  | transaction_code        |
| transaction_description     | transaction_description |
| currency_cd                 | currency_code           |
| budget_line_description     | budget_line_description |
| bu_amount                   | amount                  |

Required source headers:

- journal_date
- country_code
- grant_code
- account
- currency_cd
- budget_line_description
- bu_amount

`journal_date` accepts `%m/%d/%Y` and is normalized to Dioptra's canonical
`YYYY-MM-DD` date. Zero padding is not required. Amounts must be numeric strings
without currency symbols. Standard thousands separators are allowed.

`budget_line_code`, `account`, and `journal_id` are formatted as text in the
download template so identifier values and leading zeroes are preserved.
