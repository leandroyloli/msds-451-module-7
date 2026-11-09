# Design scope fixed for this run

This is the operational extension requested after reviewing the first Module 7 baseline. It preserves earlier files and does not publish anything.

| Decision | Implementation | Reason / limit |
| --- | --- | --- |
| Narrative | Allocation becomes orders, positions and maintenance; trend is an added hypothesis | Continue the fund project rather than substitute an unrelated strategy |
| Catalogue | All 61 prior candidates, dynamically filtered | Existing fund context; retrospective survivor/metadata bias remains |
| Structural estimator | Checkpoint B common-mean shrinkage and Ledoit-Wolf covariance | Retain the preceding allocation approach |
| Structural objective | Maximum forecast net Sharpe, with explicit minimum-risk fallback | Retain allocation logic; estimated means remain uncertain |
| Cost reference in allocation | Previous structural target shared by both accounts | Isolate filter from separate allocator feedback; actual costs use actual trades |
| Long-only / no leverage | Mandatory for this operational variant | Avoid claiming unverifiable historical borrow availability |
| Target restrictions | 20% ETF cap; 95% empirical monthly CVaR at 15% | Model limits at monthly decisions; no continuous market-loss guarantee |
| Underlying holdings limits | No historical company/sector/country/economic-FX compliance claim | Current holdings cannot legitimately be inserted into past decisions |
| Trend | Ten-month adjusted-USD moving-average gate, matching discussion | Fixed main hypothesis, not selected as the best result |
| Cash | Removed allocations remain in growth-fund cash | No redistribution to positive ETFs; safety reserve stays separate |
| Bands | Minimum turnover within 3 pp; mandatory exits for zero targets | Continue the maintenance policy and model actual trading |
| Execution | Subsequent common observed close, with fresh-quote checks | Avoid same-close signals/fills and stale execution |
| Daily valuation | SPY calendar; at most 7-day prior observed USD value | Bounded carry for holidays; asynchronous closes remain a limitation |
| Cash rate | Yield strictly before interval start; ACT/365 proxy | Prevent using a yield published during or after the interval |
| Expenses | 10 bp per dollar bought/sold; 25 bp/year fund NAV accrual | Explicit assumptions; no duplicate embedded ETF expenses |
| Evaluation | July 2019-September 2026; chronological subperiods | Complete frozen months; no prospective holdout claim |
| Alternatives | Costs, trend windows, bands and delay fixed for diagnosis | Do not promote a winning backtest after looking at results |
| Discussion continuity | Same ten-month hypothesis; fuller optimizer/accounting here | The simplified discussion is preserved, and results legitimately differ |

No AGENTS.md files were found in the workspace search or checked ancestor paths before editing. No subagents were used. All writes for this version stay in this new package directory. Sibling source assignments and discussion files are read-only references.
