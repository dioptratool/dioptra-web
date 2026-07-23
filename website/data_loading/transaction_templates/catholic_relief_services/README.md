Catholic Relief Services transaction template.

Select `Catholic Relief Services` in the admin panel under
`Settings > Analysis > Transaction Import Template`. The stored template ID is
`catholic_relief_services`.

The upload file is expected to include the headers returned by the transaction
template download. The CRS report shape is close to Dioptra's canonical
transaction format; this template maps the CRS header names to Dioptra's
canonical transaction field names.

Mapped fields:

| Catholic Relief Services header | Dioptra field           |
|---------------------------------|-------------------------|
| Date                            | transaction_date        |
| Country_code                    | country_code            |
| Grant_code                      | grant_code              |
| Budget_line_code                | budget_line_code        |
| Account_code                    | account_code            |
| Site_code                       | site_code               |
| Sector_code                     | sector_code             |
| Transaction_code                | transaction_code        |
| Transaction_description         | transaction_description |
| Currency_code                   | currency_code           |
| Budget_line_description         | budget_line_description |
| Amount                          | amount                  |
| Dummy_field_1                   | dummy_field_1           |
| Dummy_field_2                   | dummy_field_2           |
| Dummy_field_3                   | dummy_field_3           |
| Dummy_field_4                   | dummy_field_4           |
| Dummy_field_5                   | dummy_field_5           |

Required source headers:

- Date
- Country_code
- Grant_code
- Account_code
- Currency_code
- Budget_line_description
- Amount

`Date` must use `%Y-%m-%d`. Amounts must be numeric strings without currency
symbols. Standard thousands separators are allowed.
