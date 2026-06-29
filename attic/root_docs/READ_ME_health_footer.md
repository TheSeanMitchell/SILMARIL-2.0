# Health Footer Now Displays

The health/status footer at the bottom of the page was defined but never called.

**Fixed:** added `renderHealth()` to the load cycle. Now you'll see at the bottom:

```
PROJECT HEALTH · last sim run: Jun 22, 2025 8:45 PM (2m ago) · books live: 
crypto/stock/metal/energy · feeds: price+ccxt+news active, metals/energy via API 
keys · data: internal paper sim (Alpaca paper + live shown separately when wired)
```

Shows:
- When the last sim cycle ran and how long ago
- Which books are active (all 4)
- Which feeds are live (prices, CCXT, news; metals/energy via your API keys)
- Data source note (internal lab, not production)

Updates on each page load.
