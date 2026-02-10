import asyncio
import csv
import re
import json
import os
from playwright.async_api import async_playwright
from collections import defaultdict

# Use the search page as the main URL
MAIN_URL = "https://www.criterion.com/closet-picks/search"
OUTPUT_FILE = "docs/closet_picks.csv"
TEST_OUTPUT_FILE = "docs/closet_picks_search_test.csv"
CONCURRENCY = 5
LIMIT = None # Full run

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
    "Monsters and Madmen": "Various",
    "Rebel Samurai: Sixties Swordplay Classics": "Various",
    "Jackie Chan: Emergence of a Superstar": "Jackie Chan",
}

IGNORE_TITLES = {
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
        return director
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

async def get_collections_from_search(page):
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

    for row in rows:
        try:
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

    print(f"Extracted {len(collections)} collections.")
    return collections

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

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        collections = await get_collections_from_search(page)
        await page.close()
        await context.close()

        if not collections:
            print("No collections found.")
            await browser.close()
            return

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

        await browser.close()

        aggregated = defaultdict(lambda: {"count": 0, "pickers": []})

        print(f"Aggregating {len(all_picks)} picks...")
        for pick in all_picks:
            key = (pick["title"], pick["director"])
            picker = pick["picker"]

            existing_pickers = set(aggregated[key]["pickers"])
            if picker not in existing_pickers:
                aggregated[key]["pickers"].append(picker)
                aggregated[key]["count"] = len(aggregated[key]["pickers"])

        sorted_data = sorted(aggregated.items(), key=lambda x: x[1]["count"], reverse=True)

        print(f"Writing {len(sorted_data)} unique movies to {TEST_OUTPUT_FILE}...")
        os.makedirs(os.path.dirname(TEST_OUTPUT_FILE), exist_ok=True)
        with open(TEST_OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Movie Title", "Director", "Count", "Picked By"])
            for (title, director), data in sorted_data:
                pickers_str = ", ".join(sorted(data["pickers"]))
                writer.writerow([title, director, data["count"], pickers_str])

        # Write to Main File
        print(f"Writing {len(sorted_data)} unique movies to {OUTPUT_FILE}...")
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Movie Title", "Director", "Count", "Picked By"])
            for (title, director), data in sorted_data:
                pickers_str = ", ".join(sorted(data["pickers"]))
                writer.writerow([title, director, data["count"], pickers_str])

        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
