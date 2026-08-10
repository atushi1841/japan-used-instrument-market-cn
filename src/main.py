import asyncio
import json
import sys

import httpx

try:
    from apify import Actor
except Exception:
    Actor = None


async def run(actor_input, actor=None):
    search_keyword = actor_input.get("searchKeyword") or ""
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
                if actor is not None:
                    await actor.push_data(item)
                else:
                    print(json.dumps(item, ensure_ascii=False))
                collected += 1
                if collected >= max_items:
                    break


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
