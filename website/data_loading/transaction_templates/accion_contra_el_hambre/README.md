Accion Contra el Hambre transaction template.

Select `Accion Contra el Hambre` in the admin panel under
`Settings > Analysis > Transaction Import Template`. The stored template ID is
`accion_contra_el_hambre`.

The upload file is expected to include the headers returned by the transaction
template download. Unmapped headers are accepted as no-op fields so users can
upload the Accion Contra el Hambre report shape without reducing it to only
Dioptra fields first.

Mapped fields:

| Accion Contra el Hambre header | Dioptra field           |
|--------------------------------|-------------------------|
| trans_date                     | transaction_date        |
| dim_1                          | country_code            |
| contract                       | grant_code              |
| cat5_adjusted                  | budget_line_code        |
| account                        | account_code            |
| cat6                           | sector_code             |
| trans_no                       | transaction_code        |
| text                           | transaction_description |
| description_ii                 | budget_line_description |
| amount_eur                     | amount                  |

The layout has no currency column, so `currency_code` is left blank and the
currency configured for the instance is used; `amount_eur` is reported in that
currency.

Required source headers:

- contract
- trans_date
- account
- amount_eur
- dim_1

`trans_date` accepts `%m/%d/%Y` and is normalized to Dioptra's canonical
`YYYY-MM-DD` date. Amounts must be numeric strings without currency symbols.
Standard thousands separators are allowed.
