import json
import os
import pandas as pd

PLATES_FILE = "plates.json"

# Pre-recommended café plates with typical ingredients
DEFAULT_PLATES = [
    {
        "name": "Flat White",
        "ingredients": [
            {"description": "Espresso Beans", "quantity_kg": 0.018},
            {"description": "Full Cream Milk", "quantity_kg": 0.15}
        ]
    },
    {
        "name": "Cappuccino",
        "ingredients": [
            {"description": "Espresso Beans", "quantity_kg": 0.018},
            {"description": "Full Cream Milk", "quantity_kg": 0.12}
        ]
    },
    {
        "name": "Avocado Toast",
        "ingredients": [
            {"description": "Avocado", "quantity_kg": 0.15},
            {"description": "Sourdough Bread", "quantity_kg": 0.08},
            {"description": "Lemon", "quantity_kg": 0.03}
        ]
    },
    {
        "name": "Banana Bread (slice)",
        "ingredients": [
            {"description": "Banana", "quantity_kg": 0.12},
            {"description": "Flour", "quantity_kg": 0.08},
            {"description": "Eggs", "quantity_kg": 0.05},
            {"description": "Butter", "quantity_kg": 0.03}
        ]
    },
    {
        "name": "Acai Bowl",
        "ingredients": [
            {"description": "Acai", "quantity_kg": 0.15},
            {"description": "Banana", "quantity_kg": 0.1},
            {"description": "Granola", "quantity_kg": 0.05}
        ]
    }
]


def load_plates() -> list:
    """Load plates from file, or return defaults if none exist."""
    if os.path.exists(PLATES_FILE):
        with open(PLATES_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_PLATES


def save_plates(plates: list):
    """Save plates to file."""
    with open(PLATES_FILE, "w") as f:
        json.dump(plates, f, indent=2)


def get_latest_prices(df: pd.DataFrame) -> dict:
    """
    Extract latest unit price per ingredient from invoice data.
    Returns dict: {description_lower: unit_price}
    """
    if df.empty:
        return {}
    cogs_df = df[df["category"] == "COGS"].copy()
    cogs_df["description_lower"] = cogs_df["description"].str.lower().str.strip()
    latest = cogs_df.sort_values("invoice").groupby("description_lower")["unit_price"].last()
    return latest.to_dict()


def calculate_plate_cost(plate: dict, prices: dict) -> dict:
    """
    Calculate cost of a plate based on latest ingredient prices.
    Returns plate with cost_per_unit and matched/unmatched ingredients.
    """
    total_cost = 0.0
    breakdown = []

    for ingredient in plate["ingredients"]:
        key = ingredient["description"].lower().strip()
        qty = ingredient["quantity_kg"]

        # Try fuzzy match — check if any price key contains the ingredient name
        matched_price = None
        matched_name = None
        for price_key, price_val in prices.items():
            if key in price_key or price_key in key:
                matched_price = price_val
                matched_name = price_key
                break

        if matched_price:
            cost = matched_price * qty
            total_cost += cost
            breakdown.append({
                "ingredient": ingredient["description"],
                "qty_kg": qty,
                "unit_price": matched_price,
                "cost": cost,
                "matched": True
            })
        else:
            breakdown.append({
                "ingredient": ingredient["description"],
                "qty_kg": qty,
                "unit_price": None,
                "cost": None,
                "matched": False
            })

    return {
        "name": plate["name"],
        "total_cost": total_cost,
        "breakdown": breakdown,
        "has_unmatched": any(not b["matched"] for b in breakdown)
    }
