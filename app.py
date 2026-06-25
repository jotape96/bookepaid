import streamlit as st
import pandas as pd
import plotly.express as px
import os

from auth import check_auth
from data import (load_data, is_duplicate_invoice, save_invoice,
                  save_line_items, snapshot_plate_costs, load_plate_history)
from invoice import extract_invoice, extract_invoice_image
from pdf_export import generate_pdf
from plates import (load_plates, save_plate, update_plate, delete_plate,
                    plates_exist, get_latest_prices, calculate_plate_cost,
                    generate_plates_for_restaurant, extract_plates_from_menu,
                    RESTAURANT_TYPES)

# --- AUTH ---
user = check_auth()

# --- CONFIG ---
st.set_page_config(page_title="BookepAId", page_icon="💜", layout="wide")

business_id = user.business_id

# ─────────────────────────────────────────
# ONBOARDING — runs once if no plates exist
# ─────────────────────────────────────────
if not plates_exist(business_id):
    st.title("Welcome to BookePaid 💜💙")
    st.subheader("Let's set up your menu")
    st.write("Tell us what kind of business you run and we'll generate starter menu items automatically.")

    tab1, tab2 = st.tabs(["📷 Upload your menu", "🍽️ Choose restaurant type"])

    with tab1:
        st.write("Take a photo of your menu and we'll extract your dishes automatically.")
        menu_file = st.file_uploader("Upload menu photo", type=["jpg", "jpeg", "png", "pdf"])

        if menu_file is not None:
            if st.button("Generate from Menu ✨"):
                with st.spinner("Reading your menu..."):
                    try:
                        file_bytes = menu_file.read()
                        plates = extract_plates_from_menu(file_bytes, menu_file.type)
                        for plate in plates:
                            save_plate(plate, business_id)
                        st.success(f"✅ Found {len(plates)} menu items!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Something went wrong: {e}")

    with tab2:
        st.write("Tell us what kind of business you run and we'll generate typical menu items.")
        restaurant_type = st.selectbox("What type of restaurant or café are you?", options=RESTAURANT_TYPES)

        if st.button("Generate My Menu Templates ✨"):
            with st.spinner(f"Generating menu items for {restaurant_type}..."):
                try:
                    plates = generate_plates_for_restaurant(restaurant_type)
                    for plate in plates:
                        save_plate(plate, business_id)
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
st.sidebar.caption(f"👤 {user.name} — {user.role.capitalize()}")
page = st.sidebar.radio("Navigate", ["📥 Invoice Upload", "📊 Dashboard", "🍽️ Plate Costing"])

if st.sidebar.button("🚪 Logout"):
    user.logout()
    st.rerun()

# ─────────────────────────────────────────
# PAGE 1: INVOICE UPLOAD
# ─────────────────────────────────────────
if page == "📥 Invoice Upload":
    st.title("📥 Invoice Upload")
    st.write("Upload a supplier invoice — PDF or photo.")

    uploaded_file = st.file_uploader("Upload Invoice", type=["pdf", "jpg", "jpeg", "png"])

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
                date = new_df["date"].iloc[0] if "date" in new_df.columns else str(pd.Timestamp.now().date())

                if is_duplicate_invoice(invoice_number, supplier, business_id):
                    st.warning(f"⚠️ Invoice {invoice_number} from {supplier} has already been processed.")
                    if st.button("🔄 Reprocess anyway"):
                        st.session_state["force_reprocess"] = invoice_number
                else:
                    st.session_state["force_reprocess"] = invoice_number

                if st.session_state.get("force_reprocess") == invoice_number:
                    st.success("✅ Extracted — please review before saving:")
                    st.dataframe(new_df, use_container_width=True)

                    if st.button("💾 Confirm and Save"):
                        invoice_id = save_invoice(invoice_number, supplier, str(date)[:10],
                                                  uploaded_file.name, business_id)
                        save_line_items(new_df, invoice_id, business_id)
                        snapshot_plate_costs(str(date)[:10], business_id)
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

    df = load_data(business_id)

    if df.empty:
        st.info("💡 Upload your first invoice to see the dashboard.")
    else:
        st.subheader("📈 Executive Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Documented Spend", f"${df['total'].sum():.2f}")
        col2.metric("Unique Invoices", df["invoice_id"].nunique() if "invoice_id" in df.columns else "—")
        col3.metric("Total Line Items", len(df))

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
                    labels={"total": "Amount ($)", "description": "Line Item"},
                    title=f"Distribution inside: {selected_category}"
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        # Plate Cost Trend
        st.markdown("---")
        st.subheader("📈 Plate Cost Trend")
        history_df = load_plate_history(business_id)

        if history_df.empty:
            st.info("Plate cost history will appear after uploading invoices.")
        else:
            plates = load_plates(business_id)
            plate_names = history_df["plate_name"].unique().tolist()
            selected_plate = st.selectbox("Select Menu Item", options=plate_names)
            filtered = history_df[history_df["plate_name"] == selected_plate].copy()
            filtered = filtered.sort_values("date")
            fig_trend = px.line(
                filtered,
                x="date",
                y="cost",
                markers=True,
                labels={"cost": "Plate Cost ($)", "date": "Invoice Date"},
                title=f"Cost vs Selling Price  — {selected_plate}"
            )
            if user.role == "owner":
                plate_data = next((p for p in plates if p["name"] == selected_plate), None)
                if plate_data and plate_data.get("selling_price", 0) > 0:
                    selling_price = plate_data["selling_price"]
                    fig_trend.add_hline(
                        y=selling_price,
                        line_dash="dash",
                        line_color="green",
                        annotation_text=f"Selling Price ${selling_price:.2f}",
                        annotation_position="top right"
                    )
                    # Add margin zone shading
                    fig_trend.add_hrect(
                        y0=filtered["cost"].max(),
                        y1=selling_price,
                        fillcolor="green",
                        opacity=0.05,
                        line_width=0
                    )
            st.plotly_chart(fig_trend, use_container_width=True)

        # Raw COGS Trend
        st.markdown("---")
        st.subheader("📦 Raw COGS Trend")
        cogs_df = df[df["category"] == "COGS"].copy()
        if not cogs_df.empty:
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

        # Margin Overview — Owner only
        if user.role == "owner":
            st.markdown("---")
            st.subheader("💰 Menu Margin Overview")
            plates = load_plates(business_id)
            prices = get_latest_prices(df)
            margin_rows = []
            for plate in plates:
                result = calculate_plate_cost(plate, prices)
                if result["selling_price"] > 0:
                    margin_rows.append({
                        "Menu Item": plate["name"],
                        "Cost ($)": f"${result['total_cost']:.2f}",
                        "Selling Price ($)": f"${result['selling_price']:.2f}",
                        "Margin ($)": f"${result['margin']:.2f}" if result["margin"] is not None else "—",
                        "Margin (%)": f"{result['margin_pct']}%" if result["margin_pct"] is not None else "—",
                        "Status": "🟢 Healthy" if result["margin_pct"] and result["margin_pct"] >= 65
                                  else "🟡 Watch" if result["margin_pct"] and result["margin_pct"] >= 50
                                  else "🔴 At Risk"
                    })
            if margin_rows:
                st.dataframe(pd.DataFrame(margin_rows), use_container_width=True)
            else:
                st.info("Set selling prices in Plate Costing to see margin analysis.")

        # Full Ledger
        st.markdown("---")
        st.subheader("📒 Accumulated Financial Ledger")
        st.dataframe(df, use_container_width=True)

        # Export — Owner only
        if user.role == "owner":
            st.markdown("---")
            st.subheader("📁 Export for Accountant")
            col_from, col_to = st.columns(2)
            with col_from:
                date_from = st.date_input("From", value=pd.Timestamp.now().date().replace(month=1, day=1))
            with col_to:
                date_to = st.date_input("To", value=pd.Timestamp.now().date())

            gst_rate = st.number_input("GST Rate (%)", value=10.0, step=0.5) / 100

            filtered_export = df.copy()
            filtered_export = filtered_export[
                (filtered_export["date"] >= pd.Timestamp(date_from)) &
                (filtered_export["date"] <= pd.Timestamp(date_to))
            ]
            filtered_export["gst_amount"] = (filtered_export["total"] * gst_rate / (1 + gst_rate)).round(2)
            filtered_export["total_ex_gst"] = (filtered_export["total"] - filtered_export["gst_amount"]).round(2)
            filtered_export["total_inc_gst"] = filtered_export["total"].round(2)

            export_cols = ["date", "description", "quantity", "unit_price",
                          "total_ex_gst", "gst_amount", "total_inc_gst", "category"]
            export_cols = [c for c in export_cols if c in filtered_export.columns]

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Ex GST", f"${filtered_export['total_ex_gst'].sum():.2f}")
            col2.metric("GST Amount", f"${filtered_export['gst_amount'].sum():.2f}")
            col3.metric("Total Inc GST", f"${filtered_export['total_inc_gst'].sum():.2f}")

            csv = filtered_export[export_cols].to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"bookepaid_export_{date_from}_{date_to}.csv",
                mime="text/csv"
            )

            st.markdown("---")
            st.subheader("📄 Export PDF Report")
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

    df = load_data(business_id)
    prices = get_latest_prices(df)
    plates = load_plates(business_id)

    if df.empty:
        st.info("💡 Upload invoices first so BookePaid can match ingredient prices.")

    st.subheader("Menu Item Cost Tracker")
    for i, plate in enumerate(plates):
        result = calculate_plate_cost(plate, prices)
        open_key = f"open_{i}"
        if open_key not in st.session_state:
            st.session_state[open_key] = False

        with st.expander(
            f"{'🟢' if not result['has_unmatched'] else '🟡'} {plate['name']} — ${result['total_cost']:.2f}",
            expanded=st.session_state[open_key]
        ):
            st.session_state[open_key] = True

            # Selling price — owner only
            if user.role == "owner":
                selling_price = st.number_input(
                    "Selling Price ($)",
                    value=float(plate.get("selling_price", 0)),
                    min_value=0.0,
                    step=0.50,
                    key=f"sell_{i}"
                )
            else:
                selling_price = plate.get("selling_price", 0)

            st.caption("Edit ingredients and quantities:")
            h1, h2, h3, h4, h5 = st.columns([3, 1, 2, 2, 1])
            with h1:
                st.caption("**Ingredient**")
            with h2:
                st.caption("**Grams**")
            with h3:
                st.caption("**Invoice Match**")
            with h4:
                st.caption("**Cost**")
            with h5:
                st.caption("")
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
                    new_desc = st.text_input("Ingredient", value=ingredient["description"],
                                            key=f"desc_{i}_{j}", label_visibility="collapsed")
                with col2:
                    new_qty = st.number_input("Grams", value=round(ingredient["quantity_kg"] * 1000, 1),
                                             min_value=0.1, step=1.0, key=f"qty_{i}_{j}",
                                             label_visibility="collapsed")
                with col3:
                    if candidates:
                        options = [c[0] for c in candidates]
                        selected = st.selectbox("Match", options=options, key=f"match_{i}_{j}",
                                               label_visibility="collapsed")
                        selected_price = dict(candidates)[selected]
                        cost = round(selected_price * (new_qty / 1000), 4)
                        running_total += cost
                    else:
                        st.caption("⚠️ No match")
                        cost = None
                with col4:
                    if cost is not None:
                        st.caption(f"${cost:.4f}")
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
                    update_plate(
                        plate["id"],
                        plate["name"],
                        selling_price if user.role == "owner" else plate.get("selling_price", 0),
                        st.session_state[state_key],
                        business_id
                    )
                    del st.session_state[state_key]
                    st.session_state[open_key] = False
                    st.success("✅ Saved!")
                    st.rerun()
            with col_delete:
                if st.button("🗑️ Delete Plate", key=f"delete_{i}"):
                    delete_plate(plate["id"], business_id)
                    st.session_state[open_key] = False
                    st.success("Deleted!")
                    st.rerun()

            if result["has_unmatched"]:
                st.caption("🟡 Some ingredients couldn't be matched to invoice data yet.")

    st.markdown("---")
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
                "Ingredient", value=ingredient["description"],
                placeholder="e.g. Espresso Beans", key=f"new_desc_{j}",
                label_visibility="collapsed")
        with col2:
            new_qty = st.number_input("Grams", value=round(ingredient["quantity_kg"] * 1000, 1),
                                     min_value=0.1, step=1.0, key=f"new_qty_{j}",
                                     label_visibility="collapsed")
            st.session_state.new_plate_ingredients[j]["quantity_kg"] = new_qty / 1000
        with col3:
            if st.button("🗑️", key=f"del_new_{j}"):
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
            save_plate({"name": new_name, "ingredients": st.session_state.new_plate_ingredients}, business_id)
            del st.session_state.new_plate_ingredients
            st.success(f"✅ {new_name} saved!")
            st.rerun()
        else:
            st.error("Please enter a name and at least one ingredient.")

    # Reset onboarding — owner only
    if user.role == "owner":
        st.markdown("---")
        if st.button("🔄 Reset All Menu Templates"):
            from database import get_client
            db = get_client()
            plates_to_delete = load_plates(business_id)
            for p in plates_to_delete:
                delete_plate(p["id"], business_id)
            st.success("Reset! Refresh to run onboarding again.")
            st.rerun()
