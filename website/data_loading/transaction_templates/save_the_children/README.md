Save the Children transaction template.

Select `Save the Children` in the admin panel under
`Settings > Analysis > Transaction Import Template`. The stored template ID is
`save_the_children`.

The upload file is expected to include the headers returned by the transaction
template download. Unmapped headers are accepted as no-op fields so users can
upload the Save the Children report shape without reducing it to only Dioptra
fields first.

Mapped fields:

| Save the Children header   | Dioptra field           |
|----------------------------|-------------------------|
| Costc Description          | country_code            |
| CostC (T), as a fallback   | country_code            |
| Subaward Code              | grant_code              |
| Budget Chapter             | budget_line_code        |
| Budget Chapter Description | budget_line_description |
| Account                    | account_code            |
| Period                     | transaction_date        |
| Amount in USD              | amount                  |

The template sets `currency_code` to `USD`.
`Country Office`, `Transaction Date`, `Trans No`, and
`Transaction Desc (Text)` are accepted as no-op fields and are not mapped.

Required source headers:

- Costc Description (or CostC (T))
- Subaward Code
- Budget Chapter Description
- Account
- Period
- Amount in USD

When `Costc Description` is absent, `CostC (T)` supplies `country_code`. If
both headers are present, `Costc Description` takes precedence.

`Period` accepts `YYYYMM`, `%d/%m/%Y`, or `%Y-%m-%d` and is normalized to
Dioptra's canonical `YYYY-MM-DD` date. A `YYYYMM` period uses the first day of
the month; for example, `202605` becomes `2026-05-01`. Amounts must be numeric
strings without currency symbols. Standard thousands separators are allowed.
