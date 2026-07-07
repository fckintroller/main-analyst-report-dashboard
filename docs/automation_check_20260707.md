# Automation Check - 2026-07-07

Checked by: Codex
Workspace: `C:\claude cowork\01_projects\Anal_reports`

## Summary

The main Quant/Anal_reports scheduled jobs are registered and most core daily pipelines completed successfully on 2026-07-07.

Important status:

- Report/news collection: OK
- Daily market collection: OK
- All factor update: OK
- Consensus revision daily: OK
- Macro indicators daily: OK
- Regression signal daily: OK
- Discord morning notification: OK
- Kiwoom market-hours jobs: partially OK, with expected "not connected" defensive exits where Kiwoom was unavailable
- Investor minute collector: needs follow-up; scheduler last result is `255`

## Scheduler Snapshot

Core jobs with successful last result:

| Task | Last run | Last result | Next run |
|---|---|---:|---|
| `Anal_reports_Discord_Notify_0850` | 2026-07-07 08:50 | 0 | 2026-07-08 08:50 |
| `QuantConsensusRevisionDaily` | 2026-07-07 08:20 | 0 | 2026-07-08 08:20 |
| `QuantMacroIndicatorsDaily_0805` | 2026-07-07 08:05 | 0 | 2026-07-08 08:05 |
| `QuantDailyMarket_1610` | 2026-07-07 16:10 | 0 | 2026-07-08 16:10 |
| `QuantDailyNews_1700` | 2026-07-07 17:30 | 0 | 2026-07-08 17:30 |
| `QuantAllFactorsDaily` | 2026-07-07 18:20 | 0 | 2026-07-08 18:20 |
| `QuantFactorMasterPanelDaily` | 2026-07-07 08:40 | 0 | 2026-07-08 08:40 |
| `QuantMinuteTick_1540` | 2026-07-07 15:40 | 0 | 2026-07-08 15:40 |
| `QuantRegressionSignalDaily` | 2026-07-07 18:35 | 0 | 2026-07-08 18:35 |

Jobs with caveats:

| Task | Last result | Notes |
|---|---:|---|
| `KiwoomIntradayMarketFlow_MarketHours_10m` | 2 | Defensive exit because Kiwoom was not connected. Log shows `latest_market_flow.json` was not overwritten. |
| `KiwoomDecisionEngine_MarketHours_10m` | 0 | Latest checked market-hours decision engine task succeeded. |
| `KiwoomCandidateStockFlow_MarketHours_15m` | -1073741510 | Needs separate follow-up if candidate stock flow is required during market hours. |
| `KiwoomSessionHealth_10m` | -2147024703 | Likely scheduler/path or Kiwoom environment issue; not blocking non-Kiwoom quant pipelines. |
| `KiwoomSessionWatchdog_5m` | -2147024703 | Same class of issue as session health. |
| `KiwoomPreflight_0650` | -2147024703 | Needs follow-up before relying on morning Kiwoom preflight. |
| `QuantInvestorMinuteCollector` | 255 | Batch creates `logs\investor_minute_*.log`, but no matching log was present during this check. Needs follow-up on next market day. |

## Report And News Collection

`QuantDailyNews_1700` is enabled and completed successfully.

- Last run: 2026-07-07 17:30:02
- Last result: 0
- Next run: 2026-07-08 17:30:00
- Command: `run_daily_news.bat`

Observed outputs:

- `data\analyst_database.json` updated at 2026-07-07 17:30:02
- `data\analyst_database.json` contains 98 report records
- Latest report records include 2026-07-07 reports for S-Oil, DL이앤씨, 삼성전기, SK하이닉스, 한화오션

`run_daily_news.bat` runs:

1. `scripts\01_collect\report_crawler.py`
2. `scripts\01_collect\collect_stock_news_once.py`
3. `scripts\03_analyze\build_news_sentiment_factors.py`
4. `scripts\03_analyze\export_web_data.py`
5. `scripts\03_analyze\export_news_data.py`

## Log Checks

`logs\all_factor_update_20260707_182141.log` ended with:

- `ALL_FACTOR_UPDATE_STATUS=OK`
- `33 passed in 2.44s`
- `All factor pipeline OK`

`logs\daily_market_20260707_161002.log` ended with:

- `Daily market pipeline OK`

`logs\kiwoom_intraday_market_flow_20260707_153502.log` ended with:

- `Kiwoom not connected`
- `latest_market_flow.json not overwritten`
- `FAILED rc=2`

This is a controlled failure mode for missing Kiwoom connectivity.

## Follow-Up Items

1. Check `QuantInvestorMinuteCollector` on the next market day and verify whether `logs\investor_minute_*.log` is created.
2. Review Kiwoom scheduler failures returning `-2147024703` and `-1073741510` if Kiwoom automation is required tomorrow.
3. Consider making `run_daily_news.bat` write a timestamped `daily_news_*.log`, matching the other pipelines, so future report/news collection audits are direct.

