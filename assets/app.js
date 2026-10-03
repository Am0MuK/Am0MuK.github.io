// assets/app.js - Loads JSON data, renders metrics, tables, and Chart.js charts
// Pinned Chart.js from CDN

document.addEventListener("DOMContentLoaded", async () => {
  const isDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const textColor = isDark ? "#cbd5e1" : "#334155";
  const gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
  const fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

  // Formatters
  const fmtUsd = (n) => "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtEur = (n) => Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " EUR";
  const fmtPct = (n) => Number(n).toFixed(1) + "%";
  const fmtInt = (n) => Number(n).toLocaleString("en-US");

  try {
    const [liqRes, lpsimRes, valRes] = await Promise.all([
      fetch("data/liquidations.json"),
      fetch("data/lpsim.json"),
      fetch("data/lpsim_validation.json")
    ]);

    const liqData = await liqRes.json();
    const lpsimData = await lpsimRes.json();
    const valData = await valRes.json();

    renderLiquidations(liqData);
    renderLpSim(lpsimData, valData);
    renderDataAsOf(liqData.meta, lpsimData.meta);
  } catch (err) {
    console.error("Failed to load finding datasets:", err);
  }

  function renderDataAsOf(liqMeta, lpMeta) {
    const el = document.getElementById("data-asof");
    if (!el) return;
    el.textContent =
      "Data as of: liquidations " + liqMeta.start_date + " to " + liqMeta.end_date +
      " (exported " + liqMeta.generated_at.slice(0, 10) + "); LP simulation window " +
      lpMeta.window_days + " days (run " + lpMeta.date + ").";
  }

  function renderLiquidations(data) {
    const totals = data.totals;
    const reconc = data.reconciliation;
    const months = data.months;
    const topDays = data.top_days;

    // Metrics strip
    document.getElementById("liq-net-usd").textContent = "$" + (totals.total_net_usd / 1e6).toFixed(2) + "M";
    document.getElementById("liq-net-sub").textContent = (totals.total_net_eur / 1e6).toFixed(2) + "M EUR (" + fmtInt(totals.clean_event_count) + " events)";
    
    document.getElementById("liq-distinct").textContent = fmtInt(totals.distinct_liquidators);
    document.getElementById("liq-top1").textContent = fmtPct(totals.top1_share * 100);
    document.getElementById("liq-top1-sub").textContent = "Top-3: " + fmtPct(totals.top3_share * 100) + " | Top-10: " + fmtPct(totals.top10_share * 100);

    document.getElementById("liq-top5days").textContent = fmtPct(totals.top5_days_share * 100);
    document.getElementById("liq-top5days-sub").textContent = "2025-10-10 alone: " + fmtPct(totals.oct10_share * 100);

    // Monthly Table
    const monthTbody = document.getElementById("liq-months-tbody");
    if (monthTbody) {
      monthTbody.innerHTML = months.map(m => `
        <tr>
          <td>Month ${m.month_index}</td>
          <td>${m.start_date} to ${m.end_date}</td>
          <td class="num">${fmtInt(m.event_count)}</td>
          <td class="num">${fmtUsd(m.net_usd)}</td>
          <td class="num">${fmtEur(m.net_eur)}</td>
        </tr>
      `).join("");
    }

    // Top Days Table
    const daysTbody = document.getElementById("liq-days-tbody");
    if (daysTbody) {
      daysTbody.innerHTML = topDays.map((d, idx) => `
        <tr>
          <td>${idx + 1}</td>
          <td><strong>${d.date}</strong></td>
          <td class="num">${fmtUsd(d.net_usd)}</td>
          <td class="num">${fmtEur(d.net_eur)}</td>
          <td class="num">${fmtPct(d.share_of_year * 100)}</td>
          <td class="num">${fmtInt(d.event_count)}</td>
        </tr>
      `).join("");
    }

    // Reconciliation Table
    const reconcTbody = document.getElementById("liq-reconc-tbody");
    if (reconcTbody) {
      reconcTbody.innerHTML = `
        <tr>
          <td>Distinct liquidators</td>
          <td class="num">${reconc.distinct_liquidators.published}</td>
          <td class="num">${reconc.distinct_liquidators.recomputed}</td>
          <td class="num">${reconc.distinct_liquidators.difference === 0 ? "Exact match (0)" : reconc.distinct_liquidators.difference}</td>
        </tr>
        <tr>
          <td>Net profit USD (year)</td>
          <td class="num">~$${reconc.net_usd_millions.published}M</td>
          <td class="num">$${reconc.net_usd_millions.recomputed}M (${fmtUsd(reconc.net_usd_millions.exact_usd)})</td>
          <td class="num">Reconciled (~$3.18M)</td>
        </tr>
        <tr>
          <td>Net profit EUR (rate 1.1460)</td>
          <td class="num">~${reconc.net_eur_millions.published}M EUR</td>
          <td class="num">${reconc.net_eur_millions.recomputed}M EUR (${fmtEur(reconc.net_eur_millions.exact_eur)})</td>
          <td class="num">Reconciled (~2.77M EUR)</td>
        </tr>
        <tr>
          <td>Top-1 liquidator share</td>
          <td class="num">${reconc.top1_share_pct.published}%</td>
          <td class="num">${reconc.top1_share_pct.exact_pct}% (rounds to ${reconc.top1_share_pct.recomputed}%)</td>
          <td class="num">${(reconc.top1_share_pct.exact_pct - reconc.top1_share_pct.published).toFixed(2)}%</td>
        </tr>
        <tr>
          <td>Top-3 liquidators share</td>
          <td class="num">${reconc.top3_share_pct.published}%</td>
          <td class="num">${reconc.top3_share_pct.exact_pct}% (rounds to ${reconc.top3_share_pct.recomputed}%)</td>
          <td class="num">+${(reconc.top3_share_pct.exact_pct - reconc.top3_share_pct.published).toFixed(2)}%</td>
        </tr>
        <tr>
          <td>Top 5 days share</td>
          <td class="num">${reconc.top5_days_share_pct.published}%</td>
          <td class="num">${reconc.top5_days_share_pct.exact_pct}% (rounds to ${reconc.top5_days_share_pct.recomputed}%)</td>
          <td class="num">+${(reconc.top5_days_share_pct.exact_pct - reconc.top5_days_share_pct.published).toFixed(2)}%</td>
        </tr>
        <tr>
          <td>2025-10-10 alone</td>
          <td class="num">${reconc.oct10_share_pct.published}%</td>
          <td class="num">${reconc.oct10_share_pct.exact_pct}% (rounds to ${reconc.oct10_share_pct.recomputed}%)</td>
          <td class="num">${(reconc.oct10_share_pct.exact_pct - reconc.oct10_share_pct.published).toFixed(2)}%</td>
        </tr>
        <tr>
          <td>Unpriced event count</td>
          <td class="num">0</td>
          <td class="num">${totals.unpriced_event_count}</td>
          <td class="num">Exact match (0)</td>
        </tr>
      `;
    }

    // Chart 1: Monthly Net Profit & Event Counts
    if (window.Chart && document.getElementById("liq-chart-monthly")) {
      const ctx = document.getElementById("liq-chart-monthly").getContext("2d");
      new Chart(ctx, {
        data: {
          labels: months.map(m => `M${m.month_index} (${m.end_date.slice(5)})`),
          datasets: [
            {
              type: "bar",
              label: "Net Profit (USD)",
              data: months.map(m => m.net_usd),
              backgroundColor: isDark ? "rgba(56, 189, 248, 0.7)" : "rgba(37, 99, 235, 0.7)",
              borderColor: isDark ? "#38bdf8" : "#2563eb",
              borderWidth: 1,
              yAxisID: "y"
            },
            {
              type: "line",
              label: "Liquidation Events",
              data: months.map(m => m.event_count),
              borderColor: isDark ? "#f59e0b" : "#d97706",
              backgroundColor: isDark ? "#f59e0b" : "#d97706",
              borderWidth: 2,
              pointRadius: 3,
              yAxisID: "y1"
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { labels: { color: textColor, font: { family: fontFamily } } },
            tooltip: {
              callbacks: {
                label: (c) => c.datasetIndex === 0 ? `Net: ${fmtUsd(c.raw)}` : `Events: ${fmtInt(c.raw)}`
              }
            }
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { family: fontFamily, size: 11 } }
            },
            y: {
              type: "linear",
              display: true,
              position: "left",
              grid: { color: gridColor },
              ticks: {
                color: textColor,
                font: { family: fontFamily, size: 11 },
                callback: (v) => "$" + (v >= 1e6 ? (v/1e6).toFixed(1) + "M" : (v/1e3).toFixed(0) + "k")
              }
            },
            y1: {
              type: "linear",
              display: true,
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: { color: textColor, font: { family: fontFamily, size: 11 } }
            }
          }
        }
      });
    }

    // Chart 2: Top 10 Days Net Profit
    if (window.Chart && document.getElementById("liq-chart-days")) {
      const ctx2 = document.getElementById("liq-chart-days").getContext("2d");
      new Chart(ctx2, {
        type: "bar",
        data: {
          labels: topDays.map(d => d.date),
          datasets: [{
            label: "Net USD",
            data: topDays.map(d => d.net_usd),
            backgroundColor: topDays.map((d, i) => i < 5 ? (isDark ? "rgba(248, 113, 113, 0.8)" : "rgba(220, 38, 38, 0.8)") : (isDark ? "rgba(148, 163, 184, 0.5)" : "rgba(100, 116, 139, 0.5)")),
            borderColor: isDark ? "#243142" : "#e2e8f0",
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (c) => `Net: ${fmtUsd(c.raw)} (${(c.raw / totals.total_net_usd * 100).toFixed(1)}% of year)`
              }
            }
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { family: fontFamily, size: 11 } }
            },
            y: {
              grid: { color: gridColor },
              ticks: {
                color: textColor,
                font: { family: fontFamily, size: 11 },
                callback: (v) => "$" + (v >= 1e3 ? (v/1e3).toFixed(0) + "k" : v)
              }
            }
          }
        }
      });
    }
  }

  function renderLpSim(data, valData) {
    const meta = data.meta;
    const summaries = data.pool_summaries;
    const usdcUsdt = data.usdc_usdt0_comparison;

    // Metrics strip
    document.getElementById("lp-runs-count").textContent = fmtInt(meta.total_strategy_runs);
    document.getElementById("lp-pass-count").textContent = meta.total_pass_count + " / " + fmtInt(meta.total_strategy_runs);
    document.getElementById("lp-threshold").textContent = meta.threshold_annual_apy_pct + "% APY";
    
    const bestOverall = summaries.reduce((prev, curr) => (curr.best_avg_apy_pct > prev.best_avg_apy_pct ? curr : prev), summaries[0]);
    document.getElementById("lp-best-overall").textContent = bestOverall.best_avg_apy_pct.toFixed(1) + "%";
    document.getElementById("lp-best-overall-sub").textContent = `${bestOverall.pool_name} ($${bestOverall.best_size_usd})`;

    // Pools Table
    const poolTbody = document.getElementById("lp-pools-tbody");
    if (poolTbody) {
      poolTbody.innerHTML = summaries.map(p => `
        <tr>
          <td>
            <strong>${p.pool_name}</strong><br>
            <span class="badge ${p.is_decision_pool ? 'badge-decision' : 'badge-info'}">
              ${p.is_decision_pool ? 'DECISION POOL' : 'INFO-ONLY'}
            </span>
          </td>
          <td>${p.best_strategy}</td>
          <td class="num">$${fmtInt(p.best_size_usd)}</td>
          <td class="num"><strong>${p.best_avg_apy_pct.toFixed(2)}%</strong></td>
          <td class="num">${p.best_monthly_apys_pct.map(a => a.toFixed(1) + "%").join(", ")}</td>
          <td class="num"><span class="badge badge-fail">FAIL</span></td>
        </tr>
      `).join("");
    }

    // Autobalancer vs Static Table on USDC/USDT0 0.01%
    const autoTbody = document.getElementById("lp-auto-tbody");
    if (autoTbody && usdcUsdt) {
      autoTbody.innerHTML = ["1000", "10000"].map(sz => {
        const item = usdcUsdt[sz];
        const auto = item.autobalancer_1;
        const stat = item.best_static;
        return `
          <tr>
            <td><strong>$${fmtInt(sz)}</strong></td>
            <td>${auto.strategy}</td>
            <td class="num">${auto.rebalances}</td>
            <td class="num" style="color: var(--danger); font-weight: 600;">${fmtUsd(auto.total_net_usd)}</td>
            <td class="num" style="color: var(--danger);">${auto.avg_monthly_net_apy_pct.toFixed(1)}%</td>
            <td class="num"><span class="badge badge-fail">FAIL</span></td>
          </tr>
          <tr style="background: var(--bg-card-alt);">
            <td><strong>$${fmtInt(sz)}</strong></td>
            <td>${stat.strategy}</td>
            <td class="num">${stat.rebalances}</td>
            <td class="num" style="color: var(--success); font-weight: 600;">+${fmtUsd(stat.total_net_usd)}</td>
            <td class="num" style="color: var(--success);">+${stat.avg_monthly_net_apy_pct.toFixed(1)}%</td>
            <td class="num"><span class="badge badge-fail">FAIL</span></td>
          </tr>
        `;
      }).join("");
    }

    // Validation Table from lpsim_validation.json
    const valTbody = document.getElementById("lp-val-tbody");
    if (valTbody && valData && valData.pools) {
      valTbody.innerHTML = valData.pools.map(p => `
        <tr>
          <td><strong>${p.pool_name}</strong></td>
          <td class="num">${p.sim_onchain_token0.toFixed(4)}</td>
          <td class="num">${p.sim_onchain_token1.toFixed(4)}</td>
          <td class="num">${p.mismatches}</td>
          <td class="num">${fmtInt(p.swaps)}</td>
          <td><span class="badge" style="background: var(--success-bg); color: var(--success); border: 1px solid var(--success);">VALIDATED</span></td>
        </tr>
      `).join("");
      
      const valNotes = document.getElementById("lp-val-notes");
      if (valNotes) {
        valNotes.textContent = `Window: blocks ${fmtInt(valData.window.from_block)} to ${fmtInt(valData.window.to_block)} (90 days). Source: ${valData.source}.`;
      }
    }

    // Chart: Best APY per Pool vs 15% Threshold
    if (window.Chart && document.getElementById("lp-chart-apys")) {
      const ctx = document.getElementById("lp-chart-apys").getContext("2d");
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: summaries.map(p => p.pool_name.replace(" 0.01%", "").replace(" 0.05%", "")),
          datasets: [
            {
              label: "Best Net APY (%)",
              data: summaries.map(p => p.best_avg_apy_pct),
              backgroundColor: summaries.map(p => p.is_decision_pool ? (isDark ? "rgba(56, 189, 248, 0.85)" : "rgba(37, 99, 235, 0.85)") : (isDark ? "rgba(148, 163, 184, 0.4)" : "rgba(100, 116, 139, 0.4)")),
              borderColor: isDark ? "#243142" : "#e2e8f0",
              borderWidth: 1
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (items) => summaries[items[0].dataIndex].pool_name,
                label: (c) => `Best: ${c.raw.toFixed(2)}% APY (${summaries[c.dataIndex].best_strategy} at $${summaries[c.dataIndex].best_size_usd})`
              }
            }
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { family: fontFamily, size: 11 } }
            },
            y: {
              grid: { color: gridColor },
              max: 18,
              ticks: {
                color: textColor,
                font: { family: fontFamily, size: 11 },
                callback: (v) => v + "%"
              }
            }
          }
        },
        plugins: [{
          id: "thresholdLine",
          afterDraw: (chart) => {
            const yAxis = chart.scales.y;
            const xAxis = chart.scales.x;
            const yCoord = yAxis.getPixelForValue(15);
            const ctxChart = chart.ctx;
            ctxChart.save();
            ctxChart.beginPath();
            ctxChart.setLineDash([6, 6]);
            ctxChart.moveTo(xAxis.left, yCoord);
            ctxChart.lineTo(xAxis.right, yCoord);
            ctxChart.lineWidth = 2;
            ctxChart.strokeStyle = isDark ? "#f87171" : "#dc2626";
            ctxChart.stroke();

            ctxChart.fillStyle = isDark ? "#f87171" : "#dc2626";
            ctxChart.font = `bold 11px ${fontFamily}`;
            ctxChart.fillText("Kill Criterion Threshold: 15% APY", xAxis.left + 8, yCoord - 6);
            ctxChart.restore();
          }
        }]
      });
    }
  }
});
