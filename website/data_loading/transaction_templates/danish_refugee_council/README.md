Danish Refugee Council transaction template.

Select `Danish Refugee Council` in the admin panel under
`Settings > Analysis > Transaction Import Template`. The stored template ID is
`danish_refugee_council`.

The source file is positional. For raw DRC uploads that do not include headers,
the template treats the columns as `column_1` through `column_19` before applying
the normal mapping step. If an uploaded file already includes `column_N` headers,
those headers are used directly.

Mapped fields:

| Danish Refugee Council position | Dioptra field           |
|---------------------------------|-------------------------|
| column_6                        | transaction_date        |
| column_8                        | country_code            |
| column_9                        | grant_code              |
| column_10                       | budget_line_code        |
| column_11                       | account_code            |
| column_15                       | transaction_description |
| column_16                       | currency_code           |
| column_17                       | budget_line_description |
| column_18                       | amount                  |

Required source columns:

- column_6
- column_8
- column_9
- column_11
- column_16
- column_17
- column_18

`column_6` and `column_7` accept `%Y-%m-%d`. The transaction date
is normalized to Dioptra's canonical `YYYY-MM-DD` date. Amounts must be numeric
strings without currency symbols. Standard thousands separators are allowed.
