# BookePaid 💜💙
### AI-Powered Invoice Tracker & COGS Dashboard for Cafés and Food Businesses

BookePaid automates the painful manual process of extracting, categorising, and tracking supplier invoice data — giving small food and beverage businesses a real-time view of their cost of goods sold (COGS) without spreadsheets.



## Features

- **AI Invoice Extraction** — upload any supplier invoice PDF and Claude AI reads every line item automatically
- **Automatic Categorisation** — line items classified into COGS, Packaging, Labour, Overhead, or Other
- **Multi-Invoice Accumulation** — build a running financial ledger across all suppliers over time
- **COGS Trend Line** — visualise how your cost of goods evolves as new invoices come in
- **Plate Costing Tracker** — track the real cost of each menu item based on latest supplier prices, with pre-built templates for common café items
- **Executive Dashboard** — spend distribution charts and cost center breakdowns
- **PDF Export** — one-click financial report with charts and full line item detail
- **Password Protected** — each deployment is access-controlled for individual business use

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| AI Extraction | Anthropic Claude (claude-sonnet-4-6) |
| Data Storage | CSV (local persistence) |
| Charts | Plotly Express |
| PDF Generation | fpdf2 + kaleido |
| Deployment | Streamlit Community Cloud |
| Language | Python 3.14 |

---

## Project Structure

```
bookepaid/
├── app.py          # Main app and page routing
├── auth.py         # Password protection
├── data.py         # Data loading and persistence
├── invoice.py      # Claude API invoice extraction
├── pdf_export.py   # PDF report generation
├── plates.py       # Plate costing logic and defaults
└── requirements.txt
```

---

## How It Works

1. User uploads a supplier invoice PDF
2. The PDF is encoded and sent to Claude via the Anthropic API
3. Claude extracts all line items and returns structured JSON
4. Data is categorised, stored, and reflected across the dashboard
5. Plate costing automatically recalculates using the latest ingredient prices from invoices

---

## Built By

Juan Pablo Martinez — Finance & Data professional based in Melbourne, Australia.
Combining a background in commercial finance (CPA candidate) with applied AI development.

[LinkedIn](https://www.linkedin.com/in/juan2996/) · [GitHub](https://github.com/jotape96)
