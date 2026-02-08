# ICT Trading System Webhook Testing Guide

## Sample Alert Payload

A sample alert payload is provided in `sample_alert.json`. You can send it to your webhook endpoint using curl:

```bash
curl -X POST "https://your-domain/api/webhook/alert?secret=your-webhook-secret" \
  -H "Content-Type: application/json" \
  -d @sample_alert.json
```
Replace `your-domain` and `your-webhook-secret` with your actual values.

---

## Postman Collection

A ready-to-import Postman collection is provided as `ICT_Trading_System_Webhook_Test.postman_collection.json`.

### How to Use:
1. Open Postman.
2. Click "Import" and select the `ICT_Trading_System_Webhook_Test.postman_collection.json` file.
3. Open the "Send Test Alert" request.
4. Edit the URL to match your deployment (replace `your-domain` and `your-webhook-secret`).
5. Click "Send".
6. Check your backend logs, database, and Telegram for the result.

---

## What to Expect
- A new signal should appear in your database.
- An AI analysis record should be created.
- A Telegram alert should be sent.
- Logs should show successful processing.

If there’s an error (e.g., wrong secret, malformed payload), you’ll see an error in the response and in your logs.

---

## Advanced Testing
- Try sending a malformed payload (e.g., remove a required field) to verify error handling.
- Try a low-confidence or low-confluence signal to confirm it is dropped.

---

For troubleshooting or further automation, see the main project README.
