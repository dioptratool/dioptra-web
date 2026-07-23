Mercy Corps transaction template.

Select `Mercy Corps` in the admin panel under
`Settings > Analysis > Transaction Import Template`. The stored template ID is
`mercy_corps`.

The upload file is expected to include the headers returned by the transaction
template download. Unmapped headers are accepted as no-op fields so users can
upload the Mercy Corps report shape without reducing it to only Dioptra fields
first.

Mapped fields:

| Mercy Corps header | Dioptra field           |
|--------------------|-------------------------|
| posting_date       | transaction_date        |
| fund_no            | grant_code              |
| lin_code           | budget_line_code        |
| g_l_account_no     | account_code            |
| office_code        | site_code               |
| activity_code      | sector_code             |
| document_no        | transaction_code        |
| description        | transaction_description |
| lin_name           | budget_line_description |
| g_l_account_name   | budget_line_description fallback |
| usd_amount         | amount                  |

The template sets `country_code` to the analysis country code and `currency_code`
to `USD`.

Required source headers:

- posting_date
- fund_no
- g_l_account_no
- g_l_account_name
- lin_name
- usd_amount

`posting_date` must use `%Y-%m-%d`. `posting_period` and
`calendar_quarter` are text fields, not dates.

Rows with `lin_code` set to `ICR` use `ICR` as the budget line description
instead of the value from `lin_name`, including when `lin_name` is blank. Other
rows use `g_l_account_name` as the budget line description when `lin_name` is
blank.
