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
