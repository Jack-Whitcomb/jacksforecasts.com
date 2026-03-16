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

HEADERS  = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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
        return [], [], []

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
        return [], [], []

    sorted_days = sorted(by_day.keys())

    # Thin to one point per week; always include first and last
    thinned = [sorted_days[0]]
    for dt in sorted_days[1:]:
        if (dt - thinned[-1]).days >= 7:
            thinned.append(dt)
    if thinned[-1] != sorted_days[-1]:
        thinned.append(sorted_days[-1])

    dates    = []
    rep_odds = []
    dem_odds = []
    for dt in thinned:
        dem, rep = by_day[dt]
        dates.append(dt.strftime('%Y-%m-%d'))
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
        escaped = re.escape(name)
        pattern = (
            rf'{escaped}[^"\']*?'
            rf'(?:Democrat[^:]*?:\s*(\d+\.?\d*)%[^%]*?Republican[^:]*?:\s*(\d+\.?\d*)%'
            rf'|Republican[^:]*?:\s*(\d+\.?\d*)%[^%]*?Democrat[^:]*?:\s*(\d+\.?\d*)%)'
        )
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            if match.group(1) is not None:
                dem = round(float(match.group(1)), 1)
                rep = round(float(match.group(2)), 1)
            else:
                rep = round(float(match.group(3)), 1)
                dem = round(float(match.group(4)), 1)
            state_odds[name] = {'rep': rep, 'dem': dem}
        else:
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
    """Update the betting data block in senate2026.html"""
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    current_rep = rep_odds[-1] if rep_odds else 0
    current_dem = dem_odds[-1] if dem_odds else 0

    # Build stateOdds JS object string
    state_lines = []
    for state, odds in sorted(state_odds.items()):
        state_lines.append(f"                '{state}': {{ rep: {odds['rep']}, dem: {odds['dem']} }}")
    state_odds_str = ',\n'.join(state_lines)

    now        = datetime.now()
    updated_on = now.strftime('%b') + ' ' + str(now.day) + ', ' + str(now.year)

    new_block = (
        f"// BEGIN_BETTING_DATA\n"
        f"        betting: {{\n"
        f"            author: \"odds from electionbettingodds.com\",\n"
        f"            dates: {json.dumps(dates)},\n"
        f"            republicanOdds: {json.dumps(rep_odds)},\n"
        f"            democraticOdds: {json.dumps(dem_odds)},\n"
        f"            currentOdds: {current_rep},\n"
        f"            currentDemOdds: {current_dem},\n"
        f"            currentHungOdds: 0,\n"
        f"            stateOdds: {{\n"
        f"{state_odds_str}\n"
        f"            }}\n"
        f"        }}\n"
        f"        // END_BETTING_DATA"
    )

    start_marker = '// BEGIN_BETTING_DATA'
    end_marker   = '// END_BETTING_DATA'
    start_idx = html.find(start_marker)
    end_idx   = html.find(end_marker)
    if start_idx == -1 or end_idx == -1:
        print("ERROR: Could not find BEGIN_BETTING_DATA / END_BETTING_DATA markers in senate2026.html.")
        sys.exit(1)

    new_html = html[:start_idx] + new_block + html[end_idx + len(end_marker):]

    # Update the date in the JS heroId line
    new_html = re.sub(
        r"'Updated [A-Za-z]+ \d+, \d+'",
        f"'Updated {updated_on}'",
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
