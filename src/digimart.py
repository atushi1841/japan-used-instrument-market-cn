import asyncio
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup


def extract_price(text):
    if not text:
        return None
    text_clean = text.replace('¥', '').replace('円', '').replace(',', '')
    m = re.search(r'(\d+)', text_clean)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def split_top_level(s, sep=','):
    parts = []
    depth = 0
    in_str = False
    quote = ''
    cur = []
    for ch in s:
        if in_str:
            cur.append(ch)
            if ch == '\\':
                continue
            elif ch == quote:
                in_str = False
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            cur.append(ch)
            continue
        if ch in '({[':
            depth += 1
        elif ch in ')}]':
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if ''.join(cur).strip():
        parts.append(''.join(cur).strip())
    return parts


def parse_js_value(val):
    val = val.strip()
    if not val:
        return None
    if val.startswith('{') and val.endswith('}'):
        return parse_js_object(val)
    if val.startswith('[') and val.endswith(']'):
        inner = val[1:-1].strip()
        if not inner:
            return []
        parts = split_top_level(inner, ',')
        return [parse_js_value(p) for p in parts]
    if val in ('true', 'True'):
        return True
    if val in ('false', 'False'):
        return False
    if val in ('null', 'None'):
        return None
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            return val[1:-1]
        return val


def find_colon(s):
    depth = 0
    in_str = False
    quote = ''
    for i, ch in enumerate(s):
        if in_str:
            if ch == '\\':
                continue
            elif ch == quote:
                in_str = False
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            continue
        if ch in '({[':
            depth += 1
            continue
        if ch in ')}]':
            depth -= 1
            continue
        if ch == ':' and depth == 0:
            return i
    return -1


def parse_js_object(s):
    s = s.strip()
    if not s.startswith('{') or not s.endswith('}'):
        return {}
    inner = s[1:-1].strip()
    if not inner:
        return {}
    fields = split_top_level(inner, ',')
    obj = {}
    for f in fields:
        idx = find_colon(f)
        if idx == -1:
            continue
        key = f[:idx].strip().strip('"\'')
        val = f[idx + 1:].strip()
        obj[key] = parse_js_value(val)
    return obj


def parse_js_array(s):
    s = s.strip()
    if not s.startswith('[') or not s.endswith(']'):
        return []
    inner = s[1:-1].strip()
    if not inner:
        return []
    parts = split_top_level(inner, ',')
    return [parse_js_value(p) for p in parts]


def extract_data_items(html):
    # view_item_list イベントを含む dataLayer.push ブロックを探す
    # （最初の dataLayer.push は user_id_custom 等の別ブロックのことがある）
    marker = 'dataLayer.push({'
    search_from = 0
    while True:
        start = html.find(marker, search_from)
        if start == -1:
            return []
        # このブロックに view_item_list と items: が含まれるか先読み
        i = start + len(marker)
        depth = 0
        in_str = False
        quote = ''
        end = -1
        for idx in range(i, len(html)):
            ch = html[idx]
            if in_str:
                if ch == '\\':
                    continue
                elif ch == quote:
                    in_str = False
                continue
            if ch in ("'", '"'):
                in_str = True
                quote = ch
                continue
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        if end == -1:
            return []
        block = html[i:end]
        if 'view_item_list' in block and re.search(r'items\s*:\s*\[', block):
            break
        search_from = start + 1
    m = re.search(r'items\s*:\s*\[', block)
    if not m:
        return []
    start_arr = m.end() - 1
    depth = 0
    in_str = False
    quote = ''
    end_arr = -1
    for idx in range(start_arr, len(block)):
        ch = block[idx]
        if in_str:
            if ch == '\\':
                continue
            elif ch == quote:
                in_str = False
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end_arr = idx
                break
    if end_arr == -1:
        return []
    arr_str = block[start_arr:end_arr + 1]
    return parse_js_array(arr_str)


def parse_page(html):
    items = extract_data_items(html)
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.select('div.itemSearchBlock.itemSearchListItem')
    html_items = []
    for card in cards:
        product_id = card.get('data-instrument-cd')
        title_elem = card.select_one('p.ttl a')
        title = title_elem.get_text(strip=True) if title_elem else ''
        product_url = title_elem.get('href') if title_elem else ''
        shop_elem = card.select_one('p.itemShopInfo a')
        shop_name = shop_elem.get_text(strip=True) if shop_elem else ''
        fixed_price_elem = card.select_one('p.fixedPrice span')
        list_price = extract_price(fixed_price_elem.get_text()) if fixed_price_elem else None
        price_elem = card.select_one('p.price')
        price = extract_price(price_elem.get_text()) if price_elem else None
        cond_elem = card.select_one('p.state span.tooltip')
        condition = cond_elem.get_text(strip=True) if cond_elem else ''
        reg_elem = card.select_one('ul.itemDateInfo li:nth-of-type(2)')
        registered = None
        if reg_elem:
            txt = reg_elem.get_text(strip=True)
            m = re.search(r'登録：(.+)', txt)
            if m:
                registered = m.group(1).strip()
        img_elem = card.select_one('div.pic img')
        image_url = img_elem.get('src') if img_elem else ''
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        if product_url.startswith('/'):
            product_url = 'https://www.digimart.net' + product_url
        html_items.append({
            'productId': product_id,
            'title': title,
            'shopName': shop_name,
            'listPrice': list_price,
            'price': price,
            'condition': condition,
            'registeredAt': registered,
            'imageUrl': image_url,
            'productUrl': product_url,
        })

    data_map = {}
    for it in items:
        pid = it.get('item_id')
        if pid:
            data_map[str(pid)] = it
    html_map = {}
    for it in html_items:
        pid = it.get('productId')
        if pid:
            html_map[str(pid)] = it

    all_ids = set(data_map.keys()) | set(html_map.keys())
    results = []
    instru_labels = {
        '1': '新品',
        '2': '中古',
        '3': 'ビンテージ',
        '4': '新品アウトレット',
        '5': 'B-stock',
    }
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    for pid in all_ids:
        d = data_map.get(pid, {})
        h = html_map.get(pid, {})
        product = {}
        product['productId'] = pid
        product['title'] = d.get('item_name') or h.get('title')
        product['brand'] = d.get('item_brand')
        product['category'] = d.get('item_category')
        product['price'] = d.get('price') or h.get('price')
        product['listPrice'] = h.get('listPrice')
        product['condition'] = h.get('condition')
        instru = d.get('instru_type')
        product['instruType'] = instru
        if instru is not None:
            product['instruTypeLabel'] = instru_labels.get(str(instru))
        else:
            product['instruTypeLabel'] = None
        product['inStock'] = d.get('in_stock') if 'in_stock' in d else True
        product['shopName'] = h.get('shopName')
        product['registeredAt'] = h.get('registeredAt')
        product['imageUrl'] = h.get('imageUrl')
        product['productUrl'] = h.get('productUrl')
        product['scrapedAt'] = now
        results.append(product)

    return results


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
