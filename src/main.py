import asyncio
import datetime
import json
import sys
import unicodedata

import httpx

try:
    from apify import Actor
except Exception:
    Actor = None


def _norm_key(text):
    return unicodedata.normalize("NFC", str(text)).casefold()


async def run(actor_input, actor=None):
    search_keyword = actor_input.get("searchKeyword") or ""
    stats_mode = actor_input.get("statsMode", False)
    stats_keyword = actor_input.get("statsKeyword", "") or ""
    collected_items = []
    max_items = int(actor_input.get("maxItems", 100))
    max_pages = int(actor_input.get("maxPages", 2))
    sources = [s.strip() for s in actor_input.get("sources", "digimart,ishibashi").split(",") if s.strip()]

    proxy_url = None
    if actor is not None:
        proxy_config = await actor.create_proxy_configuration(actor_proxy_input=actor_input.get("proxyConfiguration"))
        if proxy_config:
            proxy_url = await proxy_config.new_url()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9",
    }

    async with httpx.AsyncClient(proxy=proxy_url, headers=headers, timeout=30.0, follow_redirects=True) as client:
        collected = 0
        for src in sources:
            if collected >= max_items:
                break
            remaining = max_items - collected
            items = []
            if src == "digimart":
                from digimart import parse_page, fetch_page, extract_data_items
                import urllib.parse
                # Digimart: dataLayer JSON + HTMLカード
                base = "https://www.digimart.net/search?dispMode=ALL&keyword={kw}&currentPage={page}&maxCount=20"
                if search_keyword:
                    keywords = [search_keyword]
                else:
                    keywords = ["ギター"]
                for kw in keywords:
                    if collected >= max_items:
                        break
                    for page in range(1, max_pages + 1):
                        if collected >= max_items:
                            break
                        url = base.format(kw=urllib.parse.quote(kw), page=page)
                        html = await fetch_page(client, url)
                        if not html:
                            break
                        page_items = parse_page(html)
                        for it in page_items:
                            it["source"] = "digimart"
                            it["shop"] = it.get("shopName") or "Digimart"
                            it["condition"] = it.get("instruTypeLabel") or it.get("condition") or ""
                            items.append(it)
                            if len(items) >= remaining:
                                break
                        if len(page_items) < 20:
                            break
                        await asyncio.sleep(1)
                items = items[:remaining]
            elif src == "ishibashi":
                from sources.ishibashi import fetch_ishibashi
                items = await fetch_ishibashi(client, keyword=search_keyword, max_pages=max_pages, max_items=remaining)

            for item in items:
                if stats_mode:
                    collected_items.append(item)
                else:
                    if actor is not None:
                        await actor.push_data(item)
                    else:
                        print(json.dumps(item, ensure_ascii=False))
                collected += 1
                if collected >= max_items:
                    break

        if stats_mode:
            # filter by statsKeyword
            if stats_keyword:
                filtered = []
                nk = _norm_key(stats_keyword)
                for it in collected_items:
                    title = it.get("title") or ""
                    if nk in _norm_key(title):
                        filtered.append(it)
                collected_items = filtered

            prices = []
            for it in collected_items:
                try:
                    p = int(it.get("price"))
                    prices.append(p)
                except (TypeError, ValueError):
                    continue

            if prices:
                price_min = min(prices)
                price_max = max(prices)
                price_avg = int(sum(prices) / len(prices))
                sorted_prices = sorted(prices)
                n = len(sorted_prices)
                if n % 2 == 1:
                    price_median = sorted_prices[n // 2]
                else:
                    price_median = (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) // 2
                sample_items = []
                for it in collected_items[:3]:
                    sample_items.append({
                        "title": it.get("title", ""),
                        "price": it.get("price"),
                        "detailUrl": it.get("detailUrl") or it.get("url") or "",
                        "shop": it.get("shop") or it.get("shopName") or ""
                    })
                stats_result = {
                    "statsType": "japan-instrument-price-cn",
                    "keyword": stats_keyword or search_keyword or "",
                    "count": len(prices),
                    "priceMin": price_min,
                    "priceMax": price_max,
                    "priceAvg": price_avg,
                    "priceMedian": price_median,
                    "sampleItems": sample_items,
                    "collectedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            else:
                stats_result = {
                    "statsType": "japan-instrument-price-cn",
                    "keyword": stats_keyword or search_keyword or "",
                    "count": 0,
                    "priceMin": None,
                    "priceMax": None,
                    "priceAvg": None,
                    "priceMedian": None,
                    "sampleItems": [],
                    "collectedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                }

            if actor is not None:
                await actor.push_data(stats_result)
            else:
                print(json.dumps(stats_result, ensure_ascii=False))


async def main():
    if Actor is not None:
        async with Actor:
            actor_input = await Actor.get_input() or {}
            await run(actor_input, actor=Actor)
    else:
        raw = sys.stdin.read() or ""
        try:
            actor_input = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            actor_input = {}
        await run(actor_input, actor=None)


if __name__ == "__main__":
    asyncio.run(main())
