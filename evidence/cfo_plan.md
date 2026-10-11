# Promise Ledger financial model

This model is prepared for entry into cfo.ai. It separates measured product usage from commercial assumptions so the unit economics can be challenged without changing the technical evidence.

## Measured input

The saved live audit in `evidence/run_live_audit.json` processed three documents and nine promises using three model calls:

| Metric | Measured value |
| --- | ---: |
| Prompt tokens per audit | 2,886 |
| Completion tokens per audit | 929 |
| Total tokens per audit | 3,815 |
| Model calls per audit | 3 |

These counts come from the provider usage object captured during the live audit. They are not estimates.

## Pricing assumptions

Provider prices are scenario inputs because the deployment contract is not part of the repository:

- Input token price: $2.50 per million tokens.
- Output token price: $10.00 per million tokens.
- Resulting model cost: $0.016505 per three-document audit.
- Observability allowance: $0.005 per audit.

The cost equation is:

```text
(2,886 / 1,000,000 * $2.50) + (929 / 1,000,000 * $10.00) = $0.016505
```

Token cost is not the margin constraint. Infrastructure, review support, security, and customer operations dominate COGS.

## Packaging hypothesis

Test two offers during customer discovery:

1. Per-contract: $49 per monitored contract per month, including six scheduled or change-triggered audits.
2. Platform: $499 per month including 20 contracts, then $19 per additional contract.

The recommended starting offer is the platform plan. It matches how legal and security teams budget software, avoids penalizing customers for adding contracts, and still exposes a contract-based expansion metric.

## Scenario output

| Scenario | Contracts | Effective price | Audits / month | Revenue | COGS | Gross margin | Opex | Net cash flow | Runway on $50k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Downside | 25 | $49 | 150 | $1,225 | $503.23 | 58.92% | $5,000 | -$4,278.23 | 11.69 months |
| Base | 200 | $39 | 1,600 | $7,800 | $1,884.41 | 75.84% | $12,000 | -$6,084.41 | 8.22 months |
| Growth | 1,000 | $29 | 10,000 | $29,000 | $6,515.05 | 77.53% | $22,000 | $484.95 | cash-flow positive |

The base case intentionally funds product and go-to-market before break-even. At the base-case price and audit frequency, contribution after variable model, observability, and per-contract support is about $32.83 per contract per month. With $12,650 of fixed monthly infrastructure and operating expense, break-even is approximately 386 monitored contracts.

## cfo.ai entry map

Use `evidence/cfo_inputs.csv` for the three scenarios and map:

- Revenue driver: monitored contracts multiplied by monthly price per contract.
- Model API COGS: audits multiplied by $0.016505.
- Observability COGS: audits multiplied by $0.005.
- Fixed and stepped COGS: infrastructure plus support and compliance operations.
- Cash: $50,000 opening balance.
- Runway: opening cash divided by monthly burn when net cash flow is negative.

Before a real fundraising or pricing decision, replace the assumed token prices, infrastructure, payroll, and support figures with invoices and a hiring plan. The measured audit token counts can remain as the initial workload baseline.
