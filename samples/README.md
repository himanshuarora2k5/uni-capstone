# Sample data

Everything here is synthetic and tiny. It exists so the README walkthrough and the tests have fixed input.
It is NOT Loghub data and not real security telemetry. `.example` is a reserved domain; account id
`000000000000` is fake.

- `shopapp/sandbox_*` - what a sandbox run of ShopApp-mini would record (3 proxy lines, 1 CloudTrail record)
- `shopapp/prod_*` - a production run that goes outside the contract (analytics + notifications domains, `s3:PutObject`)
- `syslog_sample.log`, `apache_error_sample.log` - a few header-shaped lines, plus one line that matches nothing
