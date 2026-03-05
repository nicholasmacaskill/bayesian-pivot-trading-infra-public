london_range = None
price_quartiles = None
ref_range_target = london_range or (price_quartiles or {}).get("Asian Range")
print(ref_range_target)
