# TradingView Pine Script Installation Guide

1. Open TradingView and go to the chart of your desired symbol.
2. Click on "Pine Editor" at the bottom of the screen.
3. Copy the contents of `ict_detector.pine` into the Pine Editor.
4. Click "Add to Chart".
5. Set your desired timeframes and parameters in the script settings.
6. Set up an alert:
   - Click the "Alert" button (clock icon).
   - Choose the ICT indicator and select the alert condition.
   - Set alert action to "Webhook URL" and paste your FastAPI endpoint (e.g., `http://your-server:8000/api/webhook/receive?secret=YOUR_SECRET`).
   - Use the default JSON message or customize as needed.
7. Save and enable the alert.

**Note:** Only high-confidence, multi-confluence setups will trigger alerts.
