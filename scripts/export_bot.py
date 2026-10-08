#!/usr/bin/env python3
"""Export Telegram alert bot dataset for am0muk.github.io.

Reads /data/projects/healthfactor_watch_bot in read-only mode,
computes market statistics from hfwb/markets.json,
collects automated test counts, HEAD commit,
and formats two sample alerts (health factor & stablecoin depeg).
Outputs data/bot.json.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

BOT_REPO_DIR = Path("/data/projects/healthfactor_watch_bot")
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "bot.json"


def main() -> None:
    repo_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BOT_REPO_DIR.resolve()

    if not repo_dir.exists():
        raise FileNotFoundError(f"Bot repository directory not found: {repo_dir}")

    # 1. Market statistics from hfwb/markets.json
    markets_file = repo_dir / "hfwb" / "markets.json"
    if not markets_file.exists():
        raise FileNotFoundError(f"Markets file not found: {markets_file}")

    with open(markets_file, "r", encoding="utf-8") as f:
        markets_data = json.load(f)

    markets = markets_data.get("markets", [])
    markets_total = len(markets)
    v3_chains = len(set(m["chain"] for m in markets if m.get("protocol") == "aave_v3"))
    v4_chains = len(set(m["chain"] for m in markets if m.get("protocol") == "aave_v4"))
    v4_spokes = len([m for m in markets if m.get("protocol") == "aave_v4"])
    best_effort = len([m for m in markets if m.get("best_effort") is True])

    # 2. Test collection count via pytest
    pytest_bin = repo_dir / ".venv" / "bin" / "pytest"
    if not pytest_bin.exists():
        raise RuntimeError(f"Pytest binary not found at: {pytest_bin}")

    pytest_cmd = [str(pytest_bin), "--collect-only", "-q"]
    pytest_proc = subprocess.run(
        pytest_cmd,
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    if pytest_proc.returncode != 0:
        raise RuntimeError(
            f"pytest --collect-only failed with exit code {pytest_proc.returncode}:\n"
            f"{pytest_proc.stderr}\n{pytest_proc.stdout}"
        )

    match = re.search(r"(\d+)\s+tests?\s+collected", pytest_proc.stdout)
    if not match:
        raise RuntimeError(
            f"Could not find 'N tests collected' in pytest output:\n{pytest_proc.stdout}"
        )
    tests_collected = int(match.group(1))

    # 3. Git commit short hash
    git_proc = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    repo_commit = git_proc.stdout.strip()

    # 4. Sample alerts generated using bot's own formatters
    python_bin = repo_dir / ".venv" / "bin" / "python"
    if not python_bin.exists():
        raise RuntimeError(f"Python binary not found at: {python_bin}")

    snippet = """
import json
from decimal import Decimal
from hfwb.markets import load_markets
from hfwb.format import format_alert, format_depeg_alert
from hfwb.positions import AssetPosition, PositionBreakdown
from hfwb.pricedrop import format_liquidation_lines

markets = load_markets()
base_v3 = next(m for m in markets if m.chain == "Base" and m.protocol == "aave_v3")
fake_addr = "0x" + "ab" * 20

# Sample position: 2 WETH at $2,500 (LT 0.83) + 0.05 cbBTC at $100,000 (LT 0.78), 7,000 USDC debt.
# Weighted collateral 4,150 + 3,900 = 8,050, so HF = 8,050 / 7,000 = 1.15.
sample = PositionBreakdown(
    assets=(
        AssetPosition("WETH", "0x" + "11" * 20, 18, Decimal(2), Decimal(0), Decimal(2500), Decimal("0.83"), True),
        AssetPosition("cbBTC", "0x" + "33" * 20, 8, Decimal("0.05"), Decimal(0), Decimal(100000), Decimal("0.78"), True),
        AssetPosition("USDC", "0x" + "22" * 20, 6, Decimal(0), Decimal(7000), Decimal(1), Decimal("0.78"), False),
    ),
    emode_category=0,
    collateral_usd=Decimal(10000),
    weighted_collateral_usd=Decimal(8050),
    debt_usd=Decimal(7000),
    hf=Decimal("1.15"),
)

hf_html = format_alert(
    alert_type="L2",
    address=fake_addr,
    hf=Decimal("1.15"),
    collateral_usd=Decimal(10000),
    debt_usd=Decimal(7000),
    market=base_v3,
    details=format_liquidation_lines(sample),
)

depeg_html = format_depeg_alert(
    alert_type="D2",
    symbol="USDC",
    price=Decimal("0.9871"),
    readings_age_s=380,
    oracle_price=Decimal("0.9998"),
)

alerts = [
    {"title": "Health factor alert", "html": hf_html},
    {"title": "Stablecoin price alert", "html": depeg_html},
]
print(json.dumps(alerts))
"""
    alerts_proc = subprocess.run(
        [str(python_bin), "-c", snippet],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    sample_alerts = json.loads(alerts_proc.stdout)
    # the examples use a made-up address: show it as plain text instead of linking to a real profile page
    for alert in sample_alerts:
        alert["html"] = re.sub(r'<a href="[^"]*">(.*?)</a>', r'\1', alert["html"])

    # 5. External links
    links = {
        "telegram": "https://t.me/healthfactor_watch_bot",
        "repo": "https://github.com/Am0MuK/healthfactor_watch_bot",
    }

    # 6. Generated at timestamp (UTC ISO)
    generated_at = datetime.now(timezone.utc).isoformat()

    bot_payload = {
        "markets_total": markets_total,
        "v3_chains": v3_chains,
        "v4_chains": v4_chains,
        "v4_spokes": v4_spokes,
        "best_effort": best_effort,
        "tests_collected": tests_collected,
        "repo_commit": repo_commit,
        "links": links,
        "sample_alerts": sample_alerts,
        "generated_at": generated_at,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(bot_payload, f, indent=2)

    summary = (
        f"bot.json: {markets_total} markets (V3: {v3_chains} chains, V4: {v4_chains} chains / {v4_spokes} spokes, "
        f"best effort: {best_effort}), {tests_collected} tests collected, commit {repo_commit}"
    )
    print(summary)
    print(f"Successfully wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
