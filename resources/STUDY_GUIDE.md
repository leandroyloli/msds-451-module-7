# From portfolio design to automated trading

Earlier assignments defined the jobs of the portfolio, selected ETFs for the growth block, and studied how to divide capital among them. This assignment turns that allocation into a system that decides when to buy, sell and rebalance, and tests whether momentum improves the result after costs.

The narrative moves from **what to hold and how much to invest** to **how to operate and maintain the portfolio over time**.

The complete final assignment now lives directly in `C:/studing/msds-451-module-7`. The initial six-ETF experiment is retained separately in `resources/archive/initial-experiment.zip`. It is historical context, not the submission version. All authored documentation in the active project is in English.

## What the program does

The program considers all 61 ETFs in the preceding catalogue. At each month-end, it checks five years of returns, historical liquidity and equivalent funds, then recalculates structural weights using the stabilized estimator and net-Sharpe objective from Checkpoint B. It converts those weights into simulated trades, with three-percentage-point bands and costs on both purchases and sales.

A second account uses the same structural weights with a ten-month moving-average filter. An ETF above the average keeps its allocation. An ETF at or below the average moves its allocation to cash inside the growth fund. Other ETFs do not absorb that allocation. The safety and inflation blocks remain separate.

Signals execute only on a later date with actual observations for the traded instruments. Records include the signal, execution date, ETF, side, accounting units, dollar notional, cost, daily positions, cash and wealth. These are historical simulated orders; no live trades were sent.

## Continuity with the preceding work

The study retains the candidate catalogue, history/liquidity screens, equivalent-wrapper preference, 20% ETF target cap, stabilized mean/covariance estimates, net-Sharpe objective, empirical monthly CVaR limit and trading bands. This operational variant is long-only, without borrowing or short positions.

Checkpoint B also considered underlying company, sector, country and economic-currency limits. The available ETF compositions are recent snapshots, not historical records. Applying them to old decisions would introduce future information. This report therefore does not certify historical compliance with those look-through limits. The scope differences are explicit in `resources/design-decisions.md`.

The Module 7 discussion introduced the ten-month rule with a simplified minimum-variance optimizer and exact monthly weights. This assignment uses the preceding net-Sharpe objective, bands, CVaR and fund management expense. Its results can legitimately differ. The discussion and earlier assignments remain unchanged.

## Experiments

Five accounts use the same main period and valuation calendar:

1. The first structural fund allocation, bought once and held.
2. The fund with updated allocations and trading bands.
3. The fund with bands and the ten-month trend filter.
4. SPY buy-and-hold, meeting the required benchmark.
5. VT buy-and-hold, an additional global-equity reference.

Metrics include CAGR, annualized volatility, excess-return Sharpe, maximum drawdown, worst day, turnover, risky exposure and explicit costs. Chronological segments and sensitivities examine costs, trend windows, bands and execution delay. A winning alternative is not promoted after inspecting the results.

The bootstrap is explicitly labeled conditional resampling, not new real observations or prospective evidence. The fixed-exposure diagnostic uses the full sample's average exposure and is explicitly ex post; it is not a policy available in advance.

## Inputs and assumptions

Real historical observations were copied from Module 6 snapshots, with source metadata and integrity hashes. There was no new market-price download. The last saved price is October 23, 2026; the backtest ends September 30, 2026, the last complete available month. No November returns were invented.

Default assumptions include ten basis points per dollar bought or sold and a 0.25% annual fund management expense. Cash uses the three-month Treasury yield known before each accrual interval starts. This is a modeled cash proxy, not a traded fund or certified brokerage credit rate. The execution costs are assumptions, not verified broker quotes.

Limitations include a retrospective surviving catalogue, revised adjusted prices, asynchronous market closes, bounded prior-price use for valuation, unmodeled investor taxes/market impact and missing historical fund compositions. Overlapping data already examined in previous assignments are not called untouched or prospective evidence.

## Main files

Paths below are relative to the project root.

- `report/msds451-pa3.pdf`: final research report.
- `report/msds451-pa3.html`: self-contained HTML of the same study.
- `report/report.md`: editable generated text.
- `README.md`: complete installation, execution and testing instructions.
- `output/metrics.csv` and `run_summary.txt`: calculated results.
- `output/signals.csv` and `optimizer_diagnostics.csv`: eligibility, targets, trend and estimation timestamps.
- `output/*_trades.csv`, `*_weights.csv`, `*_account.csv` and `*_events.csv`: auditable trading histories.
- `output/verification.json`: accounting and temporal checks.
- `output/unit_tests.txt`: tests using explicitly artificial mechanism fixtures.
- `output/clean_reproduction.json`: clean-folder reproduction record.
- `output/artifact_qa.json`: PDF rendering and document checks.
- `output/cleanup_verification.json`: relocation, preservation and cleanup checks.

## Run

The checked-in delivery excludes installed Python environments. Follow the README to create an environment and install `requirements.txt`, then run:

```powershell
python run.py
python run.py --check
python -m unittest discover -s tests -v
python -m pipeline.qa_artifacts
```

Normal execution uses only files in this project. The one-time snapshot importer is not needed again. Original paths inside historical provenance records describe where files came from; they are not execution dependencies.

## Submission status

The local package contains the code, data, outputs, report and documentation.

The public repository is https://github.com/leandroyloli/msds-451-module-7. Its cloneable URL is https://github.com/leandroyloli/msds-451-module-7.git; use it in the Canvas comments. The saved deadline is November 8, 2026 at 11:59 p.m., with its time zone unconfirmed. Final academic review and Canvas submission remain with the student. No subagents were used.
