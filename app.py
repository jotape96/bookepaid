import streamlit as st
import pandas as pd
import plotly.express as px
import os
from data import (load_data, is_duplicate_invoice,
                  append_invoice, snapshot_plate_costs,
                  load_plate_history)
from auth import check_password
from invoice import extract_invoice
from pdf_export import generate_pdf
from plates import (load_plates, save_plates, plates_exist,
                    get_latest_prices, calculate_plate_cost,
                    generate_plates_for_restaurant, RESTAURANT_TYPES)
from auth import check_auth

# --- AUTH ---
user = check_auth()

# --- CONFIG ---
st.set_page_config(page_title="BookepAId", page_icon="💜", layout="wide")

# ─────────────────────────────────────────
# ONBOARDING
# ─────────────────────────────────────────
if not plates_exist():
    st.title("Welcome to BookepAId 💜💙")
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
st.sidebar.title("BookepAId 💜💙")
page = st.sidebar.radio("Navigate", ["📥 Invoice Upload", "📊 Dashboard", "🍽️ Plate Costing"])

# ─────────────────────────────────────────
# PAGE 1: INVOICE UPLOAD
# ─────────────────────────────────────────
if page == "📥 Invoice Upload":
    st.title("📥 Invoice Upload")
    st.write("Upload a supplier invoice PDF and BookePaid will extract and categorise every line item automatically.")

    uploaded_file = st.file_uploader("Upload Invoice (PDF)", type=["pdf"])

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()

        with st.spinner("Reading invoice with AI..."):
            try:
                file_type = uploaded_file.type
                if file_type == "application/pdf":
                    new_df = extract_invoice(file_bytes, uploaded_file.name)
                else:
                    new_df = extract_invoice_image(file_bytes, file_type, uploaded_file.name)

                invoice_number = new_df["invoice_number"].iloc[0] if "invoice_number" in new_df.columns else "UNKNOWN"
                supplier = new_df["supplier"].iloc[0] if "supplier" in new_df.columns else "UNKNOWN"

                if is_duplicate_invoice(invoice_number, supplier):
                    st.warning(f"⚠️ Invoice {invoice_number} from {supplier} has already been processed.")
                    existing = load_data()
                    prev = existing[existing["invoice_number"] == invoice_number]
                    if not prev.empty:
                        st.caption("Previous extraction:")
                        st.dataframe(prev, use_container_width=True)
                    if st.button("🔄 Reprocess anyway"):
                        st.session_state["force_reprocess"] = invoice_number
                
                if not is_duplicate_invoice(invoice_number, supplier) or \
                   st.session_state.get("force_reprocess") == invoice_number:
                    st.success("✅ Extracted — please review before saving:")
                    st.dataframe(new_df, use_container_width=True)

                    if st.button("💾 Confirm and Save"):
                        append_invoice(new_df)
                        invoice_date = new_df["date"].iloc[0] if "date" in new_df.columns else str(pd.Timestamp.now().date())
                        snapshot_plate_costs(invoice_date)
                        st.session_state.pop("force_reprocess", None)
                        st.success("✅ Invoice saved!")
                        st.rerun()

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
            st.subheader("Item Breakdown")
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
        st.subheader("📈 Plate Cost Trend")

        history_df = load_plate_history()

        if history_df.empty:
            st.info("Plate cost history will appear after uploading invoices.")
        else:
            plate_names = history_df["plate"].unique().tolist()
            selected_plate = st.selectbox("Select Menu Item", options=plate_names)
            
            filtered = history_df[history_df["plate"] == selected_plate].copy()
            filtered["date"] = pd.to_datetime(filtered["date"], errors="coerce")
            filtered = filtered.sort_values("date")

            fig_trend = px.line(
                filtered,
                x="date",
                y="cost",
                markers=True,
                labels={"cost": "Plate Cost ($)", "date": "Invoice Date"},
                title=f"Cost trend — {selected_plate}"
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # Keep raw COGS trend below
        st.markdown("---")
        st.subheader("📦 Raw COGS Trend")
        cogs_df = df[df["category"] == "COGS"].copy()
        if not cogs_df.empty and "date" in cogs_df.columns:
            cogs_df["date"] = pd.to_datetime(cogs_df["date"], errors="coerce")
            cogs_trend = cogs_df.groupby("date")["total"].sum().reset_index()
            fig_cogs = px.line(
                cogs_trend,
                x="date",
                y="total",
                markers=True,
                labels={"total": "COGS ($)", "date": "Invoice Date"},
                title="Total COGS by Invoice Date"
            )
            st.plotly_chart(fig_cogs, use_container_width=True)
        else:
            st.info("COGS trend will appear once invoices with dates are uploaded.")

        st.markdown("---")
        st.subheader("📁 Export for Accountant")
        
        col_from, col_to = st.columns(2)
        with col_from:
            date_from = st.date_input("From", value=pd.Timestamp.now().date().replace(month=1, day=1))
        with col_to:
            date_to = st.date_input("To", value=pd.Timestamp.now().date())

        gst_rate = st.number_input("GST Rate (%)", value=10.0, step=0.5) / 100

        filtered_export = df.copy()
        filtered_export["date"] = pd.to_datetime(filtered_export["date"], errors="coerce")
        filtered_export = filtered_export[
            (filtered_export["date"] >= pd.Timestamp(date_from)) &
            (filtered_export["date"] <= pd.Timestamp(date_to))
        ]

        # Add GST columns
        filtered_export["gst_amount"] = (filtered_export["total"] * gst_rate / (1 + gst_rate)).round(2)
        filtered_export["total_ex_gst"] = (filtered_export["total"] - filtered_export["gst_amount"]).round(2)
        filtered_export["total_inc_gst"] = filtered_export["total"].round(2)

        # Reorder columns for accountant
        export_columns = ["date", "invoice", "description", "quantity", "unit_price", 
                         "total_ex_gst", "gst_amount", "total_inc_gst", "category"]
        export_columns = [c for c in export_columns if c in filtered_export.columns]
        filtered_export = filtered_export[export_columns]

        st.caption(f"{len(filtered_export)} line items in selected range")
        
        # Summary totals
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ex GST", f"${filtered_export['total_ex_gst'].sum():.2f}")
        col2.metric("GST Amount", f"${filtered_export['gst_amount'].sum():.2f}")
        col3.metric("Total Inc GST", f"${filtered_export['total_inc_gst'].sum():.2f}")

        csv = filtered_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download CSV",
            data=csv,
            file_name=f"bookepaid_export_{date_from}_{date_to}.csv",
            mime="text/csv"
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

            for j, ingredient in enumerate(st.session_state[state_key]):
                key = ingredient["description"].lower().strip()
                candidates = [(pk, pv) for pk, pv in prices.items()
                             if key in pk or pk in key]
                candidates.sort(key=lambda x: x[1], reverse=True)
                
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
                    if candidates:
                        options = [c[0] for c in candidates]
                        selected = st.selectbox(
                            "Match",
                            options=options,
                            key=f"match_{i}_{j}",
                            label_visibility="collapsed"
                        )
                        selected_price = dict(candidates)[selected]
                        cost = round(selected_price * (new_qty / 1000), 4)
                        running_total += cost
                    else:
                        st.caption("⚠️ No match")
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