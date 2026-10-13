# MAP Violation Monitor for Google Shopping (Python)

Find every Google Shopping seller advertising your products below your minimum advertised price (MAP). List your products and MAP prices in a CSV, run `map_monitor.py check` daily, and each run saves the full API response as timestamped evidence (with a SHA-256 hash), appends every below-MAP offer to `violations.csv`, and `report` prints the day's violations grouped by seller. Python with one dependency (`requests`).

> **Uses the CrawlerData API — you need an API key** (free trial credits available at https://app.crawlerdata.com/register). Each product check costs 1 credit per 10 sellers returned (minimum 1).

> **Not legal advice.** What counts as a MAP violation, and what you can do about it, is defined by your MAP policy and the law in each market. This tool only records what Google Shopping showed.

## Features

- All Google Shopping sellers for each product, compared with your MAP (item price by default, or total price with `--compare total_price`)
- **Evidence:** every check stores the job record (ID, `createdAt`, `completedAt`, params) and the full result in `evidence/YYYY-MM-DD/<product>_<country>_<job>.json`; each violation row carries the file path and its SHA-256
- `verify` re-hashes the evidence files to show they haven't been edited
- `report`: violations for a day, grouped by seller, plus repeat offenders (below MAP on more than one day)
- `condition_flag` marks offers whose title says used, refurbished, renewed, open box or pre-owned (`--skip-condition` drops them)
- `--ignore` skips merchants (you, or resellers running an approved promotion)
- Per-product `include` / `exclude` keywords so accessories and other sizes aren't flagged
- MAP per country and currency

## Quickstart

```bash
git clone https://github.com/CrawlerData/map-violation-monitor.git
cd map-violation-monitor
pip install -r requirements.txt

export CRAWLERDATA_API_KEY="your_api_key"        # PowerShell: $env:CRAWLERDATA_API_KEY="your_api_key"

python map_monitor.py check          # run daily
python map_monitor.py report
python map_monitor.py verify
```

## Input: `map_prices.csv`

```csv
product_id,country,map_price,label,include,exclude
11726664398501807381,us,249.99,Sony WH-1000XM5 (example MAP),,case;cushion
7580511071886337697,us,129.99,Samsung Galaxy Buds3 FE (example MAP),,case
```

The MAP values in this file are made up for the demo; they are not the manufacturers' real MAP.

- `product_id`: the Google Shopping product ID. Find it by searching Google Shopping for **brand + model** (for example with the [Google Shopping scraper](https://github.com/CrawlerData/google-shopping-scraper)). Don't search by a bare GTIN/UPC: Google Shopping often returns unrelated products for a barcode.
- **One model can have several product IDs** (different listings, colors, bundles), each with its own sellers. A seller below MAP on a listing you aren't checking won't show up, so add every listing that is really your product.
- `map_price` is in the currency of `country` (USD for `us`, EUR for `de`, ...). Set a MAP per country rather than converting.
- `include` / `exclude`: optional `;`-separated words an offer title must / must not contain.

## Sample output

Real run on 13 October 2026 with the example file above:

```text
$ python map_monitor.py check
Sony WH-1000XM5 (example MAP) (us): 10 sellers, 2 below MAP 249.99  [evidence evidence/2026-10-13/11726664398501807381_us_6acdbfb1aaddb7eaed95a943.json]
Samsung Galaxy Buds3 FE (example MAP) (us): 10 sellers, 4 below MAP 129.99  [evidence evidence/2026-10-13/7580511071886337697_us_6acdbfc9aaddb7eaed95a951.json]

6 violation(s) appended to violations.csv. Credits used: 2

$ python map_monitor.py report
MAP report for 2026-10-13: 6 offer(s) below MAP from 5 seller(s)

Best Buy: 2 offer(s)
  Sony WH-1000XM5 (example MAP) (us): 228 USD vs MAP 249.99 (-21.99, -8.8%)
    checked 2026-10-13T05:21:12.959Z, job 6acdbfb1aaddb7eaed95a943, evidence evidence/2026-10-13/11726664398501807381_us_6acdbfb1aaddb7eaed95a943.json
  Samsung Galaxy Buds3 FE (example MAP) (us): 117.29 USD vs MAP 129.99 (-12.7, -9.8%)
    checked 2026-10-13T05:21:36.021Z, job 6acdbfc9aaddb7eaed95a951, evidence evidence/2026-10-13/7580511071886337697_us_6acdbfc9aaddb7eaed95a951.json
Walmart: 1 offer(s)
  Sony WH-1000XM5 (example MAP) (us): 248 USD vs MAP 249.99 (-1.99, -0.8%)
    ...
Walmart - Truly Trending: 1 offer(s)
  Samsung Galaxy Buds3 FE (example MAP) (us): 94.99 USD vs MAP 129.99 (-35.0, -26.9%)
    ...

$ python map_monitor.py verify
Checked 2 evidence file(s): 2 OK, 0 problem(s)
```

`violations.csv` ([sample](examples/sample-violations.csv)), one row per offer below MAP:

```csv
checked_at,job_id,product_id,country,label,map_price,merchant,offer_title,price,shipping,total_price,currency,availability,below_map_by,below_map_pct,condition_flag,evidence_file,evidence_sha256
2026-10-13T05:21:12.959Z,6acdbfb1aaddb7eaed95a943,11726664398501807381,us,Sony WH-1000XM5 (example MAP),249.99,Best Buy,Sony - WH-1000XM5 Wireless Noise Cancelling Over-the-Ear Headphones - Black,228,0,228,USD,In Stock,21.99,8.8,,evidence/2026-10-13/11726664398501807381_us_6acdbfb1aaddb7eaed95a943.json,5cd6c48466b034934808ecbbc71b95d6a057cc783b36271b27776f353480e9b5
```

An evidence file from that run is in [`examples/sample-evidence.json`](examples/sample-evidence.json).

## What the evidence contains (and doesn't)

Contains, per check: when it ran (`job.createdAt` / `job.completedAt`, UTC), the job ID, product, country, and every seller with merchant name, offer title, price, shipping, total price and availability.

Does not contain:

- **A screenshot.** The API returns structured data, not an image. Capture screenshots separately if your process requires them.
- **A link to the offer.** Seller links are usually not returned; identify an offer by merchant, offer title and timestamp.
- **The seller's own site.** This is what Google Shopping listed at that moment. Prices can change minutes later.

## Before acting on a flag

- **Same product and condition?** Read `offer_title` and `condition_flag`. Used, open-box or bundled offers may fall outside your policy.
- **One-off?** Many teams act only when a seller is below MAP on two consecutive checks; `report` lists repeat offenders.
- **Approved promotion?** If many sellers drop to the same price at once, check for an authorised promotion first (and add those sellers to `--ignore` while it runs).
- **Right country and currency?**

## Cost per run

Each product is one Google Shopping sellers request: **1 credit per 10 sellers returned**, rounded up, minimum 1. The sample run (2 products, 10 sellers each) cost 2 credits.

Example: 500 products checked twice a day with 21-30 sellers each = 500 × 2 × 3 × 30 = 90,000 credits a month: $90 at the smallest pack's $1.00 per 1,000 credits, less on larger packs (down to $0.30 per 1,000, see [pricing](https://crawlerdata.com/pricing)). Failed jobs are free.

## Options

| Command / option | Default | Description |
| --- | --- | --- |
| `-o, --output FILE` | `violations.csv` | Violations CSV (goes before the command) |
| `check -i FILE` | `map_prices.csv` | Products and MAP |
| `check --evidence-dir DIR` | `evidence` | Where responses are saved |
| `check --ignore a,b` | env `MAP_IGNORE_MERCHANTS` | Merchant names to skip (case-insensitive substring) |
| `check --skip-condition` | off | Skip used / refurbished / renewed / open-box / pre-owned offers |
| `check --compare` | `price` | `price` (item price) or `total_price` (with shipping) |
| `report --day YYYY-MM-DD` | latest | Day to report |
| `verify` | | Re-hash evidence files |

Schedule `check` with cron or Windows Task Scheduler (examples in the [price tracker README](https://github.com/CrawlerData/google-shopping-price-tracker#running-it-on-a-schedule)). For large catalogs, use the `fast` or `regular` queue (`client.submit()` + `client.wait()`) or a `postbackUrl` webhook instead of one live request per product; all queues cost the same.

## Limits

- Google Shopping only: sellers advertising below MAP on their own sites or other channels won't show up.
- Country-level view: one of 31 countries per request. Results can vary by location within a country and by time.
- Sellers requests take tens of seconds and occasionally fail; the client retries failed jobs, which are not charged.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `HTTP 401` | The API key is missing or wrong. Check `echo $CRAWLERDATA_API_KEY` (or `$env:CRAWLERDATA_API_KEY` in PowerShell) and create a key under API Access in the [dashboard](https://app.crawlerdata.com). |
| `HTTP 402` | You are out of credits. Buy a credit pack in the dashboard (from $1.00 down to $0.30 per 1,000 credits, see [pricing](https://crawlerdata.com/pricing)). |
| `HTTP 429` | Rate limit: 100 requests per minute and 20 per second per key. The client waits until `X-RateLimit-Reset` and retries automatically; for big batches, spread requests out. |
| Timeouts | Live requests return when Google has been fetched: a few seconds for search, 30 to 120 seconds for Google Shopping sellers. The client uses a 200 second timeout. |
| `job ... failed` | The HTTP call worked but the job did not (for example Google blocked that attempt). Failed jobs cost 0 credits and the client retries them twice before giving up. |

## Links

- [CrawlerData](https://crawlerdata.com)
- [MAP monitoring with CrawlerData](https://crawlerdata.com/solutions/map-monitoring)
- [Google Shopping Sellers API](https://crawlerdata.com/apis/google-shopping-sellers-api)
- [API docs](https://app.crawlerdata.com/docs)

## More CrawlerData examples

| Repo | What it does |
| --- | --- |
| [google-shopping-scraper](https://github.com/CrawlerData/google-shopping-scraper) | Search Google Shopping, export products to CSV/JSON (Python + Node.js) |
| [google-shopping-sellers-scraper](https://github.com/CrawlerData/google-shopping-sellers-scraper) | Every seller and price for one product, as a comparison table |
| [google-shopping-price-tracker](https://github.com/CrawlerData/google-shopping-price-tracker) | Scheduled price history in SQLite, CSV export and an HTML chart |
| [competitor-price-monitoring](https://github.com/CrawlerData/competitor-price-monitoring) | Your catalog vs Google Shopping sellers, with undercut alerts |
| [map-violation-monitor](https://github.com/CrawlerData/map-violation-monitor) | Flag sellers below MAP with timestamped evidence |
| [google-search-scraper](https://github.com/CrawlerData/google-search-scraper) | Google SERP to JSON/CSV: organic, ads, People Also Ask, AI Overview (Python + Node.js) |
| [google-rank-tracker](https://github.com/CrawlerData/google-rank-tracker) | Daily keyword positions by country and device, with a change report |
| [google-local-business-leads](https://github.com/CrawlerData/google-local-business-leads) | Google Local results to a lead list CSV |
| [google-news-scraper](https://github.com/CrawlerData/google-news-scraper) | Brand and keyword news monitoring to CSV and JSON Feed |
| [google-search-mcp-server](https://github.com/CrawlerData/google-search-mcp-server) | Connect Claude, Cursor or n8n to the CrawlerData MCP server |
| [crawlerdata-examples](https://github.com/CrawlerData/crawlerdata-examples) | Python, Node.js and curl snippets for every endpoint |

## License

MIT. See [LICENSE](LICENSE). Google and Google Shopping are trademarks of Google LLC; this project is not affiliated with Google.
