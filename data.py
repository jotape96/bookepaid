import pandas as pd
import os

DATA_FILE = "data.csv"

COLUMNS = ["invoice", "date", "description", "quantity", "unit_price", "total", "category"]


def load_data() -> pd.DataFrame:
    """Load accumulated invoice data from CSV."""
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # Ensure date column exists for older data files
        if "date" not in df.columns:
            df["date"] = "Unknown"
        return df
    return pd.DataFrame(columns=COLUMNS)


def save_data(df: pd.DataFrame):
    """Save invoice data to CSV."""
    df.to_csv(DATA_FILE, index=False)


def is_duplicate(invoice_name: str) -> bool:
    """Check if invoice has already been processed."""
    df = load_data()
    return invoice_name in df["invoice"].values


def append_invoice(new_df: pd.DataFrame):
    """Append new invoice rows to existing data and save."""
    existing_df = load_data()
    combined = pd.concat([existing_df, new_df], ignore_index=True)
    save_data(combined)

PLATE_HISTORY_FILE = "plate_history.csv"

def load_plate_history() -> pd.DataFrame:
    if os.path.exists(PLATE_HISTORY_FILE):
        return pd.read_csv(PLATE_HISTORY_FILE)
    return pd.DataFrame(columns=["date", "plate", "cost"])

def save_plate_history(df: pd.DataFrame):
    df.to_csv(PLATE_HISTORY_FILE, index=False)

def snapshot_plate_costs(invoice_date: str):
    """Recalculate all plate costs and save a snapshot."""
    from plates import load_plates, get_latest_prices, calculate_plate_cost
    
    df = load_data()
    prices = get_latest_prices(df)
    plates = load_plates()
    history = load_plate_history()

    new_rows = []
    for plate in plates:
        result = calculate_plate_cost(plate, prices)
        if result["total_cost"] > 0:
            new_rows.append({
                "date": invoice_date,
                "plate": plate["name"],
                "cost": round(result["total_cost"], 4)
            })

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([history, new_df], ignore_index=True)
        save_plate_history(combined)