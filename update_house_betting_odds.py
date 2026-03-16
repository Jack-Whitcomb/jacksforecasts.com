#!/usr/bin/env python3
"""
Scrapes betting odds from electionbettingodds.com and updates house2026.html.
Run this script whenever you want to refresh the betting odds data.
"""

import re
import json
import sys
import os
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not found. Run: pip install requests")
    sys.exit(1)

HEADERS  = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'house2026.html')


def scrape_control_odds():
    """Scrape overall house control odds time series from House-Control-2026.html"""
    print("Fetching House-Control-2026.html ...")
    url = "https://electionbettingodds.com/House-Control-2026.html"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    html = r.text

    # Parse data.addRows entries: [new Date(YYYY,M,D,H,M,S),DEM%,REP%,]
    # JavaScript months are 0-indexed
    pattern = r'\[new Date\((\d+),(\d+),(\d+)[^)]*\),(\d+\.?\d*),(\d+\.?\d*),\]'
    matches = re.findall(pattern, html)

    if not matches:
        print("WARNING: Could not find time series data in House-Control-2026.html")
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


def update_html(dates, rep_odds, dem_odds):
    """Update the betting data block in house2026.html"""
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    current_rep = rep_odds[-1] if rep_odds else 0
    current_dem = dem_odds[-1] if dem_odds else 0

    now        = datetime.now()
    updated_on = now.strftime('%b') + ' ' + str(now.day) + ', ' + str(now.year)

    new_block = (
        f"// BEGIN_BETTING_DATA\n"
        f"    betting: {{\n"
        f"        author: \"odds from electionbettingodds.com\",\n"
        f"        dates: {json.dumps(dates)},\n"
        f"        repOdds: {json.dumps(rep_odds)},\n"
        f"        demOdds: {json.dumps(dem_odds)},\n"
        f"        currentRepOdds: {current_rep},\n"
        f"        currentDemOdds: {current_dem}\n"
        f"    }}\n"
        f"    // END_BETTING_DATA"
    )

    start_marker = '// BEGIN_BETTING_DATA'
    end_marker   = '// END_BETTING_DATA'
    start_idx = html.find(start_marker)
    end_idx   = html.find(end_marker)
    if start_idx == -1 or end_idx == -1:
        print("ERROR: Could not find BEGIN_BETTING_DATA / END_BETTING_DATA markers in house2026.html.")
        sys.exit(1)

    new_html = html[:start_idx] + new_block + html[end_idx + len(end_marker):]

    # Update the date in the heroId / top-band-foot line
    new_html = re.sub(
        r'Forecast as of [A-Za-z]+ \d+, \d+\.',
        f'Forecast as of {updated_on}.',
        new_html
    )

    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f"\nUpdated {HTML_FILE} successfully.")


def main():
    print("=== Updating betting odds in house2026.html ===\n")

    dates, rep_odds, dem_odds = scrape_control_odds()
    if not dates:
        print("Aborting: could not scrape time series data.")
        sys.exit(1)

    print()
    update_html(dates, rep_odds, dem_odds)
    print("\nDone! Review the changes, then commit and push.")


if __name__ == '__main__':
    main()
