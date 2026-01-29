import asyncio
import csv
import re
import json
import os
from playwright.async_api import async_playwright
from collections import defaultdict

MAIN_URL = "https://www.criterion.com/closet-picks"
OUTPUT_FILE = "closet_picks.csv"
STATE_FILE = "scrape_state.json"
CONCURRENCY = 3

def clean_picker_name(text):
    text = re.sub(r"[’']s? Closet Picks.*$", "", text, flags=re.IGNORECASE).strip()
    # Uppercase to match the existing CSV format which uses uppercase names
    return text.upper()

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
            # Use the last dt if multiple, or filter out .preorderText
            # title = await item.locator("dt:not(.preorderText)").inner_text()
            # To be safer, let's get all dts and pick the one that looks like a title (not starting with Released?)
            # Or simpler: usually the title is the one without class, or the second one if pre-order.

            # Let's try matching specifically.
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
            picks.append({
                "title": title.strip(),
                "director": director.strip(),
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
