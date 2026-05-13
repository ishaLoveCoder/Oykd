# ============================================================
# bot.py (ONLYKDRAMA FULL FIXED RSS + TELEBOT AUTO POSTER)
# ============================================================
# pip install pyTelegramBotAPI requests beautifulsoup4 feedgen lxml
# ============================================================

import os
import re
import json
import time
import telebot
import requests

from bs4 import BeautifulSoup
from urllib.parse import urlparse
from feedgen.feed import FeedGenerator

# =========================
# ENV SETTINGS
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")   # @channelusername or -100...
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "900"))

RSS_FILE = "onlykdrama_all.xml"
SEEN_FILE = "seen_posts.json"

# =========================
# TELEBOT
# =========================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# =========================
# SOURCES
# =========================
URLS = [
    "https://onlykdrama.shop/",
    "https://onlykdrama.shop/movies/",
    "https://onlykdrama.shop/genres/upcoming/",
    "https://onlykdrama.shop/genres/koren-drama/",
    "https://onlykdrama.shop/genres/english-dubbed-movie/",
    "https://onlykdrama.shop/genres/hindi-dubbed-movie/",
    "https://onlykdrama.shop/genres/ongoing/",
    "https://onlykdrama.shop/genres/completed/",
    "https://onlykdrama.shop/genres/hindi-dubbed-drama/",
    "https://onlykdrama.shop/genres/english-dubbed-drama/",
    "https://onlykdrama.shop/reupload/"
]

# =========================
# ALLOWED HOSTS
# =========================
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
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile)"
}


# =========================
# STORAGE
# =========================
def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, indent=4, ensure_ascii=False)


# =========================
# HELPERS
# =========================
def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def extract_size(text):
    match = re.search(r"\[([^\]]*(?:GB|MB)[^\]]*)\]", text, re.I)
    return match.group(1).strip() if match else "Unknown"


def dedupe_links(links):
    unique = []
    seen = set()

    for item in links:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique


# =========================
# PRIORITY SORT
# =========================
def sort_links_by_priority(links):
    priority = {
        "gdflix.dev": 1,
        "new10.gdflix.net": 2,
        "hubcloud.fyi": 3,
        "hubcloud.foo": 4,
        "neocloud.sbs": 5,
        "new4.filepress.wiki": 6
    }

    return sorted(
        links,
        key=lambda x: priority.get(
            urlparse(x["url"]).netloc.lower(),
            999
        )
    )


# =========================
# EXTRACT DOWNLOAD LINKS
# =========================
def extract_download_links(page_url):
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=25)
        html = r.text

        soup = BeautifulSoup(html, "lxml")

        # ---------- Poster ----------
        poster = ""

        og = soup.find("meta", property="og:image")
        if og:
            poster = og.get("content", "").strip()

        if not poster:
            img = soup.find("img")
            if img:
                poster = img.get("src", "").strip()

        # ---------- Title ----------
        page_title = ""

        meta_title = soup.find("meta", property="og:title")
        if meta_title:
            page_title = clean_text(meta_title.get("content", ""))

        if not page_title:
            title_tag = soup.find("title")
            if title_tag:
                page_title = clean_text(title_tag.get_text())

        # ---------- Date ----------
        date = "Unknown"

        date_tag = soup.find("meta", property="article:published_time")
        if date_tag:
            date = date_tag.get("content", "").split("T")[0]

        if date == "Unknown":
            possible_date = soup.find(["time", "span"])
            if possible_date:
                date = clean_text(possible_date.get_text())

        # ---------- Links ----------
        found_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()

            if not href.startswith("http"):
                continue

            domain = urlparse(href).netloc.lower()

            if any(host in domain for host in ALLOWED_HOSTS):
                text = clean_text(a.get_text(" ", strip=True))

                if not text:
                    text = href

                found_links.append({
                    "title": text,
                    "url": href,
                    "size": extract_size(text),
                    "host": domain
                })

        found_links = dedupe_links(found_links)
        found_links = sort_links_by_priority(found_links)

        return {
            "title": page_title,
            "poster": poster,
            "date": date,
            "links": found_links
        }

    except Exception as e:
        print("Extract Error:", e)
        return {
            "title": "",
            "poster": "",
            "date": "Unknown",
            "links": []
        }


# =========================
# SCRAPE SITE
# =========================
def scrape_site():
    all_posts = []
    seen_local = set()

    for url in URLS:
        try:
            print("Scraping:", url)

            html = requests.get(url, headers=HEADERS, timeout=25).text
            soup = BeautifulSoup(html, "lxml")

            # WordPress articles
            articles = soup.find_all("article")

            for article in articles:
                a_tag = article.find("a", href=True)

                if not a_tag:
                    continue

                link = a_tag["href"].strip()

                if not link.startswith("http"):
                    continue

                if link in seen_local:
                    continue

                seen_local.add(link)

                title = ""
                h3 = article.find(["h2", "h3"])
                if h3:
                    title = clean_text(h3.get_text())

                if not title:
                    title = clean_text(a_tag.get_text())

                image = ""
                img = article.find("img")
                if img:
                    image = img.get("src", "").strip()

                date = "Unknown"

                span = article.find(["span", "time"])
                if span:
                    date = clean_text(span.get_text())

                all_posts.append({
                    "title": title,
                    "link": link,
                    "image": image,
                    "date": date
                })

        except Exception as e:
            print("Scrape Error:", url, e)

    return all_posts


# =========================
# CAPTION BUILDER
# =========================
def build_caption(data):
    caption = f"🎬 <b>{data['title']}</b>\n📅 {data['date']}\n\n"

    for i, item in enumerate(data["links"], start=1):
        line = (
            f"{i}. <b>{item['title']}</b>\n"
            f"📦 {item['size']}\n"
            f"🔗 {item['url']}\n\n"
        )

        if len(caption) + len(line) > 900:
            caption += "⚠️ More links available on source page..."
            break

        caption += line

    return caption


# =========================
# TELEGRAM
# =========================
def send_to_telegram(data):
    if not data["links"]:
        return

    caption = build_caption(data)

    try:
        if data["poster"]:
            bot.send_photo(
                CHANNEL_ID,
                data["poster"],
                caption=caption
            )
        else:
            bot.send_message(
                CHANNEL_ID,
                caption
            )

        print("Posted:", data["title"])

    except Exception as e:
        print("Telegram Error:", e)


# =========================
# RSS
# =========================
def generate_rss(posts):
    fg = FeedGenerator()

    fg.title("OnlyKDrama All Updates")
    fg.link(href="https://onlykdrama.shop/")
    fg.description("Movies + Dramas + Ongoing + Completed + Direct Links")

    for post in posts:
        data = extract_download_links(post["link"])

        if not data["links"]:
            continue

        desc = f"📅 {data['date']}<br><img src='{data['poster']}'><br><br>"

        for item in data["links"][:20]:
            desc += (
                f"{item['title']} | {item['size']}<br>"
                f"{item['url']}<br><br>"
            )

        fe = fg.add_entry()
        fe.title(data["title"] or post["title"])
        fe.link(href=post["link"])
        fe.description(desc)
        fe.guid(post["link"])

    fg.rss_file(RSS_FILE)
    print("RSS updated:", RSS_FILE)


# =========================
# MAIN
# =========================
def main():
    seen = load_seen()

    posts = scrape_site()

    new_posts = []

    for post in posts:
        # Every new episode/post URL unique
        if post["link"] not in seen:
            new_posts.append(post)
            seen.add(post["link"])

    if new_posts:
        print("New posts:", len(new_posts))

        # oldest first
        for post in reversed(new_posts):
            print("Opening:", post["link"])

            data = extract_download_links(post["link"])

            if not data["title"]:
                data["title"] = post["title"]

            if data["date"] == "Unknown":
                data["date"] = post["date"]

            send_to_telegram(data)

            time.sleep(3)

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

        print(f"Sleeping {CHECK_INTERVAL} seconds...\n")
        time.sleep(CHECK_INTERVAL)
