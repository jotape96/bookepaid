import pandas as pd
from database import get_client


def load_data(business_id: str) -> pd.DataFrame:
    """Load all line items for a business from Supabase."""
    db = get_client()
    result = db.table("line_items").select("*")\
        .eq("business_id", business_id)\
        .execute()
    if result.data:
        df = pd.DataFrame(result.data)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
        return df
    return pd.DataFrame(columns=["id", "invoice_id", "business_id", "description",
                                  "quantity", "unit", "unit_price", "total",
                                  "category", "date"])


def is_duplicate_invoice(invoice_number: str, supplier: str, business_id: str) -> bool:
    """Check if invoice number + supplier already exists for this business."""
    if invoice_number == "UNKNOWN" or supplier == "UNKNOWN":
        return False
    db = get_client()
    result = db.table("invoices").select("id")\
        .eq("business_id", business_id)\
        .ilike("invoice_number", invoice_number)\
        .ilike("supplier", supplier)\
        .execute()
    return len(result.data) > 0


def save_invoice(invoice_number: str, supplier: str, date: str,
                 filename: str, business_id: str) -> str:
    """Insert invoice record and return its ID."""
    db = get_client()
    result = db.table("invoices").insert({
        "business_id": business_id,
        "invoice_number": invoice_number,
        "supplier": supplier,
        "date": date,
        "filename": filename
    }).execute()
    return result.data[0]["id"]


def save_line_items(df: pd.DataFrame, invoice_id: str, business_id: str):
    """Insert all line items for an invoice into Supabase."""
    db = get_client()
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "business_id": business_id,
            "invoice_id": invoice_id,
            "description": row.get("description"),
            "quantity": row.get("quantity"),
            "unit": row.get("unit"),
            "unit_price": row.get("unit_price"),
            "total": row.get("total"),
            "category": row.get("category"),
            "date": str(row.get("date", ""))[:10]
        })
    db.table("line_items").insert(rows).execute()


def load_plate_history(business_id: str) -> pd.DataFrame:
    """Load plate cost history for a business."""
    db = get_client()
    result = db.table("plate_history").select("*")\
        .eq("business_id", business_id)\
        .execute()
    if result.data:
        df = pd.DataFrame(result.data)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df.sort_values("date")
    return pd.DataFrame(columns=["id", "business_id", "plate_id", "plate_name", "date", "cost"])


def snapshot_plate_costs(invoice_date: str, business_id: str):
    """Recalculate all plate costs and save snapshot if all ingredients matched."""
    from plates import load_plates, get_latest_prices, calculate_plate_cost
    df = load_data(business_id)
    prices = get_latest_prices(df)
    plates = load_plates(business_id)
    db = get_client()
    for plate in plates:
        result = calculate_plate_cost(plate, prices)
        if result["total_cost"] > 0 and not result["has_unmatched"]:
            db.table("plate_history").insert({
                "business_id": business_id,
                "plate_id": plate.get("id"),
                "plate_name": plate["name"],
                "date": invoice_date,
                "cost": round(result["total_cost"], 4)
            }).execute()