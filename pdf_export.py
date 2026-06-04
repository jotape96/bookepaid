import pandas as pd
import os
import tempfile
from fpdf import FPDF


def generate_pdf(df: pd.DataFrame, fig_pie) -> bytes:
    """Generate a PDF financial report with summary, table, and pie chart."""
    pdf = FPDF()
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "BookePaid - Financial Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Generated: {pd.Timestamp.now().strftime('%d %B %Y')}", ln=True, align="C")
    pdf.ln(6)

    # Executive summary
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Executive Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Total Documented Spend:    ${df['total'].sum():.2f}", ln=True)
    pdf.cell(0, 8, f"Unique Vendors / Invoices: {df['invoice'].nunique()}", ln=True)
    pdf.cell(0, 8, f"Total Line Items Audited:  {len(df)}", ln=True)
    pdf.ln(4)

    # Category breakdown
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Allocation By Cost Center", ln=True)
    pdf.set_font("Helvetica", "", 11)
    for cat in ["COGS", "Packaging", "Labour", "Overhead", "Other"]:
        if cat in df["category"].values:
            amount = df[df["category"] == cat]["total"].sum()
            pdf.cell(0, 8, f"{cat}: ${amount:.2f}", ln=True)
    pdf.ln(4)

    # Line item table
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Line Item Detail", ln=True)
    col_widths = [50, 20, 25, 25, 30, 35]
    headers = ["Description", "Qty", "Unit Price", "Total", "Category", "Invoice"]
    pdf.set_font("Helvetica", "B", 9)
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
        pdf.cell(col_widths[5], 7, str(row["invoice"])[:20], border=1)
        pdf.ln()
    pdf.ln(6)

    # Pie chart
    with tempfile.TemporaryDirectory() as tmpdir:
        pie_path = os.path.join(tmpdir, "pie.png")
        fig_pie.write_image(pie_path, width=500, height=350)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Spend Distribution", ln=True)
        pdf.image(pie_path, w=140)

    return bytes(pdf.output())
