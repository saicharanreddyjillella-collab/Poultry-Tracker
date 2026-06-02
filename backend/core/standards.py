# Cobb 400 standard body weight (grams) by day
# Source: Cobb Broiler Management Guide
# Format: day_number -> target_weight_grams

COBB_400_STANDARD = {
    0: 42,
    1: 52,
    2: 66,
    3: 82,
    4: 100,
    5: 120,
    6: 142,
    7: 170,
    8: 200,
    9: 233,
    10: 268,
    11: 306,
    12: 347,
    13: 390,
    14: 436,
    15: 485,
    16: 537,
    17: 591,
    18: 649,
    19: 709,
    20: 772,
    21: 838,
    22: 906,
    23: 976,
    24: 1050,
    25: 1126,
    26: 1204,
    27: 1284,
    28: 1367,
    29: 1451,
    30: 1538,
    31: 1626,
    32: 1716,
    33: 1808,
    34: 1901,
    35: 1996,
    36: 2091,
    37: 2188,
    38: 2285,
    39: 2383,
    40: 2481,
    41: 2579,
    42: 2677,
    43: 2775,
    44: 2872,
    45: 2968,
    46: 3063,
    47: 3156,
    48: 3248,
    49: 3338,
    50: 3425,
    51: 3510,
    52: 3593,
    53: 3673,
    54: 3750,
    55: 3824,
    56: 3895,
}


def get_standard_weight(day):
    """Get standard weight for a given day. Interpolates between known days."""
    if day in COBB_400_STANDARD:
        return COBB_400_STANDARD[day]
    if day < 0:
        return COBB_400_STANDARD[0]
    if day > 56:
        return COBB_400_STANDARD[56]
    # Interpolate
    lower = max(d for d in COBB_400_STANDARD if d <= day)
    upper = min(d for d in COBB_400_STANDARD if d >= day)
    if lower == upper:
        return COBB_400_STANDARD[lower]
    ratio = (day - lower) / (upper - lower)
    return round(COBB_400_STANDARD[lower] + ratio * (COBB_400_STANDARD[upper] - COBB_400_STANDARD[lower]))
