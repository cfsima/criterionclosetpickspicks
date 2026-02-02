import asyncio
import csv
import re
import json
import os
from playwright.async_api import async_playwright
from collections import defaultdict

MAIN_URL = "https://www.criterion.com/closet-picks"
OUTPUT_FILE = "docs/closet_picks.csv"
STATE_FILE = "scrape_state.json"
CONCURRENCY = 3

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
    text = re.sub(r"[’']s? Closet Picks.*$", "", text, flags=re.IGNORECASE).strip()
    # Uppercase to match the existing CSV format which uses uppercase names
    return text.upper()

def normalize_director(title, director):
    # Only normalize if it is a collector's set
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

def save_state(last_url):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_scraped_url": last_url}, f, indent=2)
        print(f"State saved: {last_url}")
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

            # Split and clean pickers
            pickers = [p.strip() for p in pickers_str.split(", ") if p.strip()]

            key = (title, director)
            aggregated[key]["pickers"] = pickers
            aggregated[key]["count"] = len(pickers)
            count_loaded += 1

    print(f"Loaded {count_loaded} movies from CSV.")
    return aggregated

async def get_collections(page, stop_url=None):
    print(f"Visiting main page... (Stop URL: {stop_url})")
    await page.goto(MAIN_URL)

    # Scroll to load all
    last_height = await page.evaluate("document.body.scrollHeight")

    while True:
        # Check if stop_url is present in current DOM to stop scrolling early
        if stop_url:
            slug = stop_url.split("/")[-1]
            # Check if any anchor containing the slug exists
            count = await page.locator(f"a[href*='{slug}']").count()
            if count > 0:
                print(f"Found stop URL marker ({slug}) in content. Stopping scroll.")
                break

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        try:
            await page.wait_for_timeout(2000)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                # Double check
                await page.wait_for_timeout(2000)
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
            last_height = new_height
            print(f"Scrolled... Height: {new_height}")
        except Exception as e:
             print(f"Scroll error: {e}")
             break

    print("Extracting collections...")
    elements = await page.locator("a.popbox").all()

    collections = []
    for el in elements:
        try:
            href = await el.get_attribute("href")
            if not href: continue

            full_href = href
            if href.startswith("/"):
                full_href = "https://www.criterion.com" + href

            # Check stop condition
            if stop_url:
                 # Check strict URL or slug match
                 slug = stop_url.split("/")[-1]
                 if stop_url == full_href or (slug in full_href and slug != ""):
                     print(f"Reached last scraped URL: {full_href}. Stopping extraction.")
                     break

            title_el = el.locator("p.header_lvl2")
            if await title_el.count() > 0:
                raw_name = await title_el.inner_text()
                name = clean_picker_name(raw_name)

                collections.append({"url": full_href, "picker": name})
        except Exception as e:
            print(f"Error extracting element: {e}")

    print(f"Found {len(collections)} new collections.")
    return collections

async def scrape_collection(browser, collection):
    url = collection["url"]
    picker = collection["picker"]
    picks = []

    # Create new context for each page to avoid detection/state issues
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)

        items = await page.locator("figcaption dl").all()

        if len(items) == 0:
            print(f"\n[!] No items for {url} ({await page.title()})", end="", flush=True)

        for item in items:
            # Handle potential multiple dts (e.g. preorder text)
            dts = item.locator("dt")
            count = await dts.count()
            title = ""
            for i in range(count):
                txt = await dts.nth(i).inner_text()
                if "Released" not in txt and "Available" not in txt:
                    title = txt
                    break

            if not title and count > 0:
                 # Fallback
                 title = await dts.last.inner_text()

            director = await item.locator("dd").first.inner_text()

            # Normalize director
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

async def main():
    state = load_state()
    last_url = state.get("last_scraped_url")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Phase 1: Get Collections
        # Use a context for this
        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        collections = await get_collections(page, stop_url=last_url)
        await page.close()
        await context.close()

        if not collections:
            print("No new collections found.")
            await browser.close()
            return

        all_picks = []
        semaphore = asyncio.Semaphore(CONCURRENCY)

        print(f"Starting to scrape {len(collections)} new collections...")

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

        await browser.close()

        # Load existing data
        aggregated = load_existing_picks(OUTPUT_FILE)

        # Merge new picks
        print(f"Merging {len(all_picks)} new picks...")
        for pick in all_picks:
            key = (pick["title"], pick["director"])
            picker = pick["picker"]

            # Check if this picker is already in the list for this movie
            existing_pickers = set(aggregated[key]["pickers"])
            if picker not in existing_pickers:
                aggregated[key]["pickers"].append(picker)
                aggregated[key]["count"] = len(aggregated[key]["pickers"])

        sorted_data = sorted(aggregated.items(), key=lambda x: x[1]["count"], reverse=True)

        print(f"Writing {len(sorted_data)} unique movies to {OUTPUT_FILE}...")
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Movie Title", "Director", "Count", "Picked By"])

            for (title, director), data in sorted_data:
                pickers_str = ", ".join(data["pickers"])
                writer.writerow([title, director, data["count"], pickers_str])

        # Update State with the newest URL
        if collections:
            newest_url = collections[0]["url"]
            save_state(newest_url)

        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
