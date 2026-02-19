í@echo off
REM ============================================================
REM A/B TESTING MODE
REM Runs the bot in test mode with A/B testing framework enabled
REM Tests 26 strategy configurations simultaneously
REM ============================================================

echo ============================================================
echo A/B TESTING MODE - Strategy Comparison Framework
echo ============================================================
echo.
echo This will test 26 different strategy configurations:
echo   - 8 single strategies (isolation tests)
echo   - 6 strategy combinations
echo   - 5 entry parameter variations  
echo   - 4 exit parameter variations
echo   - 3 Binance OFI sensitivity tests
echo.
echo Each config uses a $100 virtual balance.
echo Summaries printed every 30 minutes.
echo Results saved to: ab_test_results/
echo.
echo Press Ctrl+C to stop and generate final report.
echo ============================================================
echo.

REM Set environment for A/B testing
set AB_TEST_ENABLED=true
set AB_TEST_SUMMARY_INTERVAL_MINUTES=30
set AB_TEST_STARTING_BALANCE=100

REM Disable live trading (test mode only)
set ENABLE_LIVE_TRADING=false

REM Start the bot in test mode with A/B testing
python main_bot_optimized.py --test --ab-test

REM Generate final report on exit
echo.
echo ============================================================
echo A/B Testing session ended.
echo Check ab_test_results/ for:
echo   - ab_test_log.json (full log)
echo   - ab_test_trades.csv (trade history)
echo   - ab_test_summary.csv (periodic summaries)
echo   - final_report.md (rankings and recommendations)
echo ============================================================
pause
í"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Ffile:///c:/Users/rovie%20segubre/btc_15min_options_bot/run_ab_test.bat:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot