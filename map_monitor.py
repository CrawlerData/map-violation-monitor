#!/usr/bin/env python3
"""MAP violation monitor for Google Shopping.

Checks every Google Shopping seller of your products against your minimum advertised price (MAP),
saves the exact API response as timestamped evidence (with a SHA-256 hash), appends violations to a
CSV and prints a report grouped by seller.

Uses the CrawlerData API (https://crawlerdata.com). Set CRAWLERDATA_API_KEY first.

    python map_monitor.py check                       # check map_prices.csv, append to violations.csv
    python map_monitor.py check --ignore "Sony,Best Buy" --skip-condition
    python map_monitor.py report                      # latest day's violations, grouped by seller
    python map_monitor.py report --day 2026-10-13

Not legal advice: what counts as a violation is defined by your MAP policy.
"""
import argparse
import csv
import hashlib
import json
import os
import pathlib
import sys
from collections import defaultdict

CONDITION_WORDS = ("used", "refurbished", "renewed", "open box", "open-box", "pre-owned", "preowned")
FIELDS = ["checked_at", "job_id", "product_id", "country", "label", "map_price", "merchant", "offer_title",
          "price", "shipping", "total_price", "currency", "availability", "below_map_by", "below_map_pct",
          "condition_flag", "evidence_file", "evidence_sha256"]


def value(m):
    return m["value"] if m else None


def split_words(s):
    return [w.strip().lower() for w in (s or "").replace(",", ";").split(";") if w.strip()]


def save_evidence(evidence_dir, response):
    """Store the full API response (job + result) as JSON and return (path, sha256)."""
    job = response["job"]
    folder = pathlib.Path(evidence_dir) / job["completedAt"][:10]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{job["params"]["product_id"]}_{job["params"]["country"]}_{job["id"]}.json'
    raw = json.dumps(response, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(raw)
    return path.as_posix(), hashlib.sha256(raw).hexdigest()


def find_violations(row, response, evidence_file, digest, ignore, skip_condition, compare):
    job, result = response["job"], response["result"]
    map_price = float(row["map_price"])
    include, exclude = split_words(row.get("include")), split_words(row.get("exclude"))
    found = []
    for s in result.get("sellers") or []:
        merchant = s.get("merchant") or ""
        title = (s.get("offer_title") or "").lower()
        if any(name in merchant.lower() for name in ignore):
            continue
        if include and not all(w in title for w in include):
            continue
        if any(w in title for w in exclude):
            continue
        condition = next((w for w in CONDITION_WORDS if w in title), "")
        if condition and skip_condition:
            continue
        price = value(s.get(compare))
        if price is None or price >= map_price:
            continue
        found.append({
            "checked_at": job["completedAt"],
            "job_id": job["id"],
            "product_id": row["product_id"],
            "country": row["country"],
            "label": row.get("label") or row["product_id"],
            "map_price": map_price,
            "merchant": merchant,
            "offer_title": s.get("offer_title"),
            "price": value(s.get("price")),
            "shipping": value(s.get("shipping")),
            "total_price": value(s.get("total_price")),
            "currency": (s.get("price") or {}).get("currency"),
            "availability": s.get("availability"),
            "below_map_by": round(map_price - price, 2),
            "below_map_pct": round(100 * (map_price - price) / map_price, 1),
            "condition_flag": condition,
            "evidence_file": evidence_file,
            "evidence_sha256": digest,
        })
    return found


def cmd_check(args):
    from crawlerdata_client import CrawlerData, CrawlerDataError

    try:
        client = CrawlerData()
    except CrawlerDataError as exc:
        sys.exit(str(exc))
    with open(args.input, newline="", encoding="utf-8") as f:
        products = [r for r in csv.DictReader(f) if (r.get("product_id") or "").strip()]
    ignore = split_words(args.ignore)
    new_file = not os.path.exists(args.output)
    total = 0
    with open(args.output, "a", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for row in products:
            row["country"] = (row.get("country") or "us").strip()
            label = row.get("label") or row["product_id"]
            try:
                response = client.live_response("google-shopping-product",
                                                {"product_id": row["product_id"], "country": row["country"]})
            except CrawlerDataError as exc:
                if exc.status in (401, 402):
                    sys.exit(str(exc))
                print(f"SKIPPED {label}: {exc}", file=sys.stderr)
                continue
            if response["result"].get("error"):
                print(f"SKIPPED {label}: {response['result']['error']}", file=sys.stderr)
                continue
            evidence_file, digest = save_evidence(args.evidence_dir, response)
            violations = find_violations(row, response, evidence_file, digest, ignore,
                                         args.skip_condition, args.compare)
            writer.writerows(violations)
            out.flush()
            total += len(violations)
            print(f"{label} ({row['country']}): {response['result'].get('sellers_count')} sellers, "
                  f"{len(violations)} below MAP {row['map_price']}  [evidence {evidence_file}]")
    print(f"\n{total} violation(s) appended to {args.output}. Credits used: {client.credits_used}")


def cmd_report(args):
    if not os.path.exists(args.output):
        sys.exit(f"{args.output} not found. Run: python map_monitor.py check")
    with open(args.output, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("No violations recorded.")
        return
    day = args.day or max(r["checked_at"][:10] for r in rows)
    today = [r for r in rows if r["checked_at"].startswith(day)]
    by_merchant = defaultdict(list)
    for r in today:
        by_merchant[r["merchant"]].append(r)
    print(f"MAP report for {day}: {len(today)} offer(s) below MAP from {len(by_merchant)} seller(s)\n")
    for merchant, offers in sorted(by_merchant.items(), key=lambda kv: -len(kv[1])):
        print(f"{merchant}: {len(offers)} offer(s)")
        for o in sorted(offers, key=lambda o: -float(o["below_map_by"])):
            flag = f" [{o['condition_flag']}]" if o.get("condition_flag") else ""
            print(f"  {o['label']} ({o['country']}): {o['price']} {o['currency']} vs MAP {o['map_price']} "
                  f"(-{o['below_map_by']}, -{o['below_map_pct']}%){flag}")
            print(f"    checked {o['checked_at']}, job {o['job_id']}, evidence {o['evidence_file']}")
    # repeat offenders: same merchant + product below MAP on more than one day
    days = defaultdict(set)
    for r in rows:
        days[(r["merchant"], r["label"], r["country"])].add(r["checked_at"][:10])
    repeat = {k: v for k, v in days.items() if len(v) > 1}
    if repeat:
        print("\nBelow MAP on more than one day:")
        for (merchant, label, country), d in sorted(repeat.items(), key=lambda kv: -len(kv[1])):
            print(f"  {merchant} / {label} ({country}): {len(d)} days, last {max(d)}")


def cmd_verify(args):
    """Re-hash every evidence file referenced in the CSV and report any that changed or went missing."""
    with open(args.output, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    seen, bad = {}, 0
    for r in rows:
        path = r["evidence_file"]
        if path in seen:
            continue
        p = pathlib.Path(path)
        ok = p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == r["evidence_sha256"]
        seen[path] = ok
        if not ok:
            bad += 1
            print(f"MISMATCH or missing: {path}")
    print(f"Checked {len(seen)} evidence file(s): {len(seen) - bad} OK, {bad} problem(s)")


def main():
    ap = argparse.ArgumentParser(description="Find Google Shopping sellers advertising below your MAP.")
    ap.add_argument("-o", "--output", default="violations.csv", help="violations CSV (default: violations.csv)")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="check every product and append violations")
    p.add_argument("-i", "--input", default="map_prices.csv", help="products and MAP (default: map_prices.csv)")
    p.add_argument("--evidence-dir", default="evidence", help="where API responses are saved (default: evidence)")
    p.add_argument("--ignore", default=os.environ.get("MAP_IGNORE_MERCHANTS", ""),
                   help="comma-separated merchant names to skip (you, or sellers with an approved promotion)")
    p.add_argument("--skip-condition", action="store_true",
                   help="skip offers whose title says used / refurbished / renewed / open box / pre-owned")
    p.add_argument("--compare", choices=["price", "total_price"], default="price",
                   help="compare MAP with the item price (default) or total incl. shipping")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("report", help="violations of the latest (or given) day, grouped by seller")
    p.add_argument("--day", help="YYYY-MM-DD (default: latest day in the CSV)")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("verify", help="check that evidence files still match their SHA-256 hashes")
    p.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
