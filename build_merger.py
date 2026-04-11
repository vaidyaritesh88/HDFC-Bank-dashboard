"""Build merger simulation data combining HDFC Bank + HDFC Ltd quarterly metrics.
Focus: 1QFY18 to 4QFY23 (24 quarters) for HDFC Ltd. Post 1QFY24, use HDFC Bank standalone (already merged).
"""

import pandas as pd
import json

FILE_BANK = '20260410_HDFC Bank_Model.xlsm'
FILE_LTD = 'hdfcltd.xlsm'


def sf(v):
    if pd.notna(v) and v != '.' and not isinstance(v, str):
        return round(float(v), 4)
    return None


# ============ HDFC LTD QUARTERLY (cols BK-CH = 1QFY18 to 4QFY23) ============
ldf = pd.read_excel(FILE_LTD, sheet_name='quarterly results', header=None)

# Target columns: 62 to 85 (0-indexed), which are 1QFY18 to 4QFY23 in BK-CH
LTD_COLS = list(range(62, 86))  # 24 quarters
LTD_PERIODS = []
for c in LTD_COLS:
    h = ldf.iloc[2, c]
    # Convert 1QFY18 -> 1Q18
    qn = h[0]
    yr = h[4:6]
    LTD_PERIODS.append(f'{qn}Q{yr}')

print(f'HDFC Ltd quarters (BK-CH): {LTD_PERIODS[0]} to {LTD_PERIODS[-1]} ({len(LTD_PERIODS)} quarters)')


def ext_ltd(ridx):
    """Extract row values for BK-CH columns only."""
    row = ldf.iloc[ridx].tolist()
    return {LTD_PERIODS[i]: round(float(row[c]), 4)
            for i, c in enumerate(LTD_COLS)
            if pd.notna(row[c]) and not isinstance(row[c], str)}


# Extract all P&L items from clean section (rows 263-295 in 1-indexed = 262-294 in 0-indexed)
ltd_pl = {
    'OperatingIncome': ext_ltd(262),     # Operating income
    'InterestIncome': ext_ltd(263),      # Interest income
    'InterestExpense': ext_ltd(271),     # Interest expense
    'NII': ext_ltd(272),                 # NII (Net interest income)
    'NetOpIncome': ext_ltd(273),         # Net operating income
    'OtherIncome': ext_ltd(274),         # Other income
    'TotalIncome': ext_ltd(275),         # Total income
    'Opex': ext_ltd(276),                # Operating expenses
    'PPOP': ext_ltd(281),                # PPOP
    'Provisions': ext_ltd(282),          # Provisions
    'PBT': ext_ltd(285),                 # PBT
    'Tax': ext_ltd(286),                 # Tax
    'PAT': ext_ltd(289),                 # PAT
    'LoansOnBS': ext_ltd(292),           # Loans on BS
    'LoansOffBS': ext_ltd(293),          # Loans off BS
    'LoansUM': ext_ltd(294),             # Loans under management
}

# BS items from rows 73 (Sharecapital), 74 (Reserves), 92 (Total assets)
# Note: Reserves are missing in clean section for 1Q18-3Q18, need fallback from old section
ltd_bs = {
    'Sharecapital': ext_ltd(73),
    'Reserves': ext_ltd(74),
    'TotalAssets': ext_ltd(92),
    'TotalBorrowings': ext_ltd(79),
}

# Fill missing reserves for 1Q18, 2Q18, 3Q18 from old section (cols 53, 54, 55)
# Old section has: col 53 = 1QFY18 with Reserves 411,292.7
missing_reserves = {
    '1Q18': (53, 73),  # (col, row)
    '2Q18': (54, 73),
    '3Q18': (55, 73),
}
for q, (c, _) in missing_reserves.items():
    if ltd_bs['Reserves'].get(q) is None:
        v = ldf.iloc[74, c]
        if pd.notna(v):
            ltd_bs['Reserves'][q] = round(float(v), 4)

# Compute Equity = Sharecapital + Reserves
ltd_bs['Equity'] = {}
for q in LTD_PERIODS:
    sc = ltd_bs['Sharecapital'].get(q)
    r = ltd_bs['Reserves'].get(q)
    if sc is not None and r is not None:
        ltd_bs['Equity'][q] = round(sc + r, 4)

# Merge into single HDFC Ltd dict
ltd_final = {**ltd_pl, **ltd_bs}

print(f'\nHDFC Ltd data availability:')
for k, v in ltd_final.items():
    print(f'  {k:20s}: {len(v)}/{len(LTD_PERIODS)} periods')

# Spot check
print(f'\nSpot check 1Q18 / 4Q23:')
for k in ['NII', 'PAT', 'LoansOnBS', 'TotalAssets', 'Equity']:
    print(f'  {k}: 1Q18={ltd_final[k].get("1Q18")}, 4Q23={ltd_final[k].get("4Q23")}')


# ============ HDFC BANK QUARTERLY ============
with open('data_main.js') as f:
    bank_data = json.loads(f.read().replace('const DATA = ', '').rstrip(';\n'))

bank_abs = bank_data['quarterly']['absolute']

# Bank extra P&L data from Quarters sheet
qs = pd.read_excel(FILE_BANK, sheet_name='Quarters', header=None)
qh_b = qs.iloc[2].tolist()
bank_period_map = {}
for j, h in enumerate(qh_b):
    if pd.notna(h) and isinstance(h, str) and 'Q' in h:
        bank_period_map[h] = j


def ext_bank(ridx):
    row = qs.iloc[ridx].tolist()
    return {k: round(float(row[j]), 4) for k, j in bank_period_map.items()
            if pd.notna(row[j]) and not isinstance(row[j], str)}


bank_extra = {
    'PAT': ext_bank(41),                 # Reported net profit
    'NII': ext_bank(12),                 # Net interest income
    'IntIncome': ext_bank(3),            # Interest income
    'IntPaid': ext_bank(10),             # Interest paid (negative)
    'OpRevenue': ext_bank(26),           # Operating revenue
    'Opex': ext_bank(28),                # Operating expenses
    'Provisions': ext_bank(36),          # Provisions
    'PBT': ext_bank(38),                 # PBT
}

# OtherIncome = OpRevenue - NII
bank_extra['OtherIncome'] = {}
for p in bank_period_map:
    opr = bank_extra['OpRevenue'].get(p)
    nii = bank_extra['NII'].get(p)
    if opr is not None and nii is not None:
        bank_extra['OtherIncome'][p] = round(opr - nii, 4)

# PPOP = OpRevenue - Opex
bank_extra['PPOP'] = {}
for p in bank_period_map:
    opr = bank_extra['OpRevenue'].get(p)
    opx = bank_extra['Opex'].get(p)
    if opr is not None and opx is not None:
        bank_extra['PPOP'][p] = round(opr - opx, 4)

# Total income = OpRevenue
bank_extra['TotalIncome'] = dict(bank_extra['OpRevenue'])


# ============ COMBINED (MERGER SIMULATION) ============
# Logic:
#   - For 1QFY18 to 4QFY23: Bank + HDFC Ltd (sum)
#   - For 2QFY24 onwards: Bank standalone (already merged post-July 2023)
#   - 1QFY24 gap: Bank + HDFC Ltd not available for 1QFY24 in our data (LTD ends at 4QFY23)
#     So we skip 1QFY24 or use bank standalone

# Cap quarterly data at 3QFY26 (no forecast)
def is_forecast_q(q):
    try:
        qn = int(q[0])
        yr = int(q[2:])
        return yr > 26 or (yr == 26 and qn > 3)
    except:
        return False


def q_sort_key(q):
    try:
        return (int(q[2:]), int(q[0]))
    except:
        return (0, 0)


def in_sim_range(q):
    """1Q18 to 4Q23 is the LTD simulation range."""
    try:
        qn = int(q[0])
        yr = int(q[2:])
        # 1Q18 to 4Q23: yr in [18, 23]
        return 18 <= yr <= 23
    except:
        return False


def is_post_merger(q):
    """2QFY24 onwards - bank standalone already includes merged."""
    try:
        qn = int(q[0])
        yr = int(q[2:])
        return yr > 24 or (yr == 24 and qn >= 2)
    except:
        return False


def combine(bank_d, ltd_d):
    """Combine bank + ltd for sim range; bank-only post-merger."""
    result = {}
    all_q = set(bank_d.keys()) | set(ltd_d.keys())
    for q in all_q:
        if is_forecast_q(q):
            continue
        if in_sim_range(q):
            # Must have both to be meaningful
            b = bank_d.get(q)
            l = ltd_d.get(q)
            if b is not None and l is not None:
                result[q] = round(b + l, 4)
        elif is_post_merger(q):
            # Use bank standalone
            if bank_d.get(q) is not None:
                result[q] = bank_d[q]
        # 1Q24 falls between — skip it (LTD data ends at 4Q23, merger happened July 2023)
    return result


combined = {
    # BS
    'Loans': combine(bank_abs['NetAdvances'], ltd_final['LoansOnBS']),
    'TotalAssets': combine(bank_abs['TotalAssets'], ltd_final['TotalAssets']),
    'Equity': combine(bank_abs['Equity'], ltd_final['Equity']),
    # P&L
    'PAT': combine(bank_extra['PAT'], ltd_final['PAT']),
    'NII': combine(bank_extra['NII'], ltd_final['NII']),
    'TotalIncome': combine(bank_extra['TotalIncome'], ltd_final['TotalIncome']),
    'Opex': combine(bank_extra['Opex'], ltd_final['Opex']),
    'PPOP': combine(bank_extra['PPOP'], ltd_final['PPOP']),
    'Provisions': combine(bank_extra['Provisions'], ltd_final['Provisions']),
    'PBT': combine(bank_extra['PBT'], ltd_final['PBT']),
}

# FILL 1QFY24 GAP for Loans, TotalAssets, Equity
# Use 4Q23 QoQ growth (= (4Q23 - 3Q23)/3Q23) applied forward to estimate 1Q24
for bs_key in ['Loans', 'TotalAssets', 'Equity']:
    v_3q23 = combined[bs_key].get('3Q23')
    v_4q23 = combined[bs_key].get('4Q23')
    if v_3q23 and v_4q23 and v_3q23 > 0:
        qoq_growth = (v_4q23 - v_3q23) / v_3q23
        combined[bs_key]['1Q24'] = round(v_4q23 * (1 + qoq_growth), 4)
        print(f'  1Q24 {bs_key} estimate: {combined[bs_key]["1Q24"]:,.0f} '
              f'(4Q23 {v_4q23:,.0f} * (1 + {qoq_growth*100:.2f}%))')

# Get sorted combined periods
all_combined_periods = set()
for k, d in combined.items():
    all_combined_periods.update(d.keys())
combined_periods = sorted(all_combined_periods, key=q_sort_key)


# YoY growth
def yoy(d, qlist):
    r = {}
    for i, q in enumerate(qlist):
        if i < 4:
            continue
        prev_q = qlist[i - 4]
        curr = d.get(q)
        prev = d.get(prev_q)
        if curr is not None and prev is not None and prev > 0:
            r[q] = round((curr - prev) / prev, 6)
    return r


combined_yoy = {}
for key in ['Loans', 'TotalAssets', 'Equity', 'PAT', 'NII', 'TotalIncome', 'Opex', 'PPOP', 'PBT']:
    combined_yoy[key] = yoy(combined[key], combined_periods)

# DuPont metrics for combined
combined_metrics = {'RoAA': {}, 'RoAE': {}, 'Leverage': {}, 'NIM': {}, 'CostIncome': {}, 'CreditCost': {}}
for i, q in enumerate(combined_periods):
    if i == 0:
        continue
    pat = combined['PAT'].get(q)
    ta = combined['TotalAssets'].get(q)
    ta_prev = combined['TotalAssets'].get(combined_periods[i - 1])
    eq = combined['Equity'].get(q)
    nii = combined['NII'].get(q)
    ti = combined['TotalIncome'].get(q)
    opex = combined['Opex'].get(q)
    prov = combined['Provisions'].get(q)
    loans = combined['Loans'].get(q)

    if pat is not None and ta and ta_prev:
        avg_ta = (ta + ta_prev) / 2
        combined_metrics['RoAA'][q] = round(pat * 4 / avg_ta, 6)
    if ta and eq and eq > 0:
        combined_metrics['Leverage'][q] = round(ta / eq, 4)
    if pat is not None and eq and eq > 0:
        combined_metrics['RoAE'][q] = round(pat * 4 / eq, 6)
    if nii is not None and ta and ta_prev:
        avg_ta = (ta + ta_prev) / 2
        combined_metrics['NIM'][q] = round(nii * 4 / avg_ta, 6)
    if opex is not None and ti and ti > 0:
        combined_metrics['CostIncome'][q] = round(opex / ti, 6)
    if prov is not None and loans and loans > 0:
        combined_metrics['CreditCost'][q] = round(prov * 4 / loans, 6)


# ============ HDFC LTD STANDALONE YoY & METRICS ============
ltd_yoy = {}
for key in ['LoansOnBS', 'TotalAssets', 'Equity', 'PAT', 'NII', 'PPOP', 'Opex']:
    d = ltd_final.get(key, {})
    if d:
        ltd_yoy[key] = yoy(d, LTD_PERIODS)

ltd_metrics = {'RoAA': {}, 'RoAE': {}, 'Leverage': {}, 'NIM': {}, 'CostIncome': {}, 'LoanGrowthYoY': {}}
for i, q in enumerate(LTD_PERIODS):
    if i == 0:
        continue
    pat = ltd_final['PAT'].get(q)
    ta = ltd_final['TotalAssets'].get(q)
    ta_prev = ltd_final['TotalAssets'].get(LTD_PERIODS[i - 1])
    eq = ltd_final['Equity'].get(q)
    nii = ltd_final['NII'].get(q)
    opex = ltd_final['Opex'].get(q)
    ti = ltd_final['TotalIncome'].get(q)
    loans = ltd_final['LoansOnBS'].get(q)
    loans_prev = ltd_final['LoansOnBS'].get(LTD_PERIODS[i - 4]) if i >= 4 else None

    if pat is not None and ta and ta_prev:
        ltd_metrics['RoAA'][q] = round(pat * 4 / ((ta + ta_prev) / 2), 6)
    if ta and eq and eq > 0:
        ltd_metrics['Leverage'][q] = round(ta / eq, 4)
    if pat is not None and eq and eq > 0:
        ltd_metrics['RoAE'][q] = round(pat * 4 / eq, 6)
    if nii is not None and ta and ta_prev:
        ltd_metrics['NIM'][q] = round(nii * 4 / ((ta + ta_prev) / 2), 6)
    if opex is not None and ti and ti > 0:
        ltd_metrics['CostIncome'][q] = round(opex / ti, 6)
    if loans and loans_prev and loans_prev > 0:
        ltd_metrics['LoanGrowthYoY'][q] = round((loans - loans_prev) / loans_prev, 6)


# ============ WRITE ============
bank_data['merger'] = {
    'combined': combined,
    'combined_yoy': combined_yoy,
    'combined_metrics': combined_metrics,
    'combined_periods': combined_periods,
}

# HDFC Ltd standalone
bank_data['hdfcltd'] = {
    'absolute': ltd_final,
    'yoy': ltd_yoy,
    'metrics': ltd_metrics,
    'periods': LTD_PERIODS,
}

with open('data_main.js', 'w') as f:
    f.write('const DATA = ' + json.dumps(bank_data, indent=2) + ';\n')

print(f'\nCombined merger periods: {len(combined_periods)}')
print(f'  First: {combined_periods[0] if combined_periods else None}')
print(f'  Last: {combined_periods[-1] if combined_periods else None}')
print(f'\nSample combined values:')
for q in ['1Q18', '4Q19', '4Q22', '4Q23', '2Q24', '3Q26']:
    if q in combined['Loans']:
        print(f'  {q}: Loans={combined["Loans"].get(q):,.0f}, TA={combined["TotalAssets"].get(q):,.0f}, PAT={combined["PAT"].get(q):,.0f}')

# Check 4QFY23 CAGR baseline
print(f'\nKey CAGR base values (4QFY23):')
for k in ['Loans', 'TotalAssets', 'Equity', 'NII', 'PPOP', 'PAT']:
    v = combined[k].get('4Q23')
    print(f'  {k}: {v}')
