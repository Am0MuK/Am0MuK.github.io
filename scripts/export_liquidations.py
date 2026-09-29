#!/usr/bin/env python3
"""Export Aave V3 Arbitrum liquidation data for am0muk.github.io.

Reads /data/projects/mev-scout/data/scout365.db in read-only mode,
values events offline using mev-scout's valuation module,
computes metrics, validates against published figures, and writes data/liquidations.json.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import sys

# Ensure mev_scout from /data/projects/mev-scout/src is importable
MEV_SCOUT_SRC = Path("/data/projects/mev-scout/src")
if MEV_SCOUT_SRC.exists() and str(MEV_SCOUT_SRC) not in sys.path:
    sys.path.insert(0, str(MEV_SCOUT_SRC))

from mev_scout.chains import CHAINS
from mev_scout.report import _is_anomalous, calculate_concentration
from mev_scout.store import Store
from mev_scout.value import value_liquidation

DB_URI = "file:/data/projects/mev-scout/data/scout365.db?mode=ro"
CHAIN_ID = 42161
EURUSD_RATE = Decimal("1.1460")
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "liquidations.json"


class ReadOnlyStore(Store):
    """Store subclass opening SQLite strictly read-only with URI mode=ro."""

    def __init__(self, db_uri: str):
        self.conn = sqlite3.connect(db_uri, uri=True)


class OfflineRpc:
    """Mock RPC client that strictly forbids network requests."""

    def call(self, to: str, data: str, block: int | str):
        raise RuntimeError(f"Offline mode: network call attempted for {to} at block {block}")

    def batch_call(self, calls):
        raise RuntimeError(f"Offline mode: network batch call attempted for {len(calls)} calls")


def main() -> None:
    print("Exporting Aave V3 Arbitrum liquidations...")
    print(f"Reading from database: {DB_URI}")

    store = ReadOnlyStore(DB_URI)
    try:
        events = store.get_liquidations(CHAIN_ID)
        chain = CHAINS[CHAIN_ID]
        tx_counts = Counter(e.tx_hash for e in events)

        network_failures = 0
        valued = []
        for e in events:
            try:
                v = value_liquidation(
                    event=e,
                    tx_event_count=tx_counts[e.tx_hash],
                    pool=chain.pool,
                    wrapped_native=chain.wrapped_native,
                    rpc=OfflineRpc(),
                    store=store,
                )
                valued.append(v)
            except RuntimeError as err:
                network_failures += 1

        if network_failures > 0:
            print(f"ERROR: Valuation would need a network call for {network_failures} events.")
            print("Stopping valuation per spec; no fallback price applied.")
            sys.exit(1)

        unpriced_count = sum(1 for v in valued if v.unpriced)
        anomalies = [v for v in valued if not v.unpriced and _is_anomalous(v)]
        clean = [v for v in valued if not v.unpriced and not _is_anomalous(v)]

        total_net_usd = sum((v.net_usd for v in clean if v.net_usd is not None), Decimal("0"))
        total_net_eur = total_net_usd / EURUSD_RATE
        total_gross_usd = sum((v.gross_usd for v in clean if v.gross_usd is not None), Decimal("0"))
        total_gas_usd = sum((v.gas_usd for v in clean if v.gas_usd is not None), Decimal("0"))

        liquidators = {v.event.liquidator.lower() for v in clean}
        distinct_liquidators = len(liquidators)

        # Liquidator concentration
        liq_net = defaultdict(Decimal)
        for v in clean:
            if v.net_usd is not None:
                liq_net[v.event.liquidator.lower()] += v.net_usd

        pos_liq_net = {k: v for k, v in liq_net.items() if v > 0}
        total_pos_net = sum(pos_liq_net.values(), Decimal("0"))
        sorted_pos = sorted(pos_liq_net.values(), reverse=True)

        top1_share = (sorted_pos[0] / total_pos_net) if sorted_pos else Decimal("0")
        top3_share = (sum(sorted_pos[:3]) / total_pos_net) if sorted_pos else Decimal("0")
        top10_share = (sum(sorted_pos[:10]) / total_pos_net) if sorted_pos else Decimal("0")

        # Top days by net profit (UTC)
        day_net = defaultdict(Decimal)
        day_counts = defaultdict(int)
        for v in clean:
            if v.net_usd is not None:
                day_str = datetime.fromtimestamp(v.event.timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
                day_net[day_str] += v.net_usd
                day_counts[day_str] += 1

        sorted_days = sorted(day_net.items(), key=lambda x: x[1], reverse=True)
        top5_days_net = sum(d[1] for d in sorted_days[:5])
        top5_days_share = (top5_days_net / total_net_usd) if total_net_usd > 0 else Decimal("0")

        oct10_net = day_net.get("2025-10-10", Decimal("0"))
        oct10_share = (oct10_net / total_net_usd) if total_net_usd > 0 else Decimal("0")

        top_10_days_list = []
        for day_str, net_val in sorted_days[:10]:
            top_10_days_list.append({
                "date": day_str,
                "net_usd": float(round(net_val, 2)),
                "net_eur": float(round(net_val / EURUSD_RATE, 2)),
                "share_of_year": float(round(net_val / total_net_usd, 4)),
                "event_count": day_counts[day_str],
            })

        # 12 months breakdown (chronological, oldest to newest)
        # Covering the full 365 days cleanly: Month 1 covers min_ts to max_ts - 11*30 days,
        # months 2 through 12 cover successive 30-day windows up to max_ts.
        max_ts = max(v.event.timestamp for v in clean)
        min_ts = min(v.event.timestamp for v in clean)

        months_list = []
        for m_rev in range(11, -1, -1):
            m_end = max_ts - (m_rev * 30 * 86400)
            if m_rev == 11:
                m_start = min_ts - 1
            else:
                m_start = max_ts - ((m_rev + 1) * 30 * 86400)

            m_items = [v for v in clean if m_start < v.event.timestamp <= m_end]
            m_net_usd = sum((v.net_usd for v in m_items), Decimal("0"))
            m_net_eur = m_net_usd / EURUSD_RATE
            m_gross_usd = sum((v.gross_usd for v in m_items), Decimal("0"))
            m_gas_usd = sum((v.gas_usd for v in m_items), Decimal("0"))

            d_start = datetime.fromtimestamp(m_start + (1 if m_rev == 11 else 0), tz=timezone.utc).strftime("%Y-%m-%d")
            d_end = datetime.fromtimestamp(m_end, tz=timezone.utc).strftime("%Y-%m-%d")
            month_idx = 12 - m_rev

            months_list.append({
                "month_index": month_idx,
                "start_date": d_start,
                "end_date": d_end,
                "event_count": len(m_items),
                "net_usd": float(round(m_net_usd, 2)),
                "net_eur": float(round(m_net_eur, 2)),
                "gross_usd": float(round(m_gross_usd, 2)),
                "gas_usd": float(round(m_gas_usd, 2)),
            })

        # Summary data payload
        export_data = {
            "meta": {
                "chain_id": CHAIN_ID,
                "chain_name": "Arbitrum One",
                "protocol": "Aave V3",
                "window_days": 365,
                "start_date": datetime.fromtimestamp(min_ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "end_date": datetime.fromtimestamp(max_ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "eurusd_rate": float(EURUSD_RATE),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "reconciliation": {
                "distinct_liquidators": {
                    "published": 276,
                    "recomputed": distinct_liquidators,
                    "difference": distinct_liquidators - 276,
                },
                "net_usd_millions": {
                    "published": 3.18,
                    "recomputed": float(round(total_net_usd / Decimal("1000000"), 2)),
                    "exact_usd": float(round(total_net_usd, 2)),
                },
                "net_eur_millions": {
                    "published": 2.77,
                    "recomputed": float(round(total_net_eur / Decimal("1000000"), 2)),
                    "exact_eur": float(round(total_net_eur, 2)),
                },
                "top1_share_pct": {
                    "published": 26.9,
                    "recomputed": float(round(top1_share * 100, 1)),
                    "exact_pct": float(round(top1_share * 100, 2)),
                },
                "top3_share_pct": {
                    "published": 45.9,
                    "recomputed": float(round(top3_share * 100, 1)),
                    "exact_pct": float(round(top3_share * 100, 2)),
                },
                "top5_days_share_pct": {
                    "published": 66.0,
                    "recomputed": float(round(top5_days_share * 100, 1)),
                    "exact_pct": float(round(top5_days_share * 100, 2)),
                },
                "oct10_share_pct": {
                    "published": 29.0,
                    "recomputed": float(round(oct10_share * 100, 1)),
                    "exact_pct": float(round(oct10_share * 100, 2)),
                },
            },
            "totals": {
                "total_events_in_db": len(events),
                "unpriced_event_count": unpriced_count,
                "anomalous_event_count": len(anomalies),
                "clean_event_count": len(clean),
                "distinct_liquidators": distinct_liquidators,
                "total_gross_usd": float(round(total_gross_usd, 2)),
                "total_gas_usd": float(round(total_gas_usd, 2)),
                "total_net_usd": float(round(total_net_usd, 2)),
                "total_net_eur": float(round(total_net_eur, 2)),
                "top1_share": float(round(top1_share, 4)),
                "top3_share": float(round(top3_share, 4)),
                "top10_share": float(round(top10_share, 4)),
                "top5_days_share": float(round(top5_days_share, 4)),
                "oct10_share": float(round(oct10_share, 4)),
            },
            "months": months_list,
            "top_days": top_10_days_list,
        }

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

        print(f"\nSuccessfully wrote {OUTPUT_FILE}")

        # Print reconciliation lines strictly per spec
        print("\n" + "=" * 70)
        print("RECONCILIATION TABLE: Published vs Recomputed (Section A)")
        print("=" * 70)
        print(f"Liquidators: published 276 | recomputed {distinct_liquidators} | diff: {distinct_liquidators - 276}")
        print(f"Net profit USD: published ~$3.18M | recomputed ${total_net_usd:,.2f} (~${total_net_usd/1000000:.2f}M)")
        print(f"Net profit EUR: published ~2.77M EUR | recomputed {total_net_eur:,.2f} EUR (~{total_net_eur/1000000:.2f}M EUR)")
        print(f"Top-1 share: published 26.9% | recomputed {top1_share*100:.2f}% (rounds to {round(top1_share*100, 1)}%) | diff: {top1_share*100 - Decimal('26.9'):+.2f}%")
        print(f"Top-3 share: published 45.9% | recomputed {top3_share*100:.2f}% (rounds to {round(top3_share*100, 1)}%) | diff: {top3_share*100 - Decimal('45.9'):+.2f}%")
        print(f"Top 5 days share: published 66% | recomputed {top5_days_share*100:.2f}% (rounds to {round(top5_days_share*100, 0):.0f}%) | diff: {top5_days_share*100 - Decimal('66.0'):+.2f}%")
        print(f"2025-10-10 alone: published 29% | recomputed {oct10_share*100:.2f}% (rounds to {round(oct10_share*100, 0):.0f}%) | diff: {oct10_share*100 - Decimal('29.0'):+.2f}%")
        print(f"Unpriced event count: {unpriced_count}")
        print(f"Anomalous events excluded: {len(anomalies)}")
        print("=" * 70)

    finally:
        store.close()


if __name__ == "__main__":
    main()
