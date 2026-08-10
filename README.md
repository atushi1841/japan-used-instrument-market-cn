# 日本二手乐器市场 — 跨店比价（Digimart+Ishibashi）

**日本最大の楽器ECデジマートとイシバシ楽器の中古楽器価格を横断比較。Fender、Gibsonなどのギター・ベース・アンプ。**

> 🇯🇵 English/日本語版: [Japan Market](https://apify.com/fruitful_quintessence)

## Input

| Field | Type | Default | Description |
|---|---|---|---|
| `searchKeyword` | string | `Fender` | 搜索关键词 |
| `maxItems` | integer | 100 | 最大获取件数 |
| `maxPages` | integer | 2 | 每个来源的最大页数 |
| `sources` | string | `digimart,ishibashi` | 数据来源（逗号分隔） |
| `proxyConfiguration` | object | — | Apify proxy |

## Output Sample

```json
{
  "productId": "DS10679928",
  "title": "Made in Japan Limited Active Modern Stratocaster HSS フェンダー",
  "brand": "Fender",
  "category": "エレキギター",
  "price": 275000,
  "condition": "新品",
  "inStock": true,
  "shopName": "イシバシ楽器 デジマート店",
  "imageUrl": "https://img.digimart.net/prdimg/s/2b/daef69e60a8b5ba9d6147894732cc4f424264d.jpg",
  "productUrl": "https://www.digimart.net/",
  "source": "ishibashi",
  "shop": "Ishibashi",
  "scrapedAt": "2026-08-10T10:00:00Z"
}
```

## Use Cases

- 代购/转卖: 发现低价商品，赚取差价
- 行情调研: 追踪特定型号的市场价格走势
- 库存监控: 监控店铺的库存变化

## Pricing

按事件计费 — $0.00005/次运行 + **$0.002/条数据**

## Data Source

仅收集公开的商品信息（名称、价格、品牌、库存状态）。
