import streamlit as st
import pandas as pd
import anthropic
import base64
import json
import os
import plotly.express as px
from fpdf import FPDF
import tempfile

api_key = os.environ.get("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)
DATA_FILE = "data.csv"

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame(columns=["invoice", "description", "quantity", "unit_price", "total", "category"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def generate_pdf(df, fig_pie, selected_category):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "BookePaid - Financial Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Generated: {pd.Timestamp.now().strftime('%d %B %Y')}", ln=True, align="C")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Executive Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Total Documented Spend:   ${df['total'].sum():.2f}", ln=True)
    pdf.cell(0, 8, f"Unique Vendors / Invoices: {df['invoice'].nunique()}", ln=True)
    pdf.cell(0, 8, f"Total Line Items Audited:  {len(df)}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Allocation By Cost Center", ln=True)
    pdf.set_font("Helvetica", "", 11)
    categories = ["COGS", "Packaging", "Labour", "Overhead", "Other"]
    for cat in categories:
        if cat in df["category"].values:
            amount = df[df["category"] == cat]["total"].sum()
            pdf.cell(0, 8, f"{cat}: ${amount:.2f}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Line Item Detail", ln=True)
    pdf.set_font("Helvetica", "B", 9)
    col_widths = [50, 25, 25, 25, 30, 30]
    headers = ["Description", "Qty", "Unit Price", "Total", "Category", "Invoice"]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 7, str(row["description"])[:28], border=1)
        pdf.cell(col_widths[1], 7, str(row["quantity"]), border=1)
        pdf.cell(col_widths[2], 7, f"${row['unit_price']:.2f}", border=1)
        pdf.cell(col_widths[3], 7, f"${row['total']:.2f}", border=1)
        pdf.cell(col_widths[4], 7, str(row["category"]), border=1)
        pdf.cell(col_widths[5], 7, str(row["invoice"])[:18], border=1)
        pdf.ln()
    pdf.ln(6)

    with tempfile.TemporaryDirectory() as tmpdir:
        pie_path = os.path.join(tmpdir, "pie.png")
        fig_pie.write_image(pie_path, width=400, height=300)

        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Spend Distribution", ln=True)
        pdf.image(pie_path, w=130)

    return bytes(pdf.output())

# --- APP ---

st.title("Bookepaid - 💜💙")
st.subheader("AI-Powered Invoice Tracker")
st.write("An operational bridge transforming raw supplier expenses into structured, categorized accounting data.")

uploaded_file = st.file_uploader("Upload Invoice (PDF)", type=["pdf"])

if uploaded_file is not None:
    existing_df = load_data()
    if uploaded_file.name in existing_df["invoice"].values:
        st.warning(f"⚠️ {uploaded_file.name} has already been processed and saved.")
    else:
        pdf_bytes = uploaded_file.read()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        with st.spinner("Reading invoice..."):
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": base64_pdf
                                }
                            },
                            {
                                "type": "text",
                                "text": """Extract all line items from this invoice and return ONLY a JSON array.
                                Each object should have:
                                - description (string)
                                - quantity (number)
                                - unit_price (number)
                                - total (number)
                                - category: classify using these rules:
                                * COGS: raw materials, ingredients, packaging, stock, goods for resale,
                                    production-related setup fees
                                * Packaging: boxes, bags, labels, containers
                                * Labour: staff, services, training, consulting
                                * Overhead: rent, utilities, equipment rental, admin fees, software
                                * Other: anything that doesn't fit above
                                No markdown, no explanation. Just the JSON array."""
                            }
                        ]
                    }
                ]
            )

        raw = response.content[0].text
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            st.error(f"Could not parse response. Raw output was: {raw}")
            st.stop()

        items = json.loads(raw)
        new_df = pd.DataFrame(items)
        new_df["invoice"] = uploaded_file.name
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        save_data(combined_df)
        st.success("✅ Invoice processed and saved!")

df = load_data()

if not df.empty:
    st.markdown("---")
    st.subheader("📊 Accumulated Financial Ledger")
    st.dataframe(df, use_container_width=True)

    st.subheader("📈 Executive Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Documented Spend", f"${df['total'].sum():.2f}")
    col2.metric("Unique Vendors / Invoices", df["invoice"].nunique())
    col3.metric("Total Line Items Audited", len(df))

    categories = ["COGS", "Packaging", "Labour", "Overhead", "Other"]
    existing_categories = [c for c in categories if c in df["category"].values]

    if existing_categories:
        st.subheader("Allocation By Cost Center")
        cols = st.columns(len(existing_categories))
        for i, cat in enumerate(existing_categories):
            amount = df[df["category"] == cat]["total"].sum()
            cols[i].metric(cat, f"${amount:.2f}")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Spend Distribution")
            category_totals = df.groupby("category")["total"].sum().reset_index()
            fig_pie = px.pie(
                category_totals,
                values="total",
                names="category",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with chart_col2:
            st.subheader("Item Breakdown")
            selected_category = st.selectbox("Filter Cost Center", options=existing_categories)
            filtered_df = df[df["category"] == selected_category]
            fig_bar = px.bar(
                filtered_df,
                x="description",
                y="total",
                color="invoice",
                labels={"total": "Amount ($)", "description": "Line Item"},
                title=f"Distribution inside: {selected_category}"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # Export — placed here so fig_pie, fig_bar, selected_category are all defined
        st.markdown("---")
        st.subheader("📄 Export Report")
        if st.button("Generate PDF Report"):
            with st.spinner("Building report..."):
                pdf_output = generate_pdf(df, fig_pie, selected_category)
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_output,
                file_name=f"bookepaid_report_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )

else:
    st.info("💡 Upload your first supplier invoice PDF to see the automation dashboard compile in real time.")
