import pandas as pd
import os
import hashlib
from plates import load_plates, get_latest_prices, calculate_plate_cost

DATA_FILE = "data.csv"

COLUMNS = ["invoice", "date", "description", "quantity", "unit_price", "total", "category"]

HASH_FILE = "invoice_hashes.txt"


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
    existing_df = load_data()
    combined = pd.concat([existing_df, new_df], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.sort_values("date").reset_index(drop=True)
    save_data(combined)
    
PLATE_HISTORY_FILE = "plate_history.csv"

def load_plate_history() -> pd.DataFrame:
    if os.path.exists(PLATE_HISTORY_FILE):
        return pd.read_csv(PLATE_HISTORY_FILE)
    return pd.DataFrame(columns=["date", "plate", "cost"])

def save_plate_history(df: pd.DataFrame):
    df.to_csv(PLATE_HISTORY_FILE, index=False)

def snapshot_plate_costs(invoice_date: str):
    
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

    if new_rows: # If we have any valid plate snapshots, save them
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([history, new_df], ignore_index=True)
        save_plate_history(combined)

    if result["total_cost"] > 0 and not result["has_unmatched"]:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([history, new_df], ignore_index=True)
        save_plate_history(combined)


def load_hashes() -> set:
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_hash(file_hash: str):
    with open(HASH_FILE, "a") as f:
        f.write(file_hash + "\n")

def is_duplicate_content(pdf_bytes: bytes) -> bool:
    file_hash = hashlib.md5(pdf_bytes).hexdigest()
    return file_hash in load_hashes()

def register_hash(pdf_bytes: bytes):
    file_hash = hashlib.md5(pdf_bytes).hexdigest()
    save_hash(file_hash)