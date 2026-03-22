"""
CSV → HTML Rapor Üretici
Her oturum CSV dosyasından güzel, yazdırılabilir HTML raporu üretir.
"""

import csv
import os
import webbrowser
from datetime import datetime


def generate_report(csv_path: str) -> str:
    """CSV dosyasından HTML rapor üretir. Rapor yolunu döner."""

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        raise ValueError("CSV dosyası boş.")

    # ── Özet bilgiler ──────────────────────────────────────────────────────────
    animal_id     = rows[0].get("animal_id", "—")
    total_trials  = len(rows)
    timestamp_raw = rows[0].get("timestamp", "")
    try:
        session_date = datetime.fromisoformat(timestamp_raw).strftime("%d.%m.%Y %H:%M")
    except Exception:
        session_date = timestamp_raw[:16] if timestamp_raw else "—"

    last = rows[-1]
    hit_rate  = float(last.get("hit_rate",  0) or 0)
    cr_rate   = float(last.get("cr_rate",   0) or 0)
    d_prime   = float(last.get("d_prime",   0) or 0)
    rewarded  = int(last.get("rewarded",   0) or 0)
    punished  = int(last.get("punished",   0) or 0)
    omission  = int(last.get("omission",   0) or 0)
    cr_count  = int(last.get("correct_rejection", 0) or 0)

    total_licks     = sum(int(r.get("lick_count", 0) or 0) for r in rows)
    total_iti       = sum(int(r.get("iti_presses", 0) or 0) for r in rows)
    sync_misses     = sum(1 for r in rows if r.get("sound_confirmed", "1") == "0")

    # Kritere ulaşılan ilk trial
    criterion_trial = next(
        (int(r["trial"]) for r in rows if r.get("criterion_reached", "0") == "1"),
        None
    )

    # ── Renk haritası ─────────────────────────────────────────────────────────
    result_colors = {
        "rewarded":          "#c8e6c9",
        "punished":          "#ffe0b2",
        "omission":          "#ffcdd2",
        "correct_rejection": "#bbdefb",
    }
    result_labels = {
        "rewarded":          "Ödül",
        "punished":          "Ceza",
        "omission":          "Omission",
        "correct_rejection": "Correct Rejection",
    }

    # ── d' rengi ──────────────────────────────────────────────────────────────
    def dprime_color(v):
        if v >= 2.0: return "#2e7d32"
        if v >= 1.0: return "#f57f17"
        return "#c62828"

    # ── Trial satırları ───────────────────────────────────────────────────────
    trial_rows_html = ""
    for r in rows:
        result  = r.get("result", "")
        bg      = result_colors.get(result, "#ffffff")
        label   = result_labels.get(result, result)
        rt_ds   = f"{float(r['rt_from_ds_s']):.3f}" if r.get("rt_from_ds_s") else "—"
        rt_lev  = f"{float(r['rt_from_lever_s']):.3f}" if r.get("rt_from_lever_s") else "—"
        licks   = r.get("lick_count", "0") or "0"
        iti_p   = r.get("iti_presses", "0") or "0"
        hr      = f"{float(r['hit_rate'])*100:.1f}%" if r.get("hit_rate") else "—"
        cr      = f"{float(r['cr_rate'])*100:.1f}%" if r.get("cr_rate") else "—"
        dp_val  = float(r.get("d_prime", 0) or 0)
        dp_str  = f"{dp_val:.2f}" if r.get("d_prime") else "—"
        dp_col  = dprime_color(dp_val) if r.get("d_prime") else "#333"
        crit    = "✓" if r.get("criterion_reached", "0") == "1" else ""
        crit_col = "color:#2e7d32;font-weight:bold" if crit else ""
        sync    = "" if r.get("sound_confirmed", "1") == "1" else "⚠"
        sync_col = "color:#c62828;font-weight:bold" if sync else ""
        iti_col  = "color:#e65100;font-weight:bold" if int(iti_p) > 0 else ""

        trial_rows_html += f"""
        <tr style="background:{bg}">
            <td>{r.get('trial','')}</td>
            <td>{r.get('ds_type','')}</td>
            <td><b>{label}</b></td>
            <td>{rt_ds}</td>
            <td>{rt_lev}</td>
            <td>{licks}</td>
            <td style="{iti_col}">{iti_p}</td>
            <td>{hr}</td>
            <td>{cr}</td>
            <td style="color:{dp_col};font-weight:bold">{dp_str}</td>
            <td style="{crit_col}">{crit}</td>
            <td style="{sync_col}">{sync}</td>
        </tr>"""

    # ── Criterion badge ───────────────────────────────────────────────────────
    if criterion_trial:
        crit_badge = f'<span style="background:#2e7d32;color:white;padding:4px 12px;border-radius:4px;font-size:14px">✓ Trial {criterion_trial}\'de kritere ulaşıldı</span>'
    else:
        crit_badge = '<span style="background:#c62828;color:white;padding:4px 12px;border-radius:4px;font-size:14px">✗ Kriter bu oturumda sağlanamadı</span>'

    # ── HTML ──────────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Oturum Raporu — {animal_id}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 32px; color: #212121; background: #fafafa; }}
  h1   {{ color: #1565c0; margin-bottom: 4px; }}
  h2   {{ color: #1565c0; margin-top: 32px; border-bottom: 2px solid #1565c0; padding-bottom: 4px; }}
  .meta {{ color: #555; font-size: 14px; margin-bottom: 24px; }}
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin: 16px 0 24px;
  }}
  .card {{
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}
  .card .value {{ font-size: 28px; font-weight: bold; color: #1565c0; }}
  .card .label {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .outcome-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 16px 0;
  }}
  .outcome-card {{ border-radius: 8px; padding: 12px; text-align: center; }}
  .outcome-card .num {{ font-size: 24px; font-weight: bold; }}
  .outcome-card .lbl {{ font-size: 11px; margin-top: 2px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    background: white;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    border-radius: 8px;
    overflow: hidden;
  }}
  th {{
    background: #1565c0;
    color: white;
    padding: 10px 8px;
    text-align: center;
    font-size: 12px;
  }}
  td {{ padding: 7px 8px; text-align: center; border-bottom: 1px solid #e0e0e0; }}
  tr:last-child td {{ border-bottom: none; }}
  .legend {{
    display: flex; gap: 16px; flex-wrap: wrap;
    margin: 12px 0; font-size: 12px;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-dot {{ width: 14px; height: 14px; border-radius: 3px; }}
  .warn {{ background: #fff3e0; border: 1px solid #ff9800; border-radius: 6px; padding: 10px 16px; margin: 12px 0; font-size: 13px; color: #e65100; }}
  @media print {{ body {{ margin: 16px; }} }}
</style>
</head>
<body>

<h1>Oturum Raporu</h1>
<div class="meta">
  <b>Hayvan ID:</b> {animal_id} &nbsp;|&nbsp;
  <b>Tarih:</b> {session_date} &nbsp;|&nbsp;
  <b>Toplam Trial:</b> {total_trials} &nbsp;|&nbsp;
  <b>CSV:</b> {os.path.basename(csv_path)}
</div>

{crit_badge}

<h2>Diskriminasyon Metrikleri</h2>
<div class="summary-grid">
  <div class="card">
    <div class="value">{hit_rate*100:.1f}%</div>
    <div class="label">Hit Rate (DS+)</div>
  </div>
  <div class="card">
    <div class="value">{cr_rate*100:.1f}%</div>
    <div class="label">Correct Rejection Rate (DS−)</div>
  </div>
  <div class="card">
    <div class="value" style="color:{dprime_color(d_prime)}">{d_prime:.2f}</div>
    <div class="label">d' (d-prime)</div>
  </div>
  <div class="card">
    <div class="value">{total_licks}</div>
    <div class="label">Toplam Lick</div>
  </div>
</div>

<h2>Trial Sonuçları</h2>
<div class="outcome-grid">
  <div class="outcome-card" style="background:#c8e6c9">
    <div class="num">{rewarded}</div>
    <div class="lbl">Ödül (Rewarded)</div>
  </div>
  <div class="outcome-card" style="background:#ffe0b2">
    <div class="num">{punished}</div>
    <div class="lbl">Ceza (Punished)</div>
  </div>
  <div class="outcome-card" style="background:#ffcdd2">
    <div class="num">{omission}</div>
    <div class="lbl">Omission (DS+↓)</div>
  </div>
  <div class="outcome-card" style="background:#bbdefb">
    <div class="num">{cr_count}</div>
    <div class="lbl">Correct Rejection (DS−↓)</div>
  </div>
</div>

{"" if total_iti == 0 else f'<div class="warn">⚠ Bu oturumda toplam <b>{total_iti}</b> ITI lever press kaydedildi (dürtüsellik).</div>'}
{"" if sync_misses == 0 else f'<div class="warn">⚠ <b>{sync_misses}</b> trialda Avisoft ses onayı alınamadı (sound_confirmed=0). Bu trialleri analizden çıkarmayı düşün.</div>'}

<h2>Trial Detayları</h2>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#c8e6c9"></div> Ödül</div>
  <div class="legend-item"><div class="legend-dot" style="background:#ffe0b2"></div> Ceza</div>
  <div class="legend-item"><div class="legend-dot" style="background:#ffcdd2"></div> Omission</div>
  <div class="legend-item"><div class="legend-dot" style="background:#bbdefb"></div> Correct Rejection</div>
  <div class="legend-item">✓ = Kriter sağlandı</div>
  <div class="legend-item">⚠ = Ses onayı yok</div>
</div>

<table>
  <thead>
    <tr>
      <th>Trial</th>
      <th>DS Tipi</th>
      <th>Sonuç</th>
      <th>RT (DS'den) sn</th>
      <th>RT (Lever'dan) sn</th>
      <th>Lick</th>
      <th>ITI Press</th>
      <th>Hit Rate</th>
      <th>CR Rate</th>
      <th>d'</th>
      <th>Kriter</th>
      <th>Ses</th>
    </tr>
  </thead>
  <tbody>
    {trial_rows_html}
  </tbody>
</table>

<p style="margin-top:32px;font-size:11px;color:#aaa;text-align:center">
  Boğaziçi Üniversitesi Davranışsal Nörobilim Laboratuvarı —
  Oluşturulma: {datetime.now().strftime("%d.%m.%Y %H:%M")}
</p>

</body>
</html>"""

    # ── Kaydet ────────────────────────────────────────────────────────────────
    report_path = csv_path.replace(".csv", "_rapor.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    return report_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python3 report.py logs/session_RAT_01_....csv")
        sys.exit(1)
    path = generate_report(sys.argv[1])
    print(f"Rapor oluşturuldu: {path}")
    webbrowser.open(f"file://{os.path.abspath(path)}")
