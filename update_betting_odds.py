#!/usr/bin/env python3
"""
Scrapes betting odds from electionbettingodds.com and updates senate2026.html.
Run this script whenever you want to refresh the betting odds data.
"""

import re
import json
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not found. Run: pip install requests")
    sys.exit(1)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
HTML_FILE = 'senate2026.html'

STATE_ABBR_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming'
}


def scrape_control_odds():
    """Scrape overall senate control odds time series from Senate-Control-2026.html"""
    print("Fetching Senate-Control-2026.html ...")
    url = "https://electionbettingodds.com/Senate-Control-2026.html"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    html = r.text

    # Parse data.addRows entries: [new Date(YYYY,M,D,H,M,S),DEM%,REP%,]
    # JavaScript months are 0-indexed
    pattern = r'\[new Date\((\d+),(\d+),(\d+)[^)]*\),(\d+\.?\d*),(\d+\.?\d*),\]'
    matches = re.findall(pattern, html)

    if not matches:
        print("WARNING: Could not find time series data in Senate-Control-2026.html")
        return [], []

    # Collect one data point per day (last reading of each day)
    by_day = {}
    for m in matches:
        year, month_js, day = int(m[0]), int(m[1]), int(m[2])
        dem, rep = float(m[3]), float(m[4])
        month = month_js + 1  # convert JS 0-indexed month
        try:
            dt = datetime(year, month, day)
            by_day[dt] = (dem, rep)
        except ValueError:
            continue

    if not by_day:
        print("WARNING: No valid data points parsed.")
        return [], []

    sorted_days = sorted(by_day.keys())

    # Thin data: keep one point per week to avoid chart clutter
    # Always include first, last, and one per ~7 days
    thinned = [sorted_days[0]]
    for dt in sorted_days[1:]:
        if (dt - thinned[-1]).days >= 7:
            thinned.append(dt)
    # Always include the most recent
    if thinned[-1] != sorted_days[-1]:
        thinned.append(sorted_days[-1])

    dates = []
    rep_odds = []
    dem_odds = []
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    for dt in thinned:
        dem, rep = by_day[dt]
        dates.append(f"{month_names[dt.month - 1]} {dt.day}")
        rep_odds.append(rep)
        dem_odds.append(dem)

    print(f"  Parsed {len(matches)} raw data points -> thinned to {len(thinned)} weekly points")
    print(f"  Date range: {dates[0]} to {dates[-1]}")
    print(f"  Current odds: Rep {rep_odds[-1]}%, Dem {dem_odds[-1]}%")
    return dates, rep_odds, dem_odds


def scrape_state_odds():
    """Scrape per-state senate odds from SenateMap2026.html"""
    print("Fetching SenateMap2026.html ...")
    url = "https://electionbettingodds.com/SenateMap2026.html"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    html = r.text

    state_odds = {}
    failed = []

    for abbr, name in STATE_ABBR_TO_NAME.items():
        # Look for the state name followed by odds in various formats:
        # "StateName: Democrat: X% vs Republican: Y%"
        # "StateName: Republican: X% vs Democrat: Y%"
        escaped = re.escape(name)
        pattern = (
            rf'{escaped}[^"\']*?'
            rf'(?:Democrat[^:]*?:\s*(\d+\.?\d*)%[^%]*?Republican[^:]*?:\s*(\d+\.?\d*)%'
            rf'|Republican[^:]*?:\s*(\d+\.?\d*)%[^%]*?Democrat[^:]*?:\s*(\d+\.?\d*)%)'
        )
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            if match.group(1) is not None:
                # Democrat listed first
                dem = round(float(match.group(1)), 1)
                rep = round(float(match.group(2)), 1)
            else:
                # Republican listed first
                rep = round(float(match.group(3)), 1)
                dem = round(float(match.group(4)), 1)
            state_odds[name] = {'rep': rep, 'dem': dem}
        else:
            # Check if it's a "no race" state (not in 2026 elections)
            no_race_pattern = rf'{escaped}[^"\']*?[Nn]o race'
            if not re.search(no_race_pattern, html):
                failed.append(name)

    print(f"  Parsed odds for {len(state_odds)} states")
    if failed:
        print(f"  WARNING: Could not find odds for: {', '.join(failed)}")
    for state, odds in sorted(state_odds.items()):
        print(f"    {state}: Rep {odds['rep']}%, Dem {odds['dem']}%")

    return state_odds


def update_html(dates, rep_odds, dem_odds, state_odds):
    """Update the betting data object in senate2026.html"""
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    updated_on = datetime.now().strftime('%-m/%-d/%Y')

    # Build new betting data block
    dates_json = json.dumps(dates)
    rep_json = json.dumps(rep_odds)
    dem_json = json.dumps(dem_odds)
    current = rep_odds[-1] if rep_odds else 0

    # Build stateOdds JS object string
    state_lines = []
    for state, odds in sorted(state_odds.items()):
        state_lines.append(f"                    '{state}': {{ rep: {odds['rep']}, dem: {odds['dem']} }}")
    state_odds_str = ',\n'.join(state_lines)

    new_betting_block = (
        f"            betting: {{\n"
        f"                name: \"Betting odds\",\n"
        f"                author: \"odds from electionbettingodds.com\",\n"
        f"                dates: {dates_json},\n"
        f"                republicanOdds: {rep_json},\n"
        f"                democraticOdds: {dem_json},\n"
        f"                currentOdds: {current},\n"
        f"                stateOdds: {{\n"
        f"{state_odds_str}\n"
        f"                }}\n"
        f"            }}"
    )

    # Replace the existing betting block
    pattern = r'betting:\s*\{.*?(?=\n\s*\};?\s*\n\s*\};)'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        print("ERROR: Could not find the 'betting' data block in senate2026.html.")
        print("The script expects a block starting with 'betting: {' inside 'const dataSources'.")
        sys.exit(1)

    new_html = html[:match.start()] + new_betting_block + html[match.end():]

    # Also update the "last updated" date in the desktop header
    new_html = re.sub(
        r'(last updated )\d+/\d+/\d+',
        rf'\g<1>{updated_on}',
        new_html
    )

    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f"\nUpdated {HTML_FILE} successfully.")


def main():
    print("=== Updating betting odds in senate2026.html ===\n")

    dates, rep_odds, dem_odds = scrape_control_odds()
    if not dates:
        print("Aborting: could not scrape time series data.")
        sys.exit(1)

    print()
    state_odds = scrape_state_odds()
    if not state_odds:
        print("Aborting: could not scrape state odds.")
        sys.exit(1)

    print()
    update_html(dates, rep_odds, dem_odds, state_odds)
    print("\nDone! Review the changes, then commit and push.")


if __name__ == '__main__':
    main()
