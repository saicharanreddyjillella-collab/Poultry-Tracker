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


# ─── Feed intake forecast (Cobb-400 style) ───────────────────────────────
# Approximate daily feed intake per bird (grams/day) by age in days.
# Standard broiler figures; used for forward feed-requirement forecasting.
DAILY_FEED_INTAKE_G = {
    0: 13, 1: 15, 2: 18, 3: 21, 4: 24, 5: 27, 6: 31, 7: 35,
    8: 39, 9: 43, 10: 48, 11: 53, 12: 58, 13: 63, 14: 69,
    15: 75, 16: 81, 17: 87, 18: 94, 19: 101, 20: 108, 21: 115,
    22: 122, 23: 129, 24: 136, 25: 143, 26: 150, 27: 157, 28: 164,
    29: 171, 30: 178, 31: 185, 32: 191, 33: 197, 34: 203, 35: 209,
    36: 214, 37: 219, 38: 224, 39: 228, 40: 232, 41: 236, 42: 239,
    43: 242, 44: 244, 45: 246, 46: 248, 47: 249, 48: 250, 49: 251,
    50: 252, 51: 252, 52: 253, 53: 253, 54: 253, 55: 253, 56: 253,
}

# Feed phase by age (days): pre-starter -> starter -> finisher.
FEED_PHASE_DAYS = {'BPSC': (0, 10), 'BSC': (11, 21), 'BFP': (22, 999)}


def get_daily_feed_intake(day):
    """Approx grams of feed per bird on a given day of age. Interpolates;
    clamps below 0 and above 56 to the endpoints."""
    if day < 0:
        return DAILY_FEED_INTAKE_G[0]
    if day in DAILY_FEED_INTAKE_G:
        return DAILY_FEED_INTAKE_G[day]
    if day > 56:
        return DAILY_FEED_INTAKE_G[56]
    lower = max(d for d in DAILY_FEED_INTAKE_G if d <= day)
    upper = min(d for d in DAILY_FEED_INTAKE_G if d >= day)
    if lower == upper:
        return DAILY_FEED_INTAKE_G[lower]
    ratio = (day - lower) / (upper - lower)
    return round(DAILY_FEED_INTAKE_G[lower] + ratio * (DAILY_FEED_INTAKE_G[upper] - DAILY_FEED_INTAKE_G[lower]))


def get_feed_phase(day):
    """Which feed phase (BPSC/BSC/BFP) applies at a given age in days."""
    for phase, (lo, hi) in FEED_PHASE_DAYS.items():
        if lo <= day <= hi:
            return phase
    return 'BFP'
