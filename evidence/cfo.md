# cfo.ai evidence

## Saved model

On October 11, 2026, cfo.ai created a page titled **Promise Ledger — Scenario Model** in the signed-in hackathon workspace. The page keeps measured product usage separate from pricing and operating assumptions and saves three named scenarios: Downside, Base, and Growth.

The live comparison was checked row by row against `evidence/cfo_inputs.csv`. All 42 scenario cells matched:

| Scenario | Revenue | Total COGS | Gross margin | Net cash flow | Runway |
| --- | ---: | ---: | ---: | ---: | ---: |
| Downside | $1,225 | $503.23 | 58.92% | -$4,278.23 | 11.69 months |
| Base | $7,800 | $1,884.41 | 75.84% | -$6,084.41 | 8.22 months |
| Growth | $29,000 | $6,515.05 | 77.53% | $484.95 | cash-flow positive |

The model also records the measured three-document audit usage: 2,886 input tokens, 929 output tokens, 3,815 total tokens, and $0.016505 assumed model cost per audit. It includes the $32.83 base-case contribution estimate, approximately 386-contract break-even, and both pricing hypotheses.

## Export and verification

- `evidence/cfo_scenario_model.xlsx` is the spreadsheet exported directly by cfo.ai.
- `evidence/cfo_scenario_model.png` is a rendered view of the exported comparison table.
- The workbook imports successfully with three sheets and 42 scenario formulas.
- The formula-error scan found no `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A`, `#NUM!`, `#NULL!`, `#SPILL!`, or `#CALC!` results.
- Export SHA-256: `80a8395dc3210c787bb12513449e5af4dc748b5196018427706f768b0cfc5d0b`.
- Render SHA-256: `997d6d04cd3e20800f2fd16cbf4a2add24bf5540f8907deac50d8dc55ee9c812`.

The exported workbook is the durable submission artifact. A live-dashboard screenshot can still be added to the final video capture, but the repository no longer depends on an authenticated cfo.ai session to inspect the financial model.
