import asyncio
import csv
import re
from playwright.async_api import async_playwright
from collections import defaultdict

MAIN_URL = "https://www.criterion.com/closet-picks"
OUTPUT_FILE = "closet_picks.csv"
CONCURRENCY = 3

def clean_picker_name(text):
    text = re.sub(r"[’']s? Closet Picks.*$", "", text, flags=re.IGNORECASE).strip()
    return text

async def get_collections(page):
    print("Visiting main page...")
    await page.goto(MAIN_URL)

    # Scroll to load all
    last_height = await page.evaluate("document.body.scrollHeight")
    while True:
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

            title_el = el.locator("p.header_lvl2")
            if await title_el.count() > 0:
                raw_name = await title_el.inner_text()
                name = clean_picker_name(raw_name)
                if href.startswith("/"):
                    href = "https://www.criterion.com" + href

                collections.append({"url": href, "picker": name})
        except Exception as e:
            print(f"Error extracting element: {e}")

    print(f"Found {len(collections)} collections.")
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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Phase 1: Get Collections
        # Use a context for this
        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        collections = await get_collections(page)
        await page.close()
        await context.close()

        # Limit for testing? No, user wants full. But for debugging...
        # Let's try first 5 again to see if it works with concurrency 1
        # collections = collections[:5]

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

        for pick in all_picks:
            key = (pick["title"], pick["director"])
            aggregated[key]["count"] += 1
            aggregated[key]["pickers"].append(pick["picker"])

        sorted_data = sorted(aggregated.items(), key=lambda x: x[1]["count"], reverse=True)

        print(f"Writing {len(sorted_data)} unique movies to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Movie Title", "Director", "Count", "Picked By"])

            for (title, director), data in sorted_data:
                pickers_str = ", ".join(data["pickers"])
                writer.writerow([title, director, data["count"], pickers_str])

        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
