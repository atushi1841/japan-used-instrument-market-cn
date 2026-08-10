import asyncio
import random
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

BASE_URL = "https://store.ishibashi.co.jp"

# カテゴリ: 中古楽器の主要カテゴリ（pathパラメータ）
CATEGORIES = {
    "エレキギター": "エレキギター",
    "アコースティックギター": "アコースティックギター",
    "エレキベース": "エレキベース",
    "エフェクター": "エフェクター",
    "アンプ": "アンプ",
    "ドラム": "ドラム",
    "シンセサイザー・キーボード": "シンセサイザー・キーボード",
    "管楽器": "管楽器",
    "弦楽器": "弦楽器",
    "DJ・VJ・映像機器": "DJ・VJ・映像機器",
}


def extract_price(text):
    if not text:
        return None
    text_clean = text.replace("¥", "").replace("円", "").replace(",", "")
    m = re.search(r"(\d+)", text_clean)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def parse_page(html, category_label):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("a.im-products-card")
    items = []
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for card in cards:
        url = card.get("data-field") and card.get("href") or ""
        # 商品URL
        href = card.get("href", "")
        if not href:
            continue
        # 商品名: data-name属性 or title要素
        title = card.get("data-name") or ""
        if not title:
            title_el = card.select_one(".im-products-card-title")
            title = title_el.get_text(strip=True) if title_el else ""
        # 価格
        price_el = card.select_one(".im-product-sale-price, .im-product-price, .im-products-card-price")
        price = extract_price(price_el.get_text()) if price_el else None
        # 画像
        img_el = card.select_one("img")
        image_url = ""
        if img_el:
            image_url = str(img_el.get("src") or img_el.get("data-src") or "")
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        # 商品ID（URL末尾）
        m = re.search(r"/view/item/([0-9A-Za-z]+)", str(href))
        product_id = m.group(1) if m else ""
        # ブランド: タイトル先頭（【中古】の後、最初の/の前）
        brand = ""
        t = str(title).strip()
        t_clean = re.sub(r"^【[^】]*】\s*", "", t)
        parts = t_clean.split("/", 1)
        if parts:
            brand = parts[0].strip()
        items.append({
            "productId": product_id,
            "title": str(title).strip(),
            "price": price,
            "brand": brand,
            "shop": "Ishibashi Music",
            "category": category_label,
            "condition": "中古",
            "source": "ishibashi",
            "imageUrl": image_url,
            "productUrl": str(href) if str(href).startswith("http") else BASE_URL + str(href),
            "scrapedAt": now,
        })
    return items


async def fetch_page(client, url):
    for attempt in range(3):
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code in (429, 500, 502, 503, 504):
                await asyncio.sleep(2 ** attempt)
                continue
            return None
        except Exception:
            await asyncio.sleep(2 ** attempt)
    return None


async def fetch_ishibashi(client, keyword="", max_pages=2, max_items=100):
    results = []
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    categories = CATEGORIES

    for code, label in categories.items():
        if len(results) >= max_items:
            break
        # キーワード指定時は該当カテゴリのみスキャン
        if keyword and keyword.lower() not in code.lower():
            continue
        offset = 0
        for page in range(max_pages):
            if len(results) >= max_items:
                break
            params = f"?limit=72&path={code}&s4%5B0%5D=%E4%B8%AD%E5%8F%A4&q=&fmt=json&style=0&o={offset}"
            url = BASE_URL + "/search" + params
            html = await fetch_page(client, url)
            if not html:
                break
            items = parse_page(html, label)
            if not items:
                break
            for it in items:
                if keyword and keyword.lower() not in it["title"].lower():
                    continue
                results.append(it)
                if len(results) >= max_items:
                    break
            offset += 72
            if len(items) < 72:
                break
            await asyncio.sleep(random.uniform(1, 2))

    return results[:max_items]
