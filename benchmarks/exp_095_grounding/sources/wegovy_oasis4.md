# Topic 9: Oral Wegovy (Semaglutide) OASIS 4 Trial — Ground Truth

**Domain:** Pharmaceutical / obesity
**FDA approval:** Late 2025 / early January 2026
**Manufacturer:** Novo Nordisk
**Primary source:** OASIS 4 trial results (NEJM, DOI: 10.1056/NEJMoa2500969), ACC summary
**Secondary source:** FDA approval press release, Applied Clinical Trials Online
**Collected:** 2026-04-10 via WebSearch

## Why this is a hard topic

Post-cutoff: FDA approved the oral formulation around late 2025 / early January 2026. The trial data (OASIS 4) was published in 2025 (possibly in training) but the FDA approval and the specific "first oral GLP-1 for weight loss" framing is 2026. This is a MIXED topic: the model might have SOME data from the trial publication but not the FDA decision context. Direct comparison to easy-set topic_04 (donanemab/Kisunla) tests a different drug, different indication, similar domain.

## Verified numerical claims

### OASIS 4 trial design

| Metric | Value |
|---|---|
| Trial name | OASIS 4 |
| Design | Randomized, double-blind, placebo-controlled |
| Duration | 64 weeks |
| Enrollment | 307 adults |
| Population | Adults with obesity or overweight plus at least one weight-related comorbidity, excluding diabetes |
| Drug | Oral semaglutide 25 mg once daily |
| Brand name | Wegovy (oral formulation) |

### Primary efficacy

| Metric | Treatment | Placebo |
|---|---|---|
| Mean weight loss at 64 weeks (adherent) | 16.6% | 2.7% |
| Achieved at least 20% weight loss | approximately one-third | under 3% |
| Achieved at least 5% weight loss | 76% | 31% |

### Regulatory

| Metric | Value |
|---|---|
| Significance | First oral GLP-1 receptor agonist approved for weight loss |
| Additional indication | Reduce risk of major adverse cardiovascular events (death, heart attack, stroke) |
| Expected launch | Early January 2026 |

## Verification rules

- Weight loss: 16.6% at 64 weeks (adherent population). Accept "approximately 17%" or "16-17%."
- The "adherent" qualifier matters: the treatment policy estimate (including dropouts) is different and lower.
- Placebo: 2.7%. The difference (approximately 14 percentage points) is derivable.
- The one-third / 20% threshold: accept "about 33%" or "one in three."
- 76% / 31% at the 5% threshold.
- Enrollment: 307 adults. Much smaller than donanemab's 1,736.
- Duration: 64 weeks. Different from donanemab's 76 weeks.
- The "first oral GLP-1 for weight loss" framing is the key post-cutoff claim.
- Models may confuse the injectable Wegovy (already available) with the oral formulation (new).
- Models may confuse OASIS 4 with other OASIS trials (OASIS 1, 2, 3 tested different doses/populations).
