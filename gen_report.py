#!/usr/bin/env python3
"""
CPL Report HTML Generator - Cloud Edition
Reads cpl_raw_data.json + cpl_mtd_raw.json + cpl_summary.json, generates report.html
"""
import json, os

ROOT = os.environ.get('GITHUB_WORKSPACE', os.path.dirname(os.path.abspath(__file__)))

with open(f'{ROOT}/cpl_raw_data.json') as f:
    all_data = json.load(f)
with open(f'{ROOT}/cpl_mtd_raw.json') as f:
    mtd_data = json.load(f)
with open(f'{ROOT}/cpl_summary.json') as f:
    summary = json.load(f)

today_d = all_data['today']
yesterday_d = all_data['yesterday']
last_week_d = all_data['last_week']

# Use dates from summary
MAIN_DATE = summary['main_date']
MAIN_DISPLAY = summary['main_display']

# ── Helpers ──
def sf(v, d=0):
    try: return float(v) if v else d
    except: return d
def si(v, d=0):
    try: return int(v) if v else d
    except: return d
def pct(c, p):
    if p == 0 or p is None: return None
    return (c - p) / p * 100
def fmt_pct(c, p):
    d = pct(c, p)
    if d is None: return '-', 'gray'
    return f"{d:+.1f}%", 'green' if d >= 0 else 'red'

def classify(name):
    n = (name or '').lower()
    if 'emu' in n: return 'EMU'
    if '外放' in n: return '外部'
    if 'facebook' in n or 'tiktok' in n or '内部' in n: return '内部'
    if '外投' in n: return '外部'
    return '外部'

def agg_aff(details):
    m = {}
    for r in details:
        aid = si(r.get('affiliateId', 0))
        if not aid: continue
        name = r.get('affiliateName', '')
        cat = classify(name)
        rev = sf(r.get('revenue', 0)); gp = sf(r.get('gp', 0))
        conv = si(r.get('conversionCount', 0)); clk = si(r.get('totalClickCount', 0))
        mp = sf(r.get('mediaPayout', 0)); ap = sf(r.get('affPayout', 0))
        unique_clk = si(r.get('uniqueClickCount', 0)); aff_conv = si(r.get('affConversionCount', 0))
        oid = str(r.get('offerId', '')); oname = r.get('offerName', '')
        if aid not in m:
            m[aid] = {'aid': aid, 'name': name, 'cat': cat,
                      'rev': 0, 'gp': 0, 'conv': 0, 'clk': 0, 'mp': 0, 'ap': 0,
                      'unique_clk': 0, 'aff_conv': 0, 'offers': {}}
        e = m[aid]
        e['rev'] += rev; e['gp'] += gp; e['conv'] += conv
        e['clk'] += clk; e['mp'] += mp; e['ap'] += ap
        e['unique_clk'] += unique_clk; e['aff_conv'] += aff_conv
        if oid not in e['offers']:
            e['offers'][oid] = {'name': oname, 'rev': 0, 'gp': 0, 'conv': 0, 'ap': 0}
        e['offers'][oid]['rev'] += rev; e['offers'][oid]['gp'] += gp
        e['offers'][oid]['conv'] += conv; e['offers'][oid]['ap'] += ap
    for v in m.values():
        v['epc'] = v['rev'] / v['clk'] if v['clk'] else 0
        v['cr'] = v['conv'] / v['clk'] * 100 if v['clk'] else 0
        v['vpn'] = v['unique_clk'] / v['clk'] * 100 if v['clk'] else 0
    return m

def agg_adv(details):
    m = {}
    for r in details:
        aid = si(r.get('advertiserId', 0))
        if not aid: continue
        rev = sf(r.get('revenue', 0)); gp = sf(r.get('gp', 0))
        conv = si(r.get('conversionCount', 0)); mp = sf(r.get('mediaPayout', 0))
        ap = sf(r.get('affPayout', 0))
        if aid not in m:
            m[aid] = {'aid': aid, 'name': r.get('advertiserName', ''), 'rev': 0, 'gp': 0, 'conv': 0, 'mp': 0, 'ap': 0, 'clk': 0}
        e = m[aid]
        e['rev'] += rev; e['gp'] += gp; e['conv'] += conv; e['mp'] += mp; e['ap'] += ap
        e['clk'] += si(r.get('totalClickCount', 0))
    return {k: v for k, v in m.items() if v['conv'] > 0}

today_aff = agg_aff(today_d['details'])
yday_aff = agg_aff(yesterday_d['details'])
lwk_aff = agg_aff(last_week_d['details'])
today_ex = {k: v for k, v in today_aff.items() if v['cat'] == '外部'}
today_in = {k: v for k, v in today_aff.items() if v['cat'] == '内部'}
today_adv = agg_adv(today_d['details'])
yday_adv = agg_adv(yesterday_d['details'])
lwk_adv = agg_adv(last_week_d['details'])
mtd_adv = agg_adv(mtd_data['details'])

ts = today_d['summary']; ys = yesterday_d['summary']; ls = last_week_d['summary']; ms = mtd_data['summary']

# ─── KPI Table ───
def kpi_row(label, fmt_fn, tv, yv, lv):
    d_delta = pct(tv, yv) if yv else None
    w_delta = pct(tv, lv) if lv else None
    d_str = f"{d_delta:+.1f}%" if d_delta is not None else '-'
    w_str = f"{w_delta:+.1f}%" if w_delta is not None else '-'
    dc = 'green' if (d_delta or 0) >= 0 else 'red'
    wc = 'green' if (w_delta or 0) >= 0 else 'red'
    return f"""<tr>
        <td><strong>{label}</strong></td>
        <td class="num">{fmt_fn(tv)}</td>
        <td class="num">{fmt_fn(yv)}</td>
        <td class="num {dc}">{d_str}</td>
        <td class="num">{fmt_fn(lv)}</td>
        <td class="num {wc}">{w_str}</td>
    </tr>"""

kpi_rows = (
    kpi_row('Revenue', lambda x: f"${x:,.2f}", sf(ts['revenue']), sf(ys['revenue']), sf(ls['revenue'])) +
    kpi_row('GP', lambda x: f"${x:,.2f}", sf(ts['gp']), sf(ys['gp']), sf(ls['gp'])) +
    kpi_row('Conversions', lambda x: f"{int(x):,}", si(ts['conversionCount']), si(ys['conversionCount']), si(ls['conversionCount'])) +
    kpi_row('Media Payout', lambda x: f"${x:,.2f}", sf(ts['mediaPayout']), sf(ys['mediaPayout']), sf(ls['mediaPayout'])) +
    kpi_row('Aff Payout', lambda x: f"${x:,.2f}", sf(ts['affPayout']), sf(ys['affPayout']), sf(ls['affPayout'])) +
    kpi_row('Total Clicks', lambda x: f"{int(x):,}", si(ts['totalClickCount']), si(ys['totalClickCount']), si(ls['totalClickCount'])) +
    kpi_row('CR (%)', lambda x: f"{x:.2f}%", sf(ts['cr']), sf(ys['cr']), sf(ls['cr'])) +
    kpi_row('EPC', lambda x: f"${x:.4f}", sf(ts['epc']), sf(ys['epc']), sf(ls['epc'])) +
    kpi_row('VPN Rate (%)', lambda x: f"{x:.2f}%", sf(ts['vpnRate']), sf(ys['vpnRate']), sf(ls['vpnRate']))
)

# ─── Channel Tables ───
def chan_table(aff_map, prev_map, prev_wk_map):
    ext = sorted(aff_map.values(), key=lambda x: x['rev'], reverse=True)
    rows = ''
    for i, e in enumerate(ext):
        aid = e['aid']; name = e['name'][:30]
        prev = prev_map.get(aid) if prev_map else None
        pw = prev_wk_map.get(aid) if prev_wk_map else None
        d_str, dc = fmt_pct(e['rev'], prev['rev']) if prev else ('-', 'gray')
        w_str, wc = fmt_pct(e['rev'], pw['rev']) if pw else ('-', 'gray')
        rows += f"""<tr>
            <td>{i+1}</td>
            <td><strong>{aid}</strong><br><span class="sub">{name}</span></td>
            <td class="num">${e['rev']:,.2f}</td>
            <td class="num">${e['gp']:,.2f}</td>
            <td class="num">${e['epc']:.4f}</td>
            <td class="num">{e['cr']:.2f}%</td>
            <td class="num">{e['vpn']:.1f}%</td>
            <td class="num">{e['conv']}</td>
            <td class="num">${e['ap']:,.2f}</td>
            <td class="num {dc}">{d_str}</td>
            <td class="num {wc}">{w_str}</td>
        </tr>"""
    return rows

chan_rows = chan_table(today_ex, yday_aff, lwk_aff)

def internal_table(aff_map):
    inn = sorted(aff_map.values(), key=lambda x: x['rev'], reverse=True)
    rows = ''
    for i, e in enumerate(inn):
        rows += f"""<tr>
            <td>{i+1}</td>
            <td><strong>{e['aid']}</strong><br><span class="sub">{e['name'][:30]}</span></td>
            <td class="num">${e['rev']:,.2f}</td>
            <td class="num">${e['gp']:,.2f}</td>
            <td class="num">{e['conv']}</td>
            <td class="num">${e['epc']:.4f}</td>
        </tr>"""
    return rows
internal_rows = internal_table(today_in)

# ─── Top 5 Offers ───
offer_sections = ''
for e in sorted(today_ex.values(), key=lambda x: x['rev'], reverse=True):
    offs = sorted(e['offers'].values(), key=lambda x: x['conv'], reverse=True)[:5]
    orows = ''
    for j, o in enumerate(offs):
        nm = o['name'][:50]
        orows += f"<tr><td>{j+1}</td><td>{nm}</td><td class=num>{o['conv']}</td><td class=num>${o['rev']:,.2f}</td><td class=num>${o['gp']:,.2f}</td></tr>"
    if not orows:
        orows = '<tr><td colspan=5>No data</td></tr>'
    offer_sections += f"""<div class="offer-section">
        <div class="offer-header" onclick="toggle('offers-{e['aid']}')">
            <span>[{e['aid']}] {e['name'][:40]}</span>
            <span id="arr-offers-{e['aid']}" class="arrow">&#9660;</span>
        </div>
        <div id="offers-{e['aid']}" style="display:none">
            <table class="data-table"><thead><tr><th>#</th><th>Offer Name</th><th>Conv</th><th>Revenue</th><th>GP</th></tr></thead><tbody>{orows}</tbody></table>
        </div>
    </div>"""

# ─── Advertiser Tables ───
def adv_mtd_table(mtd_map, today_map):
    lst = sorted(mtd_map.values(), key=lambda x: x['rev'], reverse=True)
    rows = ''
    for i, e in enumerate(lst):
        today_e = today_map.get(e['aid'])
        margin = e['gp']/e['rev']*100 if e['rev'] > 0 else 0
        epc = e['rev']/e['clk'] if e['clk'] > 0 else 0
        name = e['name'][:35]; today_rev = today_e['rev'] if today_e else 0
        rows += f"""<tr>
            <td>{i+1}</td>
            <td><strong>{e['aid']}</strong><br><span class="sub">{name}</span></td>
            <td class="num">${e['rev']:,.2f}</td>
            <td class="num">${e['gp']:,.2f}</td>
            <td class="num">{margin:.1f}%</td>
            <td class="num">{e['conv']}</td>
            <td class="num">${e['mp']:,.2f}</td>
            <td class="num">${epc:.4f}</td>
            <td class="num">${today_rev:,.2f}</td>
        </tr>"""
    return rows

def adv_daily_table(adv_map, prev_map, prev_wk_map):
    lst = sorted(adv_map.values(), key=lambda x: x['rev'], reverse=True)
    rows = ''
    for i, e in enumerate(lst):
        name = e['name'][:35]
        prev = prev_map.get(e['aid']); pw = prev_wk_map.get(e['aid'])
        d_str, dc = fmt_pct(e['rev'], prev['rev']) if prev else ('-', 'gray')
        w_str, wc = fmt_pct(e['rev'], pw['rev']) if pw else ('-', 'gray')
        margin = e['gp']/e['rev']*100 if e['rev'] else 0
        rows += f"""<tr>
            <td>{i+1}</td>
            <td><strong>{e['aid']}</strong><br><span class="sub">{name}</span></td>
            <td class="num">${e['rev']:,.2f}</td>
            <td class="num">${e['gp']:,.2f}</td>
            <td class="num">{margin:.1f}%</td>
            <td class="num">{e['conv']}</td>
            <td class="num">${e['mp']:,.2f}</td>
            <td class="num {dc}">{d_str}</td>
            <td class="num {wc}">{w_str}</td>
        </tr>"""
    return rows

mtd_rows = adv_mtd_table(mtd_adv, today_adv)
adv_daily_rows = adv_daily_table(today_adv, yday_adv, lwk_adv)

# ─── Chart Data ───
ext_sorted = sorted(today_ex.values(), key=lambda x: x['rev'], reverse=True)
chan_labels = json.dumps([f"{e['aid']}" for e in ext_sorted])
chan_rev = json.dumps([round(e['rev'], 2) for e in ext_sorted])
chan_gp = json.dumps([round(e['gp'], 2) for e in ext_sorted])
payout_data = json.dumps([round(e['mp'], 2) for e in ext_sorted])

adv_sorted = sorted(today_adv.values(), key=lambda x: x['rev'], reverse=True)
adv_labels = json.dumps([e['name'][:25] for e in adv_sorted])
adv_rev = json.dumps([round(e['rev'], 2) for e in adv_sorted])
adv_gp = json.dumps([round(e['gp'], 2) for e in adv_sorted])

mtd_sorted = sorted(mtd_adv.values(), key=lambda x: x['rev'], reverse=True)
mtd_labels_chart = json.dumps([f"{e['aid']}" for e in mtd_sorted])
mtd_rev_chart = json.dumps([round(e['rev'], 2) for e in mtd_sorted])
mtd_gp_chart = json.dumps([round(e['gp'], 2) for e in mtd_sorted])

rev_t = sf(ts['revenue']); rev_y = sf(ys['revenue']); rev_w = sf(ls['revenue'])
gp_t = sf(ts['gp']); gp_y = sf(ys['gp']); gp_w = sf(ls['gp'])
conv_t = si(ts['conversionCount']); conv_y = si(ys['conversionCount'])
mp_t = sf(ts['mediaPayout']); ap_t = sf(ts['affPayout'])
margin_t = gp_t/rev_t*100 if rev_t else 0; margin_y = gp_y/rev_y*100 if rev_y else 0
best_ch = ext_sorted[0] if ext_sorted else None
best_adv = adv_sorted[0] if adv_sorted else None
mtd_best_adv = mtd_sorted[0] if mtd_sorted else None
mtd_total_rev = sf(ms['revenue'])
mtd_total_gp = sf(ms['gp'])
mtd_total_conv = si(ms['conversionCount'])
mtd_days_count = (int(MAIN_DATE[-2:]) - 1)  # approximate

# Summary text
summary_text = f"""
<p><strong>Overall Performance:</strong></p>
<p>{MAIN_DATE}: Revenue <strong>${rev_t:,.2f}</strong>, GP <strong>${gp_t:,.2f}</strong> (Margin {margin_t:.1f}%), Conversions <strong>{conv_t:,}</strong>.</p>
<p>Day-over-Day: Rev {pct(rev_t, rev_y):+.1f}%, GP {pct(gp_t, gp_y):+.1f}%. Media Payout {pct(mp_t, sf(ys['mediaPayout'])):+.1f}%.</p>
<p>Week-over-Week: Rev {pct(rev_t, rev_w):+.1f}%, GP {pct(gp_t, gp_w):+.1f}%.</p>
<p><strong>External Channels:</strong> {len(ext_sorted)} total. Top: <strong>[{best_ch['aid']}] {best_ch['name']}</strong> (${best_ch['rev']:,.2f}).</p>
"""
if best_adv:
    summary_text += f"""<p><strong>Advertisers (Today):</strong> {len(adv_sorted)} with conversions. Top: <strong>[{best_adv['aid']}] {best_adv['name']}</strong> (${best_adv['rev']:,.2f}).</p>"""
if mtd_best_adv:
    summary_text += f"""<p><strong>Advertisers (MTD):</strong> Total Rev <strong>${mtd_total_rev:,.2f}</strong>. Top: <strong>[{mtd_best_adv['aid']}] {mtd_best_adv['name']}</strong> (${mtd_best_adv['rev']:,.2f}).</p>"""

# ─── HTML ───
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CPL Daily Report — {MAIN_DATE}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f5f7fa; color: #1a1a2e; padding: 20px; }}
.container {{ max-width: 1300px; margin: 0 auto; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
h2 {{ font-size: 18px; color: #333; border-bottom: 2px solid #4f46e5; padding-bottom: 8px; margin: 32px 0 16px; }}
.subtitle {{ font-size: 13px; color: #888; margin-bottom: 24px; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 24px; }}
.kpi-card {{ background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); text-align: center; }}
.kpi-card .kpi-label {{ font-size: 11px; color: #888; letter-spacing: .5px; margin-bottom: 4px; }}
.kpi-card .kpi-value {{ font-size: 22px; font-weight: 700; }}
.kpi-card .kpi-sub {{ font-size: 11px; color: #999; margin-top: 2px; }}
.kpi-card.revenue .kpi-value {{ color: #4f46e5; }}
.kpi-card.gp .kpi-value {{ color: #059669; }}
.kpi-card.conv .kpi-value {{ color: #d97706; }}
.kpi-card.payout .kpi-value {{ color: #dc2626; }}
.kpi-card.clicks .kpi-value {{ color: #2563eb; }}
.table-wrap {{ overflow-x: auto; background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.08); padding: 12px; margin-bottom: 20px; }}
.data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.data-table th {{ background: #f1f5f9; padding: 10px 8px; text-align: left; font-size: 11px; color: #64748b; white-space: nowrap; }}
.data-table td {{ padding: 8px; border-bottom: 1px solid #f1f5f9; }}
.data-table tr:hover {{ background: #f8fafc; }}
.num {{ text-align: right !important; }}
.green {{ color: #16a34a !important; }}
.red {{ color: #dc2626 !important; }}
.gray {{ color: #94a3b8 !important; }}
.sub {{ font-size: 11px; color: #94a3b8; }}
.chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
.chart-row.single {{ grid-template-columns: 2fr 1fr; }}
.chart-box {{ background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.08); padding: 16px; }}
.chart-box canvas {{ max-height: 360px; }}
.mtd-badge {{ display: inline-block; background: #fef3c7; color: #92400e; font-size: 11px; padding: 2px 8px; border-radius: 4px; margin-left: 8px; }}
.offer-section {{ margin-bottom: 4px; }}
.offer-header {{ background: #f8fafc; padding: 10px 14px; border-radius: 8px; cursor: pointer; display: flex; justify-content: space-between; font-size: 13px; font-weight: 500; }}
.offer-header:hover {{ background: #eef2ff; }}
.arrow {{ transition: transform .2s; font-size: 11px; }}
.summary-box {{ background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.08); padding: 20px; line-height: 1.8; font-size: 14px; margin-bottom: 24px; }}
.summary-box p {{ margin-bottom: 8px; }}
@media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns: repeat(3, 1fr); }}
    .chart-row, .chart-row.single {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="container">
<h1>CPL Daily Analysis Report</h1>
<div class="subtitle">Analysis Date: {MAIN_DATE} ({MAIN_DISPLAY}, GMT) | Auto-generated by GitHub Actions
<br>Classification: External = contains "外放" | Internal = contains "Facebook/TikTok/内部" | EMU excluded</div>

<!-- KPI Cards -->
<div class="kpi-grid">
    <div class="kpi-card revenue"><div class="kpi-label">Revenue</div><div class="kpi-value">${rev_t:,.2f}</div></div>
    <div class="kpi-card gp"><div class="kpi-label">GP</div><div class="kpi-value">${gp_t:,.2f}</div><div class="kpi-sub">Margin {margin_t:.1f}%</div></div>
    <div class="kpi-card conv"><div class="kpi-label">Conversions</div><div class="kpi-value">{conv_t:,}</div></div>
    <div class="kpi-card payout"><div class="kpi-label">Media Payout</div><div class="kpi-value">${mp_t:,.2f}</div><div class="kpi-sub">Aff Payout ${ap_t:,.2f}</div></div>
    <div class="kpi-card clicks"><div class="kpi-label">Total Clicks</div><div class="kpi-value">{si(ts['totalClickCount']):,}</div><div class="kpi-sub">EPC ${sf(ts['epc']):.4f} | CR {sf(ts['cr']):.2f}%</div></div>
</div>

<!-- Comparison Table -->
<h2>1. KPI Comparison</h2>
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>Metric</th><th>{MAIN_DATE}</th><th>Day Before</th><th>DoD</th><th>Last Week</th><th>WoW</th></tr></thead>
        <tbody>{kpi_rows}</tbody>
    </table>
</div>

<!-- External Channel Charts -->
<h2>2. External Channel Revenue & Payout</h2>
<div class="chart-row">
    <div class="chart-box"><canvas id="chanBar"></canvas></div>
    <div class="chart-box"><canvas id="payoutPie"></canvas></div>
</div>

<!-- External Channel Ranking -->
<h2>3. External Channel Ranking <span class="mtd-badge">Name contains "外放"</span></h2>
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>#</th><th>Channel</th><th>Revenue</th><th>GP</th><th>EPC</th><th>CR</th><th>VPN</th><th>Conv</th><th>Aff Payout</th><th>DoD</th><th>WoW</th></tr></thead>
        <tbody>{chan_rows}</tbody>
    </table>
</div>

<!-- Top 5 Offers -->
<h2>4. Top 5 Offers per External Channel (by Conversions)</h2>
{offer_sections}

<!-- Advertiser Daily -->
<h2>5. Advertiser Daily Ranking</h2>
<div class="chart-row single">
    <div class="chart-box"><canvas id="advBar"></canvas></div>
    <div class="chart-box"><canvas id="advGPBar"></canvas></div>
</div>
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>#</th><th>Advertiser</th><th>Revenue</th><th>GP</th><th>Margin</th><th>Conv</th><th>Media Payout</th><th>DoD</th><th>WoW</th></tr></thead>
        <tbody>{adv_daily_rows}</tbody>
    </table>
</div>

<!-- MTD Advertiser -->
<h2>6. Advertiser MTD <span class="mtd-badge">Month-to-Date</span></h2>
<p style="color:#888;font-size:12px;margin-bottom:10px;">
    MTD Total Revenue <strong>${mtd_total_rev:,.2f}</strong> | GP <strong>${mtd_total_gp:,.2f}</strong> | Conversions <strong>{mtd_total_conv:,}</strong>
</p>
<div class="chart-row">
    <div class="chart-box"><canvas id="mtdBar"></canvas></div>
    <div class="chart-box"><canvas id="mtdGPBar"></canvas></div>
</div>
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>#</th><th>Advertiser</th><th>MTD Revenue</th><th>MTD GP</th><th>Margin</th><th>Conv</th><th>MTD Payout</th><th>EPC</th><th>Today Rev</th></tr></thead>
        <tbody>{mtd_rows}</tbody>
    </table>
</div>

<!-- Summary -->
<h2>7. Summary</h2>
<div class="summary-box">{summary_text}</div>

</div>
<script>
function toggle(id) {{
    const el = document.getElementById(id);
    const arr = document.getElementById('arr-' + id);
    if (el.style.display === 'none') {{ el.style.display = 'block'; arr.innerHTML = '&#9650;'; }}
    else {{ el.style.display = 'none'; arr.innerHTML = '&#9660;'; }}
}}
new Chart(document.getElementById('chanBar'), {{
    type: 'bar',
    data: {{
        labels: {chan_labels},
        datasets: [
            {{ label: 'Revenue', data: {chan_rev}, backgroundColor: '#4f46e5', borderRadius: 4 }},
            {{ label: 'GP', data: {chan_gp}, backgroundColor: '#059669', borderRadius: 4 }}
        ]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ position: 'top' }}, title: {{ display: true, text: 'Revenue vs GP' }} }},
        scales: {{ y: {{ beginAtZero: true, ticks: {{ callback: v => '$' + v.toLocaleString() }} }} }}
    }}
}});
new Chart(document.getElementById('payoutPie'), {{
    type: 'doughnut',
    data: {{
        labels: {chan_labels},
        datasets: [{{ data: {payout_data}, backgroundColor: ['#4f46e5','#059669','#d97706','#dc2626','#2563eb','#7c3aed','#db2777','#0891b2','#65a30d','#ea580c'] }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ position: 'right' }}, title: {{ display: true, text: 'Media Payout Distribution' }} }} }}
}});
new Chart(document.getElementById('advBar'), {{
    type: 'bar',
    data: {{
        labels: {adv_labels},
        datasets: [{{ label: 'Revenue', data: {adv_rev}, backgroundColor: '#4f46e5', borderRadius: 4 }}]
    }},
    options: {{
        indexAxis: 'y', responsive: true,
        plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: '{MAIN_DATE} Advertiser Revenue' }} }},
        scales: {{ x: {{ ticks: {{ callback: v => '$' + v.toLocaleString() }} }} }}
    }}
}});
new Chart(document.getElementById('advGPBar'), {{
    type: 'bar',
    data: {{
        labels: {adv_labels},
        datasets: [{{ label: 'GP', data: {adv_gp}, backgroundColor: '#059669', borderRadius: 4 }}]
    }},
    options: {{
        indexAxis: 'y', responsive: true,
        plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: '{MAIN_DATE} Advertiser GP' }} }},
        scales: {{ x: {{ ticks: {{ callback: v => '$' + v.toLocaleString() }} }} }}
    }}
}});
new Chart(document.getElementById('mtdBar'), {{
    type: 'bar',
    data: {{
        labels: {mtd_labels_chart},
        datasets: [{{ label: 'MTD Revenue', data: {mtd_rev_chart}, backgroundColor: '#7c3aed', borderRadius: 4 }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Advertiser MTD Revenue' }} }},
        scales: {{ y: {{ beginAtZero: true, ticks: {{ callback: v => '$' + v.toLocaleString() }} }} }}
    }}
}});
new Chart(document.getElementById('mtdGPBar'), {{
    type: 'bar',
    data: {{
        labels: {mtd_labels_chart},
        datasets: [{{ label: 'MTD GP', data: {mtd_gp_chart}, backgroundColor: '#059669', borderRadius: 4 }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Advertiser MTD GP' }} }},
        scales: {{ y: {{ beginAtZero: true, ticks: {{ callback: v => '$' + v.toLocaleString() }} }} }}
    }}
}});
</script>
</body>
</html>"""

out_path = f'{ROOT}/report.html'
with open(out_path, 'w') as f:
    f.write(html)
print(f"Report saved to {out_path} ({os.path.getsize(out_path):,} bytes)")
