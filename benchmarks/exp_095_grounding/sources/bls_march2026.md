# Topic 8: US BLS Employment Situation March 2026 — Ground Truth

**Domain:** Economic / labor market
**Period:** March 2026
**Released:** April 3, 2026 (7 days ago)
**Primary source:** Bureau of Labor Statistics, The Employment Situation, March 2026
**Secondary source:** Bloomberg, CNBC reporting on the release
**Collected:** 2026-04-10 via WebSearch

## Why this is a hard topic

Post-cutoff: released April 3, 2026 (one week ago). The model cannot have this data in training. This is the most recent topic in the set. Different domain from financial earnings: tests labor market statistics, a completely different kind of factual claim with different source structures (government agency vs corporate filings).

## Verified numerical claims

### Headline figures

| Metric | Value |
|---|---|
| Total nonfarm payroll employment change | +178,000 |
| Unemployment rate | 4.3% |
| Number of unemployed persons | 7.2 million |
| Labor force participation rate | 61.9% |
| Employment-population ratio | 59.2% |

### Wage data

| Metric | Value |
|---|---|
| Average hourly earnings monthly change | +0.2% |
| Average hourly earnings annual change | +3.5% (lowest since May 2021) |

### Industry detail

| Industry | Jobs gained/lost |
|---|---|
| Health care | +76,000 |
| Ambulatory health care services | +54,000 |
| Construction | +26,000 |
| Transportation and warehousing | +21,000 |

## Verification rules

- Payroll: accept +178,000 or "178 thousand" or "about 178,000"
- Unemployment: 4.3% exactly
- Unemployed: 7.2 million
- Labor force participation: 61.9%
- Average hourly earnings: +0.2% month OR +3.5% year
- Health care: +76,000 (ambulatory subset +54,000)
- Construction: +26,000
- A model citing February 2026 data as context is showing PRIOR MONTH, which is correct context but not the asked-for March data
- The "lowest since May 2021" qualifier on annual wage growth is a verifiable claim models might fabricate or get right
