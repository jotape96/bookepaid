import json
import os
import pandas as pd
import anthropic
import streamlit as st
 
PLATES_FILE = "plates.json"
 
RESTAURANT_TYPES = [
    "Specialty Coffee Shop",
    "Bakery & Pastry",
    "Juice & Smoothie Bar",
    "Breakfast & Brunch Café",
    "Italian Restaurant",
    "Mexican Restaurant",
    "Asian Restaurant",
    "Pizza Shop",
    "Burger & Grill",
    "Vegan & Healthy Food",
    "Sandwich & Deli",
    "Ice Cream & Desserts",
    "Middle Eastern Restaurant",
    "Indian Restaurant",
    "Kebab & Street Food",
]
 
 
def generate_plates_for_restaurant(restaurant_type: str) -> list:
    """Call Claude to generate typical dishes and ingredients for a restaurant type."""
    api_key = os.environ.get("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
 
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": f"""You are helping set up a food cost tracking app for a {restaurant_type}.
 
Generate 8 typical menu items for this type of business.
Return ONLY a JSON array, no markdown, no explanation.
 
Each object must have:
- name (string): the menu item name
- ingredients (array): list of ingredient objects, each with:
  - description (string): ingredient name as it would appear on a supplier invoice
  - quantity_kg (number): typical quantity in kg used per serving (use decimals, e.g. 0.15)
 
Example format:
[
  {{
    "name": "Flat White",
    "ingredients": [
      {{"description": "Espresso Beans", "quantity_kg": 0.018}},
      {{"description": "Full Cream Milk", "quantity_kg": 0.15}}
    ]
  }}
]
 
Be realistic with quantities. Only return the JSON array."""
            }
        ]
    )
 
    raw = response.content[0].text
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)
 
 
def load_plates() -> list:
    """Load plates from file."""
    if os.path.exists(PLATES_FILE):
        with open(PLATES_FILE, "r") as f:
            return json.load(f)
    return []
 
 
def save_plates(plates: list):
    """Save plates to file."""
    with open(PLATES_FILE, "w") as f:
        json.dump(plates, f, indent=2)
 
 
def plates_exist() -> bool:
    """Check if plates have been set up."""
    return os.path.exists(PLATES_FILE)
 
 
def get_latest_prices(df: pd.DataFrame) -> dict:
    """Extract latest unit price per ingredient from invoice data."""
    if df.empty:
        return {}
    cogs_df = df[df["category"] == "COGS"].copy()
    cogs_df["description_lower"] = cogs_df["description"].str.lower().str.strip()
    latest = cogs_df.sort_values("invoice").groupby("description_lower")["unit_price"].last()
    return latest.to_dict()
 
 
def calculate_plate_cost(plate: dict, prices: dict) -> dict:
    """Calculate cost of a plate based on latest ingredient prices."""
    total_cost = 0.0
    breakdown = []
 
    for ingredient in plate["ingredients"]:
        key = ingredient["description"].lower().strip()
        qty = ingredient["quantity_kg"]
 
        matched_price = None
        for price_key, price_val in prices.items():
            if key in price_key or price_key in key:
                matched_price = price_val
                break
 
        if matched_price:
            cost = matched_price * qty
            total_cost += cost
            breakdown.append({
                "ingredient": ingredient["description"],
                "qty_g": round(qty * 1000, 1),
                "unit_price": matched_price,
                "cost": cost,
                "matched": True
            })
        else:
            breakdown.append({
                "ingredient": ingredient["description"],
                "qty_g": round(qty * 1000, 1),
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