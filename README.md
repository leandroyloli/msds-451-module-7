# MSDS 451: Programming Assignment 3

Earlier assignments defined the jobs of the portfolio, selected ETFs for the growth block, and studied how to divide capital among them. This assignment turns that allocation into a system that decides when to buy, sell and rebalance. It then tests whether adding momentum improves the result after costs.

The question moves from **what to hold and how much to invest** to **how to operate and maintain the portfolio over time**.

The program can operate and reconcile the fund automatically. In this sample, repeated rebalancing did not beat holding the initial allocation on growth or Sharpe. Trend reduced drawdown at the cost of growth, without establishing a stable Sharpe advantage. It remains an experiment rather than the default fund policy.

Student: Leandro Loli. Northwestern University, MSDS 451, Section 001, Fall 2026.

Repository: [leandroyloli/msds-451-module-7](https://github.com/leandroyloli/msds-451-module-7).

Clone URL: https://github.com/leandroyloli/msds-451-module-7.git

Canvas submission is handled separately by the student.

## Read

- [PDF research report](report/msds451-pa3.pdf): submission artifact.
- [Self-contained HTML report](report/msds451-pa3.html): same content, figures and tables in a browser file.
- [Editable report source](report/report.md): generated Markdown.
- [Study guide](resources/STUDY_GUIDE.md): purpose, decisions, checks and remaining steps.
- [Official assignment snapshot](resources/assignment.md): requirements and grading rubric.

The PDF and HTML follow the preceding assignments' academic serif typography, restrained green headings, numbered sections, clear tables, equations and English figure labels. Sources are explicit. The initial six-ETF experiment is preserved separately in `resources/archive/initial-experiment.zip`; that historical archive is excluded from Git. Earlier course deliverables remain unchanged.

The main report explains the rule, results and decision in four sections. Appendices hold formulas, accounting, sensitivity checks, trade records and the full candidate list.

## Reproduce

Tested with Python 3.13.15. Create an environment and install pinned dependencies:

```powershell
cd C:/studing/msds-451-module-7
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run.py
.venv/Scripts/python.exe run.py --check
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m pipeline.qa_artifacts
```

On macOS/Linux, use `.venv/bin/python`. An existing environment does not need to be recreated. Installation needs network access. Ordinary analysis, tests and report generation are offline and require no tokens, API keys, sibling directories, Canvas access or Git.

- `python run.py`: recompute all structural allocations, five accounts, chronological segments, sensitivities and conditional bootstrap; validate; regenerate figures and PDF/HTML/Markdown.
- `python run.py --check`: validate the saved outputs, independently rebuild positions from trade units, reproduce the main accounts and execute future-perturbation/truncated-input checks.
- `python run.py --report-only`: validate saved accounting and rebuild the report; it does not repeat temporal checks. The verification file records whether temporal tests were run.
- `python -m unittest discover -s tests -v`: focused deterministic software tests. Artificial fixture data are never used as research observations.
- `python -m pipeline.qa_artifacts`: render every PDF page to `tmp/pdfs`, verify page numbers/text bounds and check report consistency. Rendered pages also require visual inspection.
- `python -m pipeline.check_reproduction`: rerun in a clean isolated folder using only included source and raw inputs, compare numerical outputs, run checks and record the result.

The full study takes several minutes, mainly for repeated conic allocations and temporal controls. The complete installed dependency set is recorded in `resources/environment-lock.txt`. Windows uses Palatino when available; the PDF falls back to Times elsewhere. Numeric reproduction does not depend on that font choice.

`pipeline/import_snapshot.py` documents the one-time import from Module 6. Do not run it for normal reproduction. It is the only helper that reads a sibling assignment; all required inputs are already included.

## Structure

| Path | Purpose |
| --- | --- |
| `run.py` | Run the complete offline study |
| `pipeline/config.py` | Explicit policy, constants and wrapper equivalence groups |
| `pipeline/data.py` | Hash checks, USD conversion, monthly observations, liquidity and eligibility |
| `pipeline/allocation.py` | Stabilized estimator, maximum net-Sharpe allocation, CVaR and minimum-turnover bands |
| `pipeline/engine.py` | Delayed orders, cash, costs, daily accounting and metrics |
| `pipeline/verify.py` | Independent saved-artifact and temporal controls |
| `pipeline/report.py` | Figures and a shared PDF/HTML/Markdown content model |
| `pipeline/qa_artifacts.py` | PDF rendering and document consistency checks |
| `pipeline/check_reproduction.py` | Clean-folder reproduction of the complete study |
| `pipeline/import_snapshot.py` | Explicit one-time import of the preceding input snapshot |
| `tests/` | Ten focused tests, including 100 random self-financing transitions |
| `data/` | Real frozen inputs, original source metadata and prepared monthly panels |
| `output/` | Signals, optimizer diagnostics, accounts, positions, tickets, metrics and verification |
| `figures/` | Four research figures and four typeset equation images |
| `report/` | Final research report in PDF, self-contained HTML and Markdown |
| `resources/archive/` | Historical initial experiment; excluded from Git |
| `resources/` | Assignment and design-scope documentation |

## Fund policy and deliberate scope

All 61 catalogue ETFs are candidates. Each month requires 61 consecutive monthly USD observations, 60 prior returns, a six-month median daily dollar volume of at least USD 1 million and at least 100 valid volume observations. Fixed equivalent-wrapper groups avoid selected duplicates. This is a retrospective surviving catalogue, not a point-in-time membership record.

The estimator retains Checkpoint B's Ledoit-Wolf covariance and data-driven common-mean shrinkage. The structural objective is maximum expected excess return after management and forecast trading costs, divided by volatility. Targets are long-only, fully invested, capped at 20% per ETF, with empirical 95% monthly CVaR no greater than 15%, including forecast costs. A nonpositive transformed opportunity uses the explicitly recorded minimum-risk fallback.

Both fund variants share the structural target stream. The forecast turnover reference is the previous structural target, not either account's actual drifted positions; this keeps the structural decision identical when testing the filter. Actual transaction costs use actual holdings and actual trades.

The full Checkpoint B mandate also considered shorts, leverage and underlying company/sector/country/economic-FX limits. This operational experiment disables shorts and leverage. It does not impose current underlying holdings on past decisions or claim historical look-through compliance. No dated historical composition archive is available. Those are explicit scope differences, not constraints silently declared satisfied. See `resources/design-decisions.md`.

## Trend and execution

The primary trend rule is fixed at ten months, matching the Module 7 discussion. At month-end, compare each eligible ETF's adjusted USD price with the average of its last ten monthly prices. Above the average, retain the structural target; at or below it, move that allocation to cash. Other ETFs do not receive the removed allocation. Cash stays inside the growth fund; the safety and inflation blocks are outside the study.

Signals execute at the first subsequent SPY-calendar close with actual quotes for potential holdings and controls. All actual buys and sells are independently checked for observed quotes; stale prices may be used only for valuation, up to seven calendar days. A delay beyond ten calendar days fails. Foreign closes and FX remain asynchronous; these are total-return accounting units, not certified live fills.

At a monthly decision, stay within three-percentage-point ETF/cash bands when possible. Otherwise an LP minimizes buys plus sells subject to ETF bands, the 20% cap and CVaR; cash returns to its desired target. A zero ETF target forces full exit. Weights may drift between decisions, so monthly caps and CVaR are not continuous or realized-loss guarantees.

Initial capital is one USD unit. Trading costs are 0.10% per dollar bought or sold; both legs count. The model solves for after-cost NAV before setting holdings. Fractional units are allowed. A fund management expense of 0.25% per year accrues ACT/365 proportionally against risky holdings and cash, without creating debt. Fund accounts pay this fee; SPY and VT controls do not pay an additional fund-management charge. Embedded ETF operating expenses already affect adjusted returns and are not deducted again.

Cash accrues the DGS3MO yield known strictly before the interval starts, times actual calendar days / 365. This is an assumed cash proxy, not the realized return of a traded Treasury fund or a verified brokerage deposit. No investor tax, market-impact, capacity, borrowing or FX-spread model is included. There is no forced terminal liquidation.

## Accounts, comparisons and robustness

Five accounts use the same main period and valuation calendar:

1. Initial fund buy-and-hold: buy the first structural allocation and let it drift.
2. Core fund: update structural targets and trade with bands.
3. Core fund plus ten-month trend: same structural targets, with the filter and cash.
4. SPY buy-and-hold: the assignment's S&P 500 benchmark.
5. VT buy-and-hold: an additional global-equity reference.

Metrics include CAGR, volatility, excess-return Sharpe, maximum drawdown, worst day, turnover, mean risky exposure and explicit costs. Volatility and Sharpe use 252 daily periods per year. Sharpe subtracts the same interval cash proxy. CAGR uses compounded wealth and elapsed calendar years. Initial costs occupy the first row with zero elapsed market interval. Drawdown includes the pre-cost initial capital. Cost sums are in original-capital units, not percentages of final NAV or annual expense rates.

Chronological segments are July 2019-December 2022 and January 2023-September 2026, with additional calendar-2020 and calendar-2022 summaries. Accounts continue across boundaries. Previous assignments and the discussion examined overlapping data; the later segment is not labeled untouched or prospective.

Fixed sensitivities test zero/ten/twenty-five basis-point costs, six/ten/twelve-month trend, exact targets without bands and an additional available common execution day. Cost alternatives recompute both the forecast-cost objective and actual costs, so they are not pure fee subtraction. The delayed scenario starts one common date later. No best-performing alternative replaces the primary policy.

Two diagnostics have limited interpretations:

- `exposure_diagnostic.csv` scales core returns with cash using the trend account's **full-sample** mean exposure. It is ex post, not an investable policy, a volatility match or causal timing attribution.
- `bootstrap.json` reports 2,000 paired stationary-block resamples of observed monthly account/cash returns, with six-month mean blocks. This is conditional resampling, not new real data, a null p-value, a complete parameter-selection correction or prospective evidence.

## Provenance and output verification

Raw prices end October 23, 2026. The experiment stops September 30, the last complete month in that frozen snapshot. No November data were generated or inferred. Vendor-adjusted histories and yields may have been revised. USD quotes do not eliminate the underlying investments' currency exposure.

`data/provenance.json` records imported hashes, sizes and origin paths. Origin paths document the import and are not runtime dependencies. Price, FX and universe hashes matched the previous source manifest. The daily volume history is an independently preserved source refresh; fourteen early PIBB11 rows lack dollar volume and are excluded without filling. Other copied-input hashes establish integrity, not vendor certification. The original liquidity-monthly file is retained for provenance; new eligibility is calculated from daily volume.

The checks reconstruct signals and eligibility, validate chronology, funding/caps/CVaR/bands, rebuild units from trade tickets and expense accrual, reconstruct NAV from market P&L/interest/costs, verify actual execution observations and independently recalculate saved metrics. Temporal controls poison future data and truncate histories, requiring earlier wealth paths to remain unchanged. Clean reproduction starts from no saved results. Test fixtures are explicitly artificial; none enter the study's price/return inputs.

The PDF is rendered and visually inspected in addition to automated text/bounds checks. `output/verification.json`, `unit_tests.txt`, `clean_reproduction.json`, `artifact_qa.json` and `run_summary.txt` record what was executed. These checks do not certify historical holdings, broker terms, vendor accuracy or future profitability.

## Submission status

The public repository contains the report, Python program, data, results and documentation. Use the cloneable URL above, ending in `.git`, in the Canvas comments.

The saved deadline is November 8, 2026 at 11:59 p.m.; the Canvas time zone remains unconfirmed. Final academic review and Canvas submission remain the student's responsibility. No Canvas submission has been made by this workflow.
