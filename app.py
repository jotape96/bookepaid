import streamlit as st
import pandas as pd
import plotly.express as px

from auth import check_password
from data import load_data, is_duplicate, append_invoice
from invoice import extract_invoice
from pdf_export import generate_pdf
from plates import load_plates, save_plates, get_latest_prices, calculate_plate_cost

# --- AUTH ---
check_password()

# --- CONFIG ---
st.set_page_config(page_title="BookePaid", page_icon="💜", layout="wide")

# --- NAVIGATION ---
st.sidebar.title("BookePaid 💜💙")
page = st.sidebar.radio("Navigate", ["📥 Invoice Upload", "📊 Dashboard", "🍽️ Plate Costing"])

# ─────────────────────────────────────────
# PAGE 1: INVOICE UPLOAD
# ─────────────────────────────────────────
if page == "📥 Invoice Upload":
    st.title("📥 Invoice Upload")
    st.write("Upload a supplier invoice PDF and BookePaid will extract and categorise every line item automatically.")

    uploaded_file = st.file_uploader("Upload Invoice (PDF)", type=["pdf"])

    if uploaded_file is not None:
        if is_duplicate(uploaded_file.name):
            st.warning(f"⚠️ {uploaded_file.name} has already been processed.")
        else:
            with st.spinner("Reading invoice with AI..."):
                try:
                    pdf_bytes = uploaded_file.read()
                    new_df = extract_invoice(pdf_bytes, uploaded_file.name)
                    append_invoice(new_df)
                    st.success("✅ Invoice processed and saved!")
                    st.dataframe(new_df, use_container_width=True)
                except ValueError as e:
                    st.error(f"Could not process invoice: {e}")

# ─────────────────────────────────────────
# PAGE 2: DASHBOARD
# ─────────────────────────────────────────
elif page == "📊 Dashboard":
    st.title("📊 Dashboard")

    df = load_data()

    if df.empty:
        st.info("💡 Upload your first invoice to see the dashboard.")
    else:
        # Executive Summary
        st.subheader("📈 Executive Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Documented Spend", f"${df['total'].sum():.2f}")
        col2.metric("Unique Vendors / Invoices", df["invoice"].nunique())
        col3.metric("Total Line Items Audited", len(df))

        # Cost Center Metrics
        categories = ["COGS", "Packaging", "Labour", "Overhead", "Other"]
        existing_categories = [c for c in categories if c in df["category"].values]

        if existing_categories:
            st.subheader("Allocation By Cost Center")
            cols = st.columns(len(existing_categories))
            for i, cat in enumerate(existing_categories):
                amount = df[df["category"] == cat]["total"].sum()
                cols[i].metric(cat, f"${amount:.2f}")

        st.markdown("---")

        # Charts
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
            st.subheader("Granular Item Breakdown")
            if existing_categories:
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

        # COGS Trend Line
        st.markdown("---")
        st.subheader("📈 COGS Trend Over Time")
        cogs_df = df[df["category"] == "COGS"].copy()
        if not cogs_df.empty and "date" in cogs_df.columns:
            cogs_df["date"] = pd.to_datetime(cogs_df["date"], errors="coerce")
            cogs_trend = cogs_df.groupby("date")["total"].sum().reset_index()
            cogs_trend = cogs_trend.sort_values("date")
            fig_trend = px.line(
                cogs_trend,
                x="date",
                y="total",
                markers=True,
                labels={"total": "COGS ($)", "date": "Invoice Date"},
                title="Total COGS by Invoice Date"
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("COGS trend will appear once invoices with dates are uploaded.")

        st.markdown("---")

        # Full Ledger
        st.subheader("📒 Accumulated Financial Ledger")
        st.dataframe(df, use_container_width=True)

        # PDF Export
        st.markdown("---")
        st.subheader("📄 Export Report")
        if st.button("Generate PDF Report"):
            with st.spinner("Building report..."):
                pdf_output = generate_pdf(df, fig_pie)
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_output,
                file_name=f"bookepaid_report_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )

# ─────────────────────────────────────────
# PAGE 3: PLATE COSTING
# ─────────────────────────────────────────
elif page == "🍽️ Plate Costing":
    st.title("🍽️ Plate Costing")
    st.write("Track the cost of each menu item based on your latest supplier prices.")

    df = load_data()
    prices = get_latest_prices(df)
    plates = load_plates()

    if df.empty:
        st.info("💡 Upload invoices first so BookePaid can match ingredient prices.")

    # Show costing for each plate
    st.subheader("Menu Item Cost Tracker")
    for i, plate in enumerate(plates):
        result = calculate_plate_cost(plate, prices)
        with st.expander(f"{'🟢' if not result['has_unmatched'] else '🟡'} {plate['name']} — ${result['total_cost']:.2f}"):
            breakdown_df = pd.DataFrame(result["breakdown"])
            st.dataframe(breakdown_df, use_container_width=True)
            if result["has_unmatched"]:
                st.caption("🟡 Some ingredients couldn't be matched to invoice data yet.")

    st.markdown("---")

    # Add custom plate
    st.subheader("➕ Add a Custom Plate")
    new_name = st.text_input("Plate name")
    st.caption("Enter ingredients one per line as: Ingredient Name, quantity_kg")
    ingredients_input = st.text_area("Ingredients", placeholder="Espresso Beans, 0.018\nFull Cream Milk, 0.15")

    if st.button("Save Plate"):
        if new_name and ingredients_input:
            lines = ingredients_input.strip().split("\n")
            ingredients = []
            for line in lines:
                parts = line.split(",")
                if len(parts) == 2:
                    ingredients.append({
                        "description": parts[0].strip(),
                        "quantity_kg": float(parts[1].strip())
                    })
            if ingredients:
                plates.append({"name": new_name, "ingredients": ingredients})
                save_plates(plates)
                st.success(f"✅ {new_name} saved!")
                st.rerun()
            else:
                st.error("Could not parse ingredients. Use format: Name, quantity")
        else:
            st.error("Please enter a plate name and ingredients.")
