#!/usr/bin/env python3
"""Export lp-sim strategy runs for am0muk.github.io.

Reads /data/projects/lp-sim/results/2026-09-29/*.json (1,464 strategy runs),
extracts best strategies per (pool, size), monthly APYs, pass counts,
and comparison between AUTOBALANCER_1 and best static strategy on USDC/USDT0.
Outputs data/lpsim.json.
"""

import glob
import json
from pathlib import Path
import sys

RESULTS_DIR = Path("/data/projects/lp-sim/results/2026-09-29")
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "lpsim.json"

DECISION_POOLS = {
    "USDC/USDT0 0.01%",
    "GHO/USDC 0.05%",
    "USDe/USDT0 0.05%",
}

THRESHOLD_APY_PCT = 15.0


def main() -> None:
    print("Exporting lp-sim simulation results...")
    pattern = str(RESULTS_DIR / "0x*.json")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"ERROR: No result files found matching {pattern}")
        sys.exit(1)

    print(f"Found {len(files)} result files in {RESULTS_DIR}")

    runs_by_pool_size = {}
    all_runs = []
    pools_meta = {}

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            runs = json.load(f)
            for r in runs:
                all_runs.append(r)
                pool_name = r["pool_name"]
                pool_addr = r["pool_address"]
                size_usd = float(r["size_usd"])
                pools_meta[pool_name] = {
                    "pool_name": pool_name,
                    "pool_address": pool_addr,
                    "is_decision_pool": (pool_name in DECISION_POOLS),
                }

                key = (pool_name, size_usd)
                if key not in runs_by_pool_size:
                    runs_by_pool_size[key] = []
                runs_by_pool_size[key].append(r)

    total_runs_count = len(all_runs)
    total_pass_count = sum(1 for r in all_runs if r["verdict"] == "PASS")
    print(f"Total strategy runs evaluated: {total_runs_count}")
    print(f"Total PASS count across all runs: {total_pass_count}")

    # Process per (pool, size)
    pool_size_results = []
    pool_summaries = {}

    for (p_name, size_usd), runs in sorted(runs_by_pool_size.items(), key=lambda x: (x[0][0], x[0][1])):
        pass_count = sum(1 for r in runs if r["verdict"] == "PASS")

        # Find best strategy by average monthly net APY
        def avg_monthly_net_apy(run_item):
            months = run_item["months"]
            if not months:
                return -999.0
            return sum(m["net_apy"] for m in months) / len(months)

        sorted_runs = sorted(runs, key=avg_monthly_net_apy, reverse=True)
        best_run = sorted_runs[0]
        best_avg_apy = avg_monthly_net_apy(best_run)
        best_monthly_apys = [round(m["net_apy"] * 100, 2) for m in best_run["months"]]

        entry = {
            "pool_name": p_name,
            "pool_address": pools_meta[p_name]["pool_address"],
            "is_decision_pool": (p_name in DECISION_POOLS),
            "size_usd": size_usd,
            "total_strategies": len(runs),
            "pass_count": pass_count,
            "best_strategy": {
                "name": best_run["strategy"],
                "avg_monthly_net_apy_pct": round(best_avg_apy * 100, 2),
                "monthly_net_apys_pct": best_monthly_apys,
                "total_net_usd": round(best_run["total_net_usd"], 2),
                "total_fees_usd": round(best_run["total_fees_usd"], 2),
                "total_gas_usd": round(best_run["total_gas_usd"], 2),
                "total_swap_costs_usd": round(best_run["total_swap_costs_usd"], 2),
                "total_rebalances": best_run["total_rebalances"],
                "verdict": best_run["verdict"],
            },
        }
        pool_size_results.append(entry)

        # Track best overall for pool summary
        if p_name not in pool_summaries or best_avg_apy > pool_summaries[p_name]["best_avg_apy"]:
            pool_summaries[p_name] = {
                "pool_name": p_name,
                "pool_address": pools_meta[p_name]["pool_address"],
                "is_decision_pool": (p_name in DECISION_POOLS),
                "best_strategy": best_run["strategy"],
                "best_size_usd": size_usd,
                "best_avg_apy": best_avg_apy,
                "best_avg_apy_pct": round(best_avg_apy * 100, 2),
                "best_monthly_apys_pct": best_monthly_apys,
            }

    # Autobalancer vs Static comparison on USDC/USDT0 0.01%
    # For sizes 1000 and 10000
    usdc_usdt_comparisons = {}
    for size in (1000.0, 10000.0):
        runs = runs_by_pool_size.get(("USDC/USDT0 0.01%", size), [])
        autobalancer = next((r for r in runs if r["strategy"] == "AUTOBALANCER_1"), None)
        static_runs = [r for r in runs if "STATIC" in r["strategy"]]
        best_static = max(
            static_runs,
            key=lambda r: sum(m["net_apy"] for m in r["months"]) / len(r["months"]),
        ) if static_runs else None

        if autobalancer and best_static:
            auto_avg_apy = sum(m["net_apy"] for m in autobalancer["months"]) / len(autobalancer["months"])
            static_avg_apy = sum(m["net_apy"] for m in best_static["months"]) / len(best_static["months"])

            usdc_usdt_comparisons[str(int(size))] = {
                "size_usd": size,
                "autobalancer_1": {
                    "strategy": autobalancer["strategy"],
                    "rebalances": autobalancer["total_rebalances"],
                    "total_net_usd": round(autobalancer["total_net_usd"], 2),
                    "total_fees_usd": round(autobalancer["total_fees_usd"], 2),
                    "total_gas_usd": round(autobalancer["total_gas_usd"], 2),
                    "total_swap_costs_usd": round(autobalancer["total_swap_costs_usd"], 2),
                    "avg_monthly_net_apy_pct": round(auto_avg_apy * 100, 2),
                    "monthly_net_apys_pct": [round(m["net_apy"] * 100, 2) for m in autobalancer["months"]],
                    "verdict": autobalancer["verdict"],
                },
                "best_static": {
                    "strategy": best_static["strategy"],
                    "rebalances": best_static["total_rebalances"],
                    "total_net_usd": round(best_static["total_net_usd"], 2),
                    "total_fees_usd": round(best_static["total_fees_usd"], 2),
                    "total_gas_usd": round(best_static["total_gas_usd"], 2),
                    "total_swap_costs_usd": round(best_static["total_swap_costs_usd"], 2),
                    "avg_monthly_net_apy_pct": round(static_avg_apy * 100, 2),
                    "monthly_net_apys_pct": [round(m["net_apy"] * 100, 2) for m in best_static["months"]],
                    "verdict": best_static["verdict"],
                },
            }

    # Format pool summaries list sorted by decision pools first, then highest APY
    summary_list = sorted(
        pool_summaries.values(),
        key=lambda x: (not x["is_decision_pool"], -x["best_avg_apy"]),
    )

    export_payload = {
        "meta": {
            "source_dir": str(RESULTS_DIR),
            "date": "2026-09-29",
            "threshold_annual_apy_pct": THRESHOLD_APY_PCT,
            "window_days": 90,
            "window_blocks": {
                "from_block": 478933741,
                "to_block": 509690000,
            },
            "total_pools": len(pool_summaries),
            "total_strategy_runs": total_runs_count,
            "total_pass_count": total_pass_count,
            "sizes_usd": [50, 1000, 10000],
            "decision_pools": list(DECISION_POOLS),
        },
        "pool_summaries": summary_list,
        "pool_size_results": pool_size_results,
        "usdc_usdt0_comparison": usdc_usdt_comparisons,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2)

    print(f"\nSuccessfully wrote {OUTPUT_FILE}")

    print("\n" + "=" * 70)
    print("SUMMARY: Best Strategy per Pool vs 15% Threshold")
    print("=" * 70)
    for p in summary_list:
        tag = "[DECISION]" if p["is_decision_pool"] else "[INFO-ONLY]"
        print(
            f"{tag:11} {p['pool_name']:20} Best: {p['best_strategy']:24} "
            f"(${p['best_size_usd']:<5.0f}) -> {p['best_avg_apy_pct']:5.2f}% APY (pass: 0)"
        )
    print("=" * 70)
    print("USDC/USDT0 0.01% Autobalancer vs Static:")
    for sz_str, comp in usdc_usdt_comparisons.items():
        auto = comp["autobalancer_1"]
        stat = comp["best_static"]
        print(f"  Size ${sz_str}:")
        print(f"    AUTOBALANCER_1 : {auto['rebalances']} rebalances | net USD: ${auto['total_net_usd']} | APY: {auto['avg_monthly_net_apy_pct']}%")
        print(f"    Best Static    : {stat['rebalances']} rebalances | net USD: ${stat['total_net_usd']} | APY: {stat['avg_monthly_net_apy_pct']}% ({stat['strategy']})")
    print("=" * 70)


if __name__ == "__main__":
    main()
