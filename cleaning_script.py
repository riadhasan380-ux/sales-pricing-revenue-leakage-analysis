"""
Sales & Pricing Data Quality Audit — Revenue Leakage Analysis
Energy/Oil & Gas Sector | Author: Riad Hasan
"""

import pandas as pd
import numpy as np

# ── 1. LOAD RAW DATA ──────────────────────────────────────────────────────────
df = pd.read_csv("raw_sales_data.csv")
total_records = len(df)
print(f"Raw records loaded: {total_records}")
print(f"Columns: {list(df.columns)}\n")

# ── 2. INITIAL PROFILE ────────────────────────────────────────────────────────
print("=" * 55)
print("STEP 1: DATA PROFILE (RAW)")
print("=" * 55)
print(f"Total records:        {total_records}")
print(f"Missing customer_id:  {df['customer_id'].isna().sum() + (df['customer_id'] == '').sum()}")
print(f"Missing unit_price:   {(df['unit_price_usd'] == '').sum() + df['unit_price_usd'].isna().sum()}")
print(f"Duplicate order_ids:  {df['order_id'].duplicated().sum()}")
print()

# ── 3. CONVERT TYPES ─────────────────────────────────────────────────────────
df["unit_price_usd"] = pd.to_numeric(df["unit_price_usd"], errors="coerce")
df["quantity_units"] = pd.to_numeric(df["quantity_units"], errors="coerce")
df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")

# ── 4. FLAG ISSUES ───────────────────────────────────────────────────────────
print("=" * 55)
print("STEP 2: ISSUE DETECTION")
print("=" * 55)

issues = {}

# 4a. Duplicates
dupes = df[df.duplicated(subset=["order_id"], keep=False)].copy()
issues["duplicate_orders"] = dupes
df["flag_duplicate"] = df.duplicated(subset=["order_id"], keep=False)
print(f"Duplicate order IDs:     {df['flag_duplicate'].sum()} records ({df['order_id'].duplicated().sum()} pairs)")

# 4b. Missing price
df["flag_missing_price"] = df["unit_price_usd"].isna()
print(f"Missing unit price:      {df['flag_missing_price'].sum()} records")

# 4c. Negative quantity
df["flag_negative_qty"] = df["quantity_units"] < 0
print(f"Negative quantity:       {df['flag_negative_qty'].sum()} records")

# 4d. Price outliers — flag if price is more than 3x or less than 0.1x the median per product
price_stats = df.groupby("product_code")["unit_price_usd"].median().rename("median_price")
df = df.join(price_stats, on="product_code")
df["flag_price_outlier"] = (
    (df["unit_price_usd"] > df["median_price"] * 3) |
    (df["unit_price_usd"] < df["median_price"] * 0.1)
)
print(f"Price outliers:          {df['flag_price_outlier'].sum()} records")

# 4e. Missing customer ID
df["flag_missing_cust"] = df["customer_id"].isna() | (df["customer_id"].astype(str).str.strip() == "")
print(f"Missing customer ID:     {df['flag_missing_cust'].sum()} records")

# 4f. Bad product name (contains lowercase+underscore pattern or suffix flags)
df["flag_bad_product_name"] = df["product_name"].str.contains(r"(_v2|_OLD|_x|_)", regex=True, na=False)
print(f"Inconsistent prod names: {df['flag_bad_product_name'].sum()} records")

# ── 5. REVENUE LEAKAGE CALCULATION ───────────────────────────────────────────
print()
print("=" * 55)
print("STEP 3: REVENUE LEAKAGE ESTIMATE")
print("=" * 55)

df["revenue"] = df["quantity_units"] * df["unit_price_usd"]

# Any record with at least one flag
any_flag = (
    df["flag_duplicate"] |
    df["flag_missing_price"] |
    df["flag_negative_qty"] |
    df["flag_price_outlier"] |
    df["flag_missing_cust"] |
    df["flag_bad_product_name"]
)

dirty_records = df[any_flag]
clean_records = df[~any_flag]

total_revenue_raw = df["revenue"].sum()
dirty_revenue = dirty_records["revenue"].abs().sum()
clean_revenue = clean_records["revenue"].sum()
error_rate = len(dirty_records) / total_records * 100

print(f"Total records:           {total_records}")
print(f"Records with issues:     {len(dirty_records)} ({error_rate:.1f}%)")
print(f"Clean records:           {len(clean_records)}")
print(f"Total revenue (raw):     ${total_revenue_raw:,.2f}")
print(f"Revenue at risk:         ${dirty_revenue:,.2f}")
print(f"Clean revenue:           ${clean_revenue:,.2f}")

# ── 6. ISSUE SUMMARY TABLE ───────────────────────────────────────────────────
print()
print("=" * 55)
print("STEP 4: ISSUE BREAKDOWN SUMMARY")
print("=" * 55)

summary = {
    "Issue Type": [
        "Duplicate Orders",
        "Missing Unit Price",
        "Negative Quantity",
        "Price Outlier",
        "Missing Customer ID",
        "Inconsistent Product Name"
    ],
    "Record Count": [
        df["flag_duplicate"].sum(),
        df["flag_missing_price"].sum(),
        df["flag_negative_qty"].sum(),
        df["flag_price_outlier"].sum(),
        df["flag_missing_cust"].sum(),
        df["flag_bad_product_name"].sum(),
    ],
    "Est. Revenue Impact ($)": [
        df[df["flag_duplicate"]]["revenue"].abs().sum(),
        df[df["flag_missing_price"]]["revenue"].abs().sum(),
        df[df["flag_negative_qty"]]["revenue"].abs().sum(),
        df[df["flag_price_outlier"]]["revenue"].abs().sum(),
        df[df["flag_missing_cust"]]["revenue"].abs().sum(),
        df[df["flag_bad_product_name"]]["revenue"].abs().sum(),
    ]
}

summary_df = pd.DataFrame(summary)
summary_df["Est. Revenue Impact ($)"] = summary_df["Est. Revenue Impact ($)"].apply(lambda x: f"${x:,.2f}")
print(summary_df.to_string(index=False))

# ── 7. EXPORT CLEANED + FLAGGED FILES ────────────────────────────────────────
df_flagged = df.copy()
df_flagged.to_csv("flagged_sales_data.csv", index=False)

df_clean = clean_records.drop(columns=[
    "flag_duplicate", "flag_missing_price", "flag_negative_qty",
    "flag_price_outlier", "flag_missing_cust", "flag_bad_product_name",
    "median_price", "revenue"
])
df_clean.to_csv("cleaned_sales_data.csv", index=False)

summary_df.to_csv("revenue_leakage_summary.csv", index=False)

print()
print("=" * 55)
print("FILES EXPORTED:")
print("  flagged_sales_data.csv    — all records with issue flags")
print("  cleaned_sales_data.csv    — clean records only")
print("  revenue_leakage_summary.csv — issue breakdown table")
print("=" * 55)
