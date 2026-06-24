## BookePaid 💜💙
---
AI-Powered Invoice Tracker, COGS Dashboard & Menu Costing for Cafés and Food Businesses

BookePaid automates the painful manual process of extracting, categorising, and tracking supplier invoice data — giving small food and beverage businesses a real-time view of their cost of goods sold (COGS), plate margins, and supplier price trends without spreadsheets or manual data entry.


Live Demo

🔗 bookepaid.streamlit.app (access code required — contact for demo access)


Features

Core


AI Invoice Extraction — upload any supplier invoice PDF or photo and Claude AI reads every line item automatically, normalising units and stripping quantity descriptors from ingredient names
Automatic Categorisation — line items classified into COGS, Packaging, Labour, Overhead, or Other
Duplicate Detection — invoices identified by invoice number + supplier, not filename — catches the same invoice uploaded as both PDF and photo
Multi-Invoice Accumulation — build a running financial ledger across all suppliers over time, sorted chronologically


Dashboard


Executive Summary — total spend, invoice count, line items audited
Cost Center Allocation — dynamic metrics per category based on actual data
Spend Distribution Chart — donut chart showing category breakdown
Granular Item Breakdown — bar chart filterable by cost center
Raw COGS Trend — total COGS over time as invoices accumulate


Plate Costing


AI Menu Onboarding — new businesses select their restaurant type and Claude generates 8 typical menu items with realistic ingredient quantities
Real-time Plate Costing — ingredient costs pulled from latest invoice prices automatically
Conservative Costing — when multiple ingredient matches exist, uses most expensive for safety margin
Ingredient Selector — when multiple matches exist (e.g. Full Cream vs Oat Milk), owner selects which applies
Plate Cost Trend — line chart showing how each plate's cost evolves as supplier prices change
Selling Price & Margin — owners set selling prices and see margin % per plate with health indicators


Role-Based Access


Owner — full access including margins, selling prices, CSV export, PDF reports, user management
Manager — invoice upload, dashboard view, plate editing — no financial controls


Compliance & Export


Export for Accountant — date-range filtered CSV with GST breakdown (ex-GST, GST amount, inc-GST)
PDF Financial Report — summary, cost center breakdown, full line item table, spend distribution chart



Tech Stack

LayerTechnologyFrontendStreamlitAI ExtractionAnthropic Claude (claude-sonnet-4-6)DatabaseSupabase (PostgreSQL)ChartsPlotly ExpressPDF Generationfpdf2 + kaleidoDeploymentStreamlit Community CloudLanguagePython 3.14


Architecture

bookepaid/
├── app.py          # Main app, page routing, role-based UI
├── auth.py         # Login system using User/Owner/Manager classes
├── models.py       # OOP class hierarchy — User, Owner, Manager, Business
├── database.py     # Supabase client initialisation
├── data.py         # Invoice and line item data layer (Supabase)
├── invoice.py      # Claude API invoice extraction (PDF + image)
├── plates.py       # Plate costing logic, Supabase read/write
├── pdf_export.py   # PDF report generation
└── requirements.txt

Class Design (OOD)

User (base class)
├── name, email, password, business_id, role
├── login() — returns Owner or Manager instance
└── logout()
    │
    ├── Owner (inherits User)
    │   ├── export_csv()
    │   ├── set_selling_price()
    │   └── manage_users()
    │
    └── Manager (inherits User)
        ├── upload_invoice()
        └── edit_plates()

Business
├── name, type, business_id
├── summary()
└── add_user()

Database Schema (Supabase)

businesses → users → (owner/manager)
          → invoices → line_items
          → plates → ingredients
          → plate_history


How It Works


Business owner signs up — business and owner account created in Supabase
Owner invites manager — manager account linked to same business
Manager uploads supplier invoice (PDF or photo)
Claude extracts line items, normalises units, categorises each item
Data saved to Supabase under the business's isolated data scope
Plate costs recalculate automatically using latest ingredient prices
Owner reviews dashboard, margins, and exports for accountant



Roadmap

v1.1 — Pilot (Current)


 AI invoice extraction (PDF + photo)
 Multi-business Supabase backend
 Role-based access (Owner / Manager)
 Plate costing with margin tracking
 Accountant CSV export with GST breakdown
 PDF financial report


v1.2 — Planned


 Fuzzy ingredient matching (rapidfuzz) to prevent cross-contamination
 Menu photo onboarding — upload a photo of your menu to auto-generate plates
 Selling price margin alert — notify when COGS increase shrinks margin below threshold
 Mobile optimisation


v2.0 — Future


 Annual Compliance Report — full year PDF with BAS-ready GST reconciliation, supplier summary, month-by-month COGS trend, and complete line item ledger. Designed to be audit-ready and handed directly to accountants at EOFY.
 Xero / MYOB / QuickBooks integration — push categorised invoices directly to accounting software
 POS integration — connect sales data for true margin analysis without manual price entry
 Multi-location support — franchise and multi-site café groups
 Cash flow forecasting — predict quiet periods and flag when financing may be needed
 Financing referral — connect cafés experiencing cash flow gaps with business lenders (Prospa, Moula) using invoice data for pre-qualification

---

## Built By

Juan Pablo Martinez — Finance & Data professional based in Melbourne, Australia.
Combining a background in commercial finance (CPA candidate) with applied AI development.

[LinkedIn](https://www.linkedin.com/in/juan2996/) · [GitHub](https://github.com/jotape96)
