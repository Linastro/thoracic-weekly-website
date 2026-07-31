"""回填 N 天的胸外文献。"""

from __future__ import annotations
import argparse
import asyncio
import logging
from datetime import date, timedelta

from .daily import run_daily

log = logging.getLogger(__name__)


def _daterange(start: date, end: date) -> list[date]:
    """[start, end] 闭区间所有日期。"""
    if end < start:
        raise ValueError(f"end ({end}) < start ({start})")
    out: list[date] = []
    d = start
    while d <= end:
        out.append(d)
        d += timedelta(days=1)
    return out


async def _run_one(target: date, dry_run: bool) -> dict:
    try:
        return await run_daily(target, dry_run=dry_run)
    except Exception as e:
        log.exception(f"backfill failed for {target}: {e}")
        return {"target_date": target.isoformat(), "error": str(e)}


async def run_backfill(
    start: date,
    end: date,
    *,
    concurrency: int = 3,
    dry_run: bool = False,
) -> list[dict]:
    """并发跑 [start, end] 区间每日抓取。"""
    import asyncio
    days = _daterange(start, end)
    log.info(f"backfill {start}..{end} ({len(days)} days), concurrency={concurrency}, dry_run={dry_run}")

    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async def task(d: date) -> dict:
        async with sem:
            return await _run_one(d, dry_run)

    results = await asyncio.gather(*[task(d) for d in days])
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Backfill PubMed thoracic literature for a date range")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--concurrency", type=int, default=3, help="Max concurrent daily runs (default 3)")
    parser.add_argument("--dry-run", action="store_true", help="Skip DB writes and JSON snapshot")
    args = parser.parse_args()

    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date)

    results = asyncio.run(run_backfill(start, end, concurrency=args.concurrency, dry_run=args.dry_run))

    print("=" * 60)
    print(f"Backfill complete: {len(results)} days")
    for r in results:
        if "error" in r:
            print(f"  {r['target_date']}: ERROR {r['error']}")
        else:
            extras = f" supplemental={len(r.get('supplemental_pmids', []))}" if r.get("supplemental_pmids") else ""
            print(
                f"  {r['target_date']}: fetched={r['total_fetched']} "
                f"publish={r['to_publish']} exclude={r['to_exclude']}{extras}"
            )


if __name__ == "__main__":
    main()
