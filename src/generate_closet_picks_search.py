import argparse
import sys
import asyncio
import csv
import re
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright
from collections import defaultdict

# Use the search page as the main URL
MAIN_URL = "https://www.criterion.com/closet-picks/search"
OUTPUT_FILE = "docs/closet_picks.csv"
STATE_FILE = "scrape_state.json"
CONCURRENCY = 5
LIMIT = None # Set to an integer for testing, None for full run

# Full Director Mappings from the original script
DIRECTOR_MAPPINGS = {
    "The Apu Trilogy": "Satyajit Ray",
    "The Koker Trilogy": "Abbas Kiarostami",
    "The Before Trilogy": "Richard Linklater",
    "Three Colors": "Krzysztof Kieślowski",
    "The BRD Trilogy": "Rainer Werner Fassbinder",
    "Trilogy of Life": "Pier Paolo Pasolini",
    "Six Moral Tales": "Eric Rohmer",
    "La Jetée/Sans Soleil": "Chris Marker",
    "I Am Curious": "Vilgot Sjöman",
    "Police Story / Police Story 2": "Jackie Chan",
    "Small Axe": "Steve McQueen",
    "Streetwise/Tiny: The Life of Erin Blackwell": "Martin Bell",
    "The Emigrants/The New Land": "Jan Troell",
    "The Shooting/Ride in the Whirlwind": "Monte Hellman",
    "By Brakhage: An Anthology, Volumes One and Two": "Stan Brakhage",
    "The Qatsi Trilogy": "Godfrey Reggio",
    "Fanny and Alexander": "Ingmar Bergman",
    "Dietrich & von Sternberg in Hollywood": "Josef von Sternberg",
    "The Infernal Affairs Trilogy": "Andrew Lau and Alan Mak",
    "Once Upon a Time in China: The Complete Films": "Tsui Hark",
    "The Complete Monterey Pop Festival": "D. A. Pennebaker",
    "Three Fantastic Journeys by Karel Zeman": "Karel Zeman",
    "Bo Widerberg’s New Swedish Cinema": "Bo Widerberg",
    "Gregg Araki’s Teen Apocalypse Trilogy": "Gregg Araki",
    "Freaks / The Unknown / The Mystic: Tod Browning’s Sideshow Shockers": "Tod Browning",
    "Carl Theodor Dreyer": "Carl Theodor Dreyer",
    "The Samurai Trilogy": "Hiroshi Inagaki",
    "Eclipse Series 11: Larisa Shepitko": "Larisa Shepitko",
    "Eclipse Series 12: Aki Kaurismäki’s Proletariat Trilogy": "Aki Kaurismäki",
    "Eclipse Series 14: Rossellini’s History Films—Renaissance and Enlightenment": "Roberto Rossellini",
    "Eclipse Series 19: Chantal Akerman in the Seventies": "Chantal Akerman",
    "Eclipse Series 21: Oshima’s Outlaw Sixties": "Nagisa Oshima",
    "Eclipse Series 23: The First Films of Akira Kurosawa": "Akira Kurosawa",
    "Eclipse Series 24: The Actuality Dramas of Allan King": "Allan King",
    "Eclipse Series 25: Basil Dearden’s London Underground": "Basil Dearden",
    "Eclipse Series 26: Silent Naruse": "Mikio Naruse",
    "Eclipse Series 29: Aki Kaurismäki’s Leningrad Cowboys": "Aki Kaurismäki",
    "Eclipse Series 2: The Documentaries of Louis Malle": "Louis Malle",
    "Eclipse Series 31: Three Popular Films by Jean-Pierre Gorin": "Jean-Pierre Gorin",
    "Eclipse Series 33: Up All Night with Robert Downey Sr.": "Robert Downey Sr.",
    "Eclipse Series 38: Masaki Kobayashi Against the System": "Masaki Kobayashi",
    "Eclipse Series 3: Late Ozu": "Yasujiro Ozu",
    "Eclipse Series 5: The First Films of Samuel Fuller": "Samuel Fuller",
    "Eclipse Series 8: Lubitsch Musicals": "Ernst Lubitsch",
    "Eclipse Series 9: The Delirious Fictions of William Klein": "William Klein",
    "Letters from Fontainhas: Three Films by Pedro Costa": "Pedro Costa",
    "Pigs, Pimps & Prostitutes: 3 Films by Shohei Imamura": "Shohei Imamura",
    "Stage and Spectacle: Three Films by Jean Renoir": "Jean Renoir",
    "The Ranown Westerns: Five Films Directed by Budd Boetticher": "Budd Boetticher",
    "The Red Balloon and Other Stories: Five Films by Albert Lamorisse": "Albert Lamorisse",
    "The Three Musketeers / The Four Musketeers: Two Films by Richard Lester": "Richard Lester",
    "Three Films by Mai Zetterling": "Mai Zetterling",
    "Three Revolutionary Films by Ousmane Sembène": "Ousmane Sembène",
    "Wim Wenders: The Road Trilogy": "Wim Wenders",
    "World of Wong Kar Wai": "Wong Kar Wai",
    "Yojimbo / Sanjuro: Two Samurai Films by Akira Kurosawa": "Akira Kurosawa",
    "3 Films by Roberto Rossellini Starring Ingrid Bergman": "Roberto Rossellini",
    "3 Silent Classics by Josef von Sternberg": "Josef von Sternberg",
    "4 by Agnès Varda": "Agnès Varda",
    "A Film Trilogy by Ingmar Bergman": "Ingmar Bergman",
    "A Story of Floating Weeds / Floating Weeds: Two Films by Yasujiro Ozu": "Yasujiro Ozu",
    "The Wes Anderson Archive: Ten Films, Twenty-Five Years": "Wes Anderson",
    "Pierre Etaix": "Pierre Etaix",
    "Essential Fellini": "Federico Fellini",
    "Three Films by Luis Buñuel": "Luis Buñuel",
    "The Complete Films of Agnès Varda": "Agnès Varda",
    "The Complete Jacques Tati": "Jacques Tati",
    "The Complete Jean Vigo": "Jean Vigo",
    "The Essential Jacques Demy": "Jacques Demy",
    "Eric Rohmer’s Tales of the Four Seasons": "Eric Rohmer",
    "Roberto Rossellini’s War Trilogy": "Roberto Rossellini",
    "The Signifyin’ Works of Marlon Riggs": "Marlon Riggs",
    "Pasolini 101": "Pier Paolo Pasolini",
}

IGNORE_TITLES = {
    "Godzilla: The Showa-Era Films, 1954–1975",
    "Zatoichi: The Blind Swordsman",
    "Bruce Lee: His Greatest Hits",
    "Martin Scorsese’s World Cinema Project No. 1",
    "Martin Scorsese’s World Cinema Project No. 2",
    "Martin Scorsese’s World Cinema Project No. 3",
    "Martin Scorsese’s World Cinema Project No. 4",
    "America Lost and Found: The BBS Story",
    "The Killers",
    "André Gregory & Wallace Shawn: 3 Films",
    "Eclipse Series 30: Sabu!",
    "Eclipse Series 32: Pearls of the Czech New Wave",
    "Monsters and Madmen",
    "Rebel Samurai: Sixties Swordplay Classics",
    "Jackie Chan: Emergence of a Superstar",
}

REGEX_PATTERNS = [
    (r"^The Complete Films of (.+)$", 1),
    (r"^Three Films by (.+)$", 1),
    (r"^Essential (.+)$", 1),
    (r"^(.+): Five Films$", 1),
    (r"^(.+)’s Cinema$", 1),
    (r"^(.+) Masterpieces.*$", 1),
    (r"^(.+) Directs .+$", 1),
    (r"^(.+): Essential Films$", 1),
    (r"^(.+): Trilogy$", 1),
    (r"^(.+): The .* Films$", 1),
    (r"^Lars von Trier’s (.+) Trilogy$", "Lars von Trier"),
]

def clean_picker_name(text):
    text = re.sub(r"\s+[A-Za-z]{3}\s+\d{1,2},\s+\d{4}$", "", text).strip()
    text = re.sub(r"[’\']s? Closet Picks.*$", "", text, flags=re.IGNORECASE).strip()
    return text.upper()

def normalize_director(title, director):
    if "Collector" not in director:
        return director
    if title in IGNORE_TITLES:
        return director # Keep as is (likely Collector's Set)
    if title in DIRECTOR_MAPPINGS:
        return DIRECTOR_MAPPINGS[title]

    for pattern, group in REGEX_PATTERNS:
        match = re.match(pattern, title)
        if match:
            if isinstance(group, int):
                name = match.group(group).strip()
            else:
                name = group
            if name == "Fellini": return "Federico Fellini"
            return name

    return director

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading state: {e}")
    return {}

def save_state(last_date):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_scraped_date": last_date}, f, indent=2)
        print(f"State saved: {last_date}")
    except Exception as e:
        print(f"Error saving state: {e}")

def load_existing_picks(filepath):
    aggregated = defaultdict(lambda: {"count": 0, "pickers": []})
    if not os.path.exists(filepath):
        return aggregated

    print(f"Loading existing picks from {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # skip header
        except StopIteration:
            return aggregated

        count_loaded = 0
        for row in reader:
            if len(row) < 4: continue
            title = row[0]
            director = row[1]
            pickers_str = row[3]

            # Normalize director immediately upon loading to fix bad data
            director = normalize_director(title, director)

            # Split and clean pickers
            pickers = [p.strip() for p in pickers_str.split(", ") if p.strip()]

            key = (title, director)
            # Merge if we already have entries for this key (from normalization merging)
            aggregated[key]["pickers"] = sorted(list(set(aggregated[key]["pickers"] + pickers)))
            aggregated[key]["count"] = len(aggregated[key]["pickers"])
            count_loaded += 1

    print(f"Loaded {count_loaded} movies from CSV (merged to {len(aggregated)} unique entries).")
    return aggregated

async def get_collections_from_search(page, stop_date=None):
    print(f"Visiting search page: {MAIN_URL}")
    await page.goto(MAIN_URL, timeout=60000)

    try:
        await page.wait_for_selector("tr.all-closet-picks-table-row", timeout=30000)
    except Exception as e:
        print(f"Error waiting for rows: {e}")

    last_height = await page.evaluate("document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        try:
             await page.wait_for_timeout(2000)
             new_height = await page.evaluate("document.body.scrollHeight")
             if new_height == last_height:
                 break
             last_height = new_height
             print(f"Scrolled... Height: {new_height}")
        except Exception:
             break

    print("Extracting collections from search rows...")
    rows = await page.locator("tr.all-closet-picks-table-row").all()

    collections = []
    print(f"Found {len(rows)} rows.")

    stop_dt = None
    if stop_date:
        try:
            stop_dt = datetime.strptime(stop_date, "%b %d, %Y")
            print(f"Stopping if date <= {stop_dt}")
        except ValueError:
            print(f"Invalid stop date format: {stop_date}. Ignoring.")

    newest_date_str = None

    for row in rows:
        try:
            # Check date first if we need to stop
            date_el = row.locator("td.all-closet-picks-table-data-filmed-on")
            date_str = ""
            if await date_el.count() > 0:
                date_str = await date_el.inner_text()
                date_str = date_str.strip()

            # Store the very first date we see as the newest date
            if newest_date_str is None and date_str:
                newest_date_str = date_str

            if stop_dt and date_str:
                try:
                    current_dt = datetime.strptime(date_str, "%b %d, %Y")
                    if current_dt <= stop_dt:
                        print(f"Reached date {date_str} which is <= last scraped {stop_date}. Stopping.")
                        break
                except ValueError:
                    pass

            click_attr = await row.get_attribute("@click") or ""
            match = re.search(r"window\.location\.href\s*=\s*[\'\"]([^\'\"]+)[\'\"]", click_attr)

            full_url = ""
            if match:
                url_path = match.group(1)
                full_url = "https://www.criterion.com" + url_path
            else:
                anchor = row.locator("a")
                if await anchor.count() > 0:
                     href = await anchor.first.get_attribute("href")
                     if href:
                         full_url = "https://www.criterion.com" + href if href.startswith("/") else href

            if not full_url:
                continue

            text_content = await row.inner_text()
            name = clean_picker_name(text_content)

            collections.append({"url": full_url, "picker": name})

        except Exception as e:
            print(f"Error extracting row: {e}")

    if collections:
        print(f"First: {collections[0]}")
        print(f"Last: {collections[-1]}")

    print(f"Extracted {len(collections)} new collections.")
    return collections, newest_date_str

async def scrape_collection(browser, collection):
    url = collection["url"]
    picker = collection["picker"]
    picks = []

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(2000)

        items = await page.locator("figcaption dl").all()

        if len(items) == 0:
            print(f"\n[!] No items for {url} ({await page.title()})", end="", flush=True)

        for item in items:
            dts = item.locator("dt")
            count = await dts.count()
            title = ""
            for i in range(count):
                txt = await dts.nth(i).inner_text()
                if "Released" not in txt and "Available" not in txt:
                    title = txt
                    break
            if not title and count > 0:
                 title = await dts.last.inner_text()
            director = await item.locator("dd").first.inner_text()
            director = normalize_director(title.strip(), director.strip())

            picks.append({
                "title": title.strip(),
                "director": director,
                "picker": picker
            })
    except Exception as e:
        print(f"\nError scraping {url}: {e}")
    finally:
        await page.close()
        await context.close()
    return picks

async def get_latest_post_date(page):
    print(f"Visiting search page: {MAIN_URL}", file=sys.stderr)
    await page.goto(MAIN_URL, timeout=60000)

    try:
        await page.wait_for_selector("tr.all-closet-picks-table-row", timeout=30000)
    except Exception as e:
        print(f"Error waiting for rows: {e}", file=sys.stderr)
        return None

    rows = await page.locator("tr.all-closet-picks-table-row").all()
    if not rows:
        return None

    first_row = rows[0]
    date_el = first_row.locator("td.all-closet-picks-table-data-filmed-on")
    if await date_el.count() > 0:
        text = await date_el.inner_text()
        return text.strip()
    return None

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--last-post-date", action="store_true", help="Print the last post date from the site and exit")
    args = parser.parse_args()

    if args.last_post_date:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            date = await get_latest_post_date(page)
            if date:
                print(date)
            await context.close()
            await browser.close()
        return

    state = load_state()
    last_scraped_date = state.get("last_scraped_date")

    # Load existing data first (and normalize it)
    aggregated = load_existing_picks(OUTPUT_FILE)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Pass stop_date to stop scraping early
        collections, newest_date = await get_collections_from_search(page, stop_date=last_scraped_date)
        await page.close()
        await context.close()

        if not collections:
            print("No new collections found.")
            # We continue to write the file because existing data was normalized
        else:
            if LIMIT:
                print(f"Limiting to first {LIMIT} collections for testing.")
                collections = collections[:LIMIT]

            all_picks = []
            semaphore = asyncio.Semaphore(CONCURRENCY)

            print(f"Starting to scrape {len(collections)} collections...")

            async def scrape_with_sem(col):
                async with semaphore:
                    res = await scrape_collection(browser, col)
                    if len(res) > 0:
                        print(".", end="", flush=True)
                    else:
                        print("x", end="", flush=True)
                    return res

            tasks = [scrape_with_sem(col) for col in collections]
            results = await asyncio.gather(*tasks)
            print("\nScraping complete.")

            for res in results:
                all_picks.extend(res)

            print(f"Merging {len(all_picks)} new picks...")
            for pick in all_picks:
                key = (pick["title"], pick["director"])
                picker = pick["picker"]

                existing_pickers = set(aggregated[key]["pickers"])
                if picker not in existing_pickers:
                    aggregated[key]["pickers"].append(picker)
                    aggregated[key]["count"] = len(aggregated[key]["pickers"])

        await browser.close()

    # Sort and Write
    sorted_data = sorted(aggregated.items(), key=lambda x: x[1]["count"], reverse=True)

    print(f"Writing {len(sorted_data)} unique movies to {OUTPUT_FILE}...")
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Movie Title", "Director", "Count", "Picked By"])
        for (title, director), data in sorted_data:
            pickers_str = ", ".join(sorted(data["pickers"]))
            writer.writerow([title, director, data["count"], pickers_str])

    # Update State if we found a new date
    # If newest_date is None (no rows found?), keep old state
    if newest_date:
        save_state(newest_date)

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
