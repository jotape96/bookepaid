import streamlit as st
import pandas as pd
import plotly.express as px
import os

from auth import check_password
from data import load_data, is_duplicate, append_invoice
from invoice import extract_invoice
from pdf_export import generate_pdf
from plates import (load_plates, save_plates, plates_exist,
                    get_latest_prices, calculate_plate_cost,
                    generate_plates_for_restaurant, RESTAURANT_TYPES)

# --- AUTH ---
check_password()

# --- CONFIG ---
st.set_page_config(page_title="BookePaid", page_icon="💜", layout="wide")

# ─────────────────────────────────────────
# ONBOARDING
# ─────────────────────────────────────────
if not plates_exist():
    st.title("Welcome to BookePaid 💜💙")
    st.subheader("Let's set up your menu")
    st.write("Tell us what kind of business you run and we'll generate a starter set of menu items automatically.")

    restaurant_type = st.selectbox("What type of restaurant or café are you?", options=RESTAURANT_TYPES)

    if st.button("Generate My Menu Templates ✨"):
        with st.spinner(f"Generating menu items for {restaurant_type}..."):
            try:
                plates = generate_plates_for_restaurant(restaurant_type)
                save_plates(plates)
                st.success(f"✅ Generated {len(plates)} menu items!")
                st.rerun()
            except Exception as e:
                st.error(f"Something went wrong: {e}")

    st.caption("You can edit, delete, or add your own items after setup.")
    st.stop()

# ─────────────────────────────────────────
# NAVIGATION
# ─────────────────────────────────────────
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

        st.markdown("---")
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
        st.subheader("📒 Accumulated Financial Ledger")
        st.dataframe(df, use_container_width=True)

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

    # ── Existing plates ──
    st.subheader("Menu Item Cost Tracker")
    for i, plate in enumerate(plates):
        result = calculate_plate_cost(plate, prices)
        with st.expander(f"{'🟢' if not result['has_unmatched'] else '🟡'} {plate['name']} — ${result['total_cost']:.2f}"):

            st.caption("Edit ingredients and quantities:")

            state_key = f"ingredients_{i}"
            if state_key not in st.session_state:
                st.session_state[state_key] = [
                    {"description": ing["description"], "quantity_kg": ing["quantity_kg"]}
                    for ing in plate["ingredients"]
                ]

            to_delete = None
            running_total = 0.0

            for j, (ingredient, breakdown_item) in enumerate(zip(st.session_state[state_key], result["breakdown"])):
                col1, col2, col3, col4, col5 = st.columns([3, 1, 2, 2, 1])

                with col1:
                    new_desc = st.text_input(
                        "Ingredient",
                        value=ingredient["description"],
                        key=f"desc_{i}_{j}",
                        label_visibility="collapsed"
                    )
                with col2:
                    new_qty = st.number_input(
                        "Grams",
                        value=round(ingredient["quantity_kg"] * 1000, 1),
                        min_value=0.1,
                        step=1.0,
                        key=f"qty_{i}_{j}",
                        label_visibility="collapsed"
                    )
                with col3:
                    if breakdown_item["candidates"]:
                        options = [c[0] for c in breakdown_item["candidates"]]
                        selected = st.selectbox(
                            "Match",
                            options=options,
                            key=f"match_{i}_{j}",
                            label_visibility="collapsed"
                        )
                        selected_price = dict(breakdown_item["candidates"])[selected]
                        cost = round(selected_price * (new_qty / 1000), 4)
                        running_total += cost
                    else:
                        st.caption("⚠️ No match")
                        selected_price = None
                        cost = None

                with col4:
                    if cost is not None:
                        st.metric("Cost", f"${cost:.4f}", label_visibility="visible")
                    else:
                        st.caption("—")

                with col5:
                    if st.button("🗑️", key=f"del_ing_{i}_{j}"):
                        to_delete = j

                st.session_state[state_key][j] = {
                    "description": new_desc,
                    "quantity_kg": new_qty / 1000
                }

            st.markdown(f"**Estimated Plate Cost: ${running_total:.4f}**")

            if to_delete is not None:
                st.session_state[state_key].pop(to_delete)
                st.rerun()

            if st.button("➕ Add Ingredient", key=f"add_ing_{i}"):
                st.session_state[state_key].append({"description": "New Ingredient", "quantity_kg": 0.1})
                st.rerun()

            st.markdown("")
            col_save, col_delete = st.columns([1, 1])
            with col_save:
                if st.button("💾 Save Changes", key=f"save_{i}"):
                    plates[i]["ingredients"] = [
                        {"description": ing["description"], "quantity_kg": ing["quantity_kg"]}
                        for ing in st.session_state[state_key]
                    ]
                    save_plates(plates)
                    del st.session_state[state_key]
                    st.success("✅ Saved!")
                    st.rerun()
            with col_delete:
                if st.button("🗑️ Delete Plate", key=f"delete_{i}"):
                    plates.pop(i)
                    save_plates(plates)
                    st.success("Deleted!")
                    st.rerun()

            if result["has_unmatched"]:
                st.caption("🟡 Some ingredients couldn't be matched to invoice data yet.")

    st.markdown("---")

    # ── Add new plate ──
    st.subheader("➕ Add New Menu Item")

    if "new_plate_ingredients" not in st.session_state:
        st.session_state.new_plate_ingredients = [{"description": "", "quantity_kg": 0.1}]

    new_name = st.text_input("Menu item name", placeholder="e.g. Flat White")

    st.caption("Ingredients:")
    to_delete_new = None
    for j, ingredient in enumerate(st.session_state.new_plate_ingredients):
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            st.session_state.new_plate_ingredients[j]["description"] = st.text_input(
                "Ingredient",
                value=ingredient["description"],
                placeholder="e.g. Espresso Beans",
                key=f"new_desc_{j}",
                label_visibility="collapsed"
            )
        with col2:
            new_qty = st.number_input(
                "Grams",
                value=round(ingredient["quantity_kg"] * 1000, 1),
                min_value=0.1,
                step=1.0,
                key=f"new_qty_{j}",
                label_visibility="collapsed"
            )
            st.session_state.new_plate_ingredients[j]["quantity_kg"] = new_qty / 1000
        with col3:
            if st.button("🗑️", key=f"del_new_{j}", help="Remove ingredient"):
                to_delete_new = j

    if to_delete_new is not None:
        st.session_state.new_plate_ingredients.pop(to_delete_new)
        st.rerun()

    if st.button("➕ Add Ingredient", key="add_new_ing"):
        st.session_state.new_plate_ingredients.append({"description": "", "quantity_kg": 0.1})
        st.rerun()

    st.markdown("")
    if st.button("💾 Save New Menu Item"):
        if new_name and any(ing["description"] for ing in st.session_state.new_plate_ingredients):
            plates.append({
                "name": new_name,
                "ingredients": st.session_state.new_plate_ingredients
            })
            save_plates(plates)
            del st.session_state.new_plate_ingredients
            st.success(f"✅ {new_name} saved!")
            st.rerun()
        else:
            st.error("Please enter a name and at least one ingredient.")

    st.markdown("---")
    if st.button("🔄 Reset All Menu Templates"):
        if os.path.exists("plates.json"):
            os.remove("plates.json")
        st.success("Reset! Refresh to run onboarding again.")
        st.rerun()