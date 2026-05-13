# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from urllib.parse import urlparse
from feedgen.feed import FeedGenerator

# =========================
# ENV SETTINGS
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "900"))

RSS_FILE = "onlykdrama_all.xml"
SEEN_FILE = "seen_posts.json"

URLS = [
    "https://onlykdrama.shop/",
    "https://onlykdrama.shop/movies/",
    "https://onlykdrama.shop/genres/upcoming/",
    "https://onlykdrama.shop/genres/koren-drama/",
    "https://onlykdrama.shop/genres/english-dubbed-movie/",
    "https://onlykdrama.shop/genres/hindi-dubbed-movie/",
    "https://onlykdrama.shop/genres/ongoing/",
    "https://onlykdrama.shop/genres/completed/"
]

ALLOWED_HOSTS = [
    "gdflix.dev",
    "new10.gdflix.net",
    "hubcloud.fyi",
    "hubcloud.foo",
    "neocloud.sbs",
    "master.onlykdrama.workers.dev",
    "new4.filepress.wiki",
    "drive.mypremiumdrive.workers.dev",
    "drive.onlykdramas.workers.dev",
    "fsl.bawoy82668.workers.dev"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# =========================
# STORAGE
# =========================
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, indent=4, ensure_ascii=False)


# =========================
# SIZE
# =========================
def extract_size(text):
    match = re.search(r"\[(.*?)\]", text)
    return match.group(1) if match else "Unknown"


# =========================
# DOWNLOAD PAGE
# =========================
def extract_download_links(page_url):
    try:
        html = requests.get(page_url, headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")

        poster = ""
        og = soup.find("meta", property="og:image")
        if og:
            poster = og.get("content", "").strip()

        page_title = ""
        title_tag = soup.find("title")
        if title_tag:
            page_title = title_tag.get_text(strip=True)

        found_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            domain = urlparse(href).netloc.lower()

            if any(host in domain for host in ALLOWED_HOSTS):
                text = a.get_text(" ", strip=True) or href
                size = extract_size(text)

                found_links.append({
                    "title": text,
                    "url": href,
                    "size": size,
                    "host": domain
                })

        unique = []
        seen_urls = set()

        for item in found_links:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique.append(item)

        return poster, unique, page_title

    except Exception as e:
        print("Extract Error:", e)
        return "", [], ""


# =========================
# CAPTION
# =========================
def build_caption(title, date, links):
    caption = f"🎬 {title}\n📅 {date}\n\n"

    for i, item in enumerate(links, start=1):
        line = (
            f"{i}. {item['title']}\n"
            f"📦 Size: {item['size']}\n"
            f"🔗 {item['url']}\n\n"
        )

        if len(caption) + len(line) > 1000:
            caption += "⚠️ More links available on source page..."
            break

        caption += line

    return caption


# =========================
# TELEGRAM
# =========================
def send_to_telegram(title, poster, date, links):
    caption = build_caption(title, date, links)

    try:
        if poster:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            payload = {
                "chat_id": CHANNEL_ID,
                "photo": poster,
                "caption": caption
            }

        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": CHANNEL_ID,
                "text": caption
            }

        requests.post(url, data=payload, timeout=30)

    except Exception as e:
        print("Telegram Error:", e)


# =========================
# SCRAPE MAIN SITE
# =========================
def scrape_site():
    all_posts = []
    seen_links = set()

    for url in URLS:
        try:
            print("Scraping:", url)

            html = requests.get(url, headers=HEADERS, timeout=20).text
            soup = BeautifulSoup(html, "html.parser")

            articles = soup.find_all("article")

            for article in articles:
                a_tag = article.find("a", href=True)
                img_tag = article.find("img")
                title_tag = article.find("h3")
                date_tag = article.find("span")

                if not a_tag or not title_tag:
                    continue

                link = a_tag["href"].strip()

                if link in seen_links:
                    continue

                seen_links.add(link)

                title = title_tag.get_text(strip=True)
                image = img_tag["src"].strip() if img_tag else ""
                date = date_tag.get_text(strip=True) if date_tag else "Unknown"

                all_posts.append({
                    "title": title,
                    "link": link,
                    "image": image,
                    "date": date
                })

        except Exception as e:
            print("Error scraping:", e)

    return all_posts


# =========================
# RSS
# =========================
def generate_rss(posts):
    fg = FeedGenerator()
    fg.title("OnlyKDrama All Updates")
    fg.link(href="https://onlykdrama.shop/")
    fg.description("All Movies, Dramas, Upcoming, Dubbed with Direct Links")

    for post in posts:
        poster, links, _ = extract_download_links(post["link"])

        desc = f"{post['date']}<br><img src='{poster}'><br><br>"

        for item in links[:20]:
            desc += f"{item['title']} | {item['size']}<br>{item['url']}<br><br>"

        fe = fg.add_entry()
        fe.title(post["title"])
        fe.link(href=post["link"])
        fe.description(desc)
        fe.guid(post["link"])

    fg.rss_file(RSS_FILE)
    print("RSS saved:", RSS_FILE)


# =========================
# MAIN TASK
# =========================
def main():
    seen = load_seen()

    posts = scrape_site()

    new_posts = []

    for post in posts:
        if post["link"] not in seen:
            new_posts.append(post)
            seen.add(post["link"])

    if new_posts:
        print("New posts found:", len(new_posts))

        for post in new_posts:
            poster, links, page_title = extract_download_links(post["link"])

            final_title = page_title if page_title else post["title"]

            if links:
                send_to_telegram(
                    final_title,
                    poster,
                    post["date"],
                    links
                )

        save_seen(seen)

    else:
        print("No new posts.")

    generate_rss(posts)


# =========================
# LOOP
# =========================
def run_bot():
    while True:
        try:
            main()
        except Exception as e:
            print("Main Loop Error:", e)

        print(f"Sleeping {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)
