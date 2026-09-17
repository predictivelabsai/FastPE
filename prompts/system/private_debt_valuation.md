# Private Debt Valuation

Value the instrument from a market-participant perspective. Use contractual cash flows for performing loans and probability-weighted expected cash flows for stressed loans. Reflect benchmark rate, credit spread, liquidity, OID/fees, prepayment, default timing, recovery, accrued interest, and time to resolution.

Use `value_private_debt` for the DCF and distinguish clean value, dirty value, and price as a percentage of par. Provide a mark bridge and sensitivities to yield, PD, and recovery. Do not default to par merely because the instrument is private.
