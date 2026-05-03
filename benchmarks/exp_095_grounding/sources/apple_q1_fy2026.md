# Topic 6: Apple Q1 FY2026 Financial Results — Ground Truth

**Domain:** Financial / consumer tech
**Period:** Quarter ended December 27, 2025
**Reported:** January 30, 2026
**Primary source:** Apple 10-Q filed with SEC, Apple newsroom press release
**Collected:** 2026-04-10 via WebFetch on StockTitan 10-Q summary

## Why this is a hard topic

Post-cutoff: gpt-5.4's training likely ends early-mid 2025. Apple Q1 FY2026 was reported January 30, 2026. The model should NOT have these numbers in training. Direct comparison to easy-set topic_02 (Apple Q1 FY2025, $124.3B) isolates the cutoff effect on the same entity.

## Verified numerical claims

### Revenue

| Metric | Value |
|---|---|
| Total net sales | $143.756 billion |
| iPhone revenue | $85.269 billion |
| Services revenue | $30.013 billion |
| Mac revenue | $8.386 billion |
| iPad revenue | $8.595 billion |
| Wearables, Home and Accessories | $11.493 billion |
| Year-over-year total revenue growth | 16% |
| Services year-over-year growth | 14% |

### Profitability

| Metric | Value |
|---|---|
| Total gross margin percentage | 48.2% |
| Products gross margin percentage | 40.7% |
| Services gross margin percentage | 76.5% |
| Total gross margin dollars | $69.231 billion |
| Net income | $42.097 billion |
| Diluted EPS | $2.84 |
| Basic EPS | $2.85 |

### Geography

| Region | Revenue |
|---|---|
| Americas | $58.529 billion |
| Europe | $38.146 billion |
| Greater China | $25.526 billion |
| Japan | $9.413 billion |
| Rest of Asia Pacific | $12.142 billion |

### Cash and returns

| Metric | Value |
|---|---|
| Operating cash flow | $53.925 billion |
| Cash and equivalents | $45.317 billion |
| Share repurchases | $25.0 billion |
| Dividends paid | $3.9 billion |
| Dividend per share | $0.26 |
| Active devices installed base | 2.5 billion |

## Verification rules

- Total revenue: accept $143.8B, $143.756B, $143.76B, "approximately $144 billion"
- iPhone: accept $85.3B, $85.269B, $85.27B
- Services: accept $30.0B, $30.013B
- EPS: $2.84 diluted is the standard
- Gross margin: 48.2% total
- Growth: 16% YoY total, 14% services
- Prior year comparison: Q1 FY2025 was $124.3B (from the easy set). A model citing this as context is CORRECT.
