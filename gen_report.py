#!/usr/bin/env python3
"""CPL Report HTML Generator - Cloud Edition v3
Reads cpl_raw_data.json + cpl_mtd_raw.json, generates docs/report.html
Optimized per Freda's requirements:
- External channels: ID whitelist + name fallback
- No Revenue/Payout columns in external channel table
- Total rows in all tables
- No charts
"""
import json, os, sys
from datetime import datetime, timedelta, timezone

# ─── External Channel ID Whitelist ────────────────────────────────
EXT_IDS = {476, 477, 451, 432, 365, 318, 323, 412, 336,
           283, 395, 442, 457, 433, 393}

ROOT = os.environ.get('GITHUB_WORKSPACE', os.path.dirname(os.path.abspath(__file__)))

with open(f'{ROOT}/cpl_raw_data.json') as f:
    all_data = json.load(f)
with open(f'{ROOT}/cpl_mtd_raw.json') as f:
    mtd_data = json.load(f)

today_d = all_data['today']
yesterday_d = all_data['yesterday']
last_week_d = all_data['last_week']

def date_label(dt_str):
    d = datetime.strptime(dt_str[:10], '%Y-%m-%d')
    wk = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d.weekday()]
    return f"{d.month}/{d.day} {wk}"

MAIN_DATE = today_d['summary'].get('dataTime', '2026-06-11')[:10]
main_display = date_label(MAIN_DATE)
yd_display = date_label(yesterday_d['summary'].get('dataTime','2026-06-10')[:10])
lw_display = date_label(last_week_d['summary'].get('dataTime','2026-06-04')[:10])

m1_date = datetime.strptime(MAIN_DATE[:7] + '-01', '%Y-%m-%d').date()
today_date = datetime.strptime(MAIN_DATE, '%Y-%m-%d').date()
mtd_days = (today_date - m1_date).days + 1
mtd_range = f"{m1_date.month}/1 - {main_display.split()[0]}"

# ─── Channel Classification ────────────────────────────────────────
def classify(aid, name):
    if aid in EXT_IDS:
        return '外部'
    n = (name or '').lower()
    if 'emu' in n:
        return 'EMU'
    if '外放' in n:
        return '外部'
    if 'facebook' in n or 'tiktok' in n or '内部' in n:
        return '内部'
    if '外投' in n:
        return '外部'
    return '外部'

# ─── Helpers ──────────────────────────────────────────────────────
def sf(v, d=0):
    try: return float(v) if v else d
    except: return d

def si(v, d=0):
    try: return int(v) if v else d
    except: return d

def pct(c, p):
    if p == 0 or p is None:
        return None
    return (c - p) / p * 100

def fmt_pct(c, p):
    d = pct(c, p)
    if d is None:
        return '-', 'gray'
    return f"{d:+.1f}%", 'green' if d >= 0 else 'red'

# ─── Aggregate by Affiliate ──────────────────────────────────────
def agg_aff(details):
    m = {}
    for r in details:
        aid = si(r.get('affiliateId', 0))
        if not aid:
            continue
        name = r.get('affiliateName', '')
        cat = classify(aid, name)
        rev = sf(r.get('revenue', 0))
        gp = sf(r.get('gp', 0))
        conv = si(r.get('conversionCount', 0))
        clk = si(r.get('totalClickCount', 0))
        mp = sf(r.get('mediaPayout', 0))
        ap = sf(r.get('affPayout', 0))
        unique_clk = si(r.get('uniqueClickCount', 0))
        aff_conv = si(r.get('affConversionCount', 0))
        oid = str(r.get('offerId', ''))
        oname = r.get('offerName', '')

        key = aid
        if key not in m:
            m[key] = {
                'aid': aid, 'name': name, 'cat': cat,
                'rev': 0, 'gp': 0, 'conv': 0, 'clk': 0,
                'mp': 0, 'ap': 0, 'unique_clk': 0, 'aff_conv': 0,
                'offers': {}
            }
        e = m[key]
        e['rev'] += rev
        e['gp'] += gp
        e['conv'] += conv
        e['clk'] += clk
        e['mp'] += mp
        e['ap'] += ap
        e['unique_clk'] += unique_clk
        e['aff_conv'] += aff_conv

        if oid not in e['offers']:
            e['offers'][oid] = {'name': oname, 'rev': 0, 'gp': 0, 'conv': 0, 'ap': 0}
        e['offers'][oid]['rev'] += rev
        e['offers'][oid]['gp'] += gp
        e['offers'][oid]['conv'] += conv
        e['offers'][oid]['ap'] += ap

    for v in m.values():
        v['epc'] = v['rev'] / v['clk'] if v['clk'] else 0
        v['cr'] = v['conv'] / v['clk'] * 100 if v['clk'] else 0
        v['vpn'] = v['unique_clk'] / v['clk'] * 100 if v['clk'] else 0
    return m

# ─── Aggregate by Advertiser ─────────────────────────────────────
def agg_adv(details):
    m = {}
    for r in details:
        aid = si(r.get('advertiserId', 0))
        if not aid:
            continue
        rev = sf(r.get('revenue', 0))
        gp = sf(r.get('gp', 0))
        conv = si(r.get('conversionCount', 0))
        mp = sf(r.get('mediaPayout', 0))
        ap = sf(r.get('affPayout', 0))
        clk = si(r.get('totalClickCount', 0))
        key = aid
        if key not in m:
            m[key] = {
                'aid': aid, 'name': r.get('advertiserName', ''),
                'rev': 0, 'gp': 0, 'conv': 0, 'mp': 0, 'ap': 0, 'clk': 0
            }
        e = m[key]
        e['rev'] += rev
        e['gp'] += gp
        e['conv'] += conv
        e['mp'] += mp
        e['ap'] += ap
        e['clk'] += clk
    return {k: v for k, v in m.items() if v['conv'] > 0}

# ─── Run Aggregation ────────────────────────────────────────────
today_aff = agg_aff(today_d['details'])
yday_aff = agg_aff(yesterday_d['details'])
lwk_aff = agg_aff(last_week_d['details'])

today_ex = {k: v for k, v in today_aff.items() if v['cat'] == '外部'}
today_in = {k: v for k, v in today_aff.items() if v['cat'] == '内部'}

today_adv = agg_adv(today_d['details'])
yday_adv = agg_adv(yesterday_d['details'])
lwk_adv = agg_adv(last_week_d['details'])
mtd_adv = agg_adv(mtd_data['details'])

# ─── KPI Rows ───────────────────────────────────────────────────
ts = today_d['summary']
ys = yesterday_d['summary']
ls = last_week_d['summary']
ms = mtd_data['summary']

def kpi_row(label, fmt_fn, tv, yv, lv):
    d_delta = pct(tv, yv) if yv else None
    w_delta = pct(tv, lv) if lv else None
    d_str = f"{d_delta:+.1f}%" if d_delta is not None else '-'
    w_str = f"{w_delta:+.1f}%" if w_delta is not None else '-'
    dc = 'green' if (d_delta or 0) >= 0 else 'red'
    wc = 'green' if (w_delta or 0) >= 0 else 'red'
    return (
        f"<tr><td><strong>{label}</strong></td>"
        f"<td class='num'>{fmt_fn(tv)}</td>"
        f"<td class='num'>{fmt_fn(yv)}</td>"
        f"<td class='num {dc}'>{d_str}</td>"
        f"<td class='num'>{fmt_fn(lv)}</td>"
        f"<td class='num {wc}'>{w_str}</td></tr>"
    )

kpi_rows = (
    kpi_row('Revenue', lambda x: f"${x:,.2f}", sf(ts['revenue']), sf(ys['revenue']), sf(ls['revenue'])) +
    kpi_row('GP (毛利)', lambda x: f"${x:,.2f}", sf(ts['gp']), sf(ys['gp']), sf(ls['gp'])) +
    kpi_row('Conversions', lambda x: f"{int(x):,}", si(ts['conversionCount']), si(ys['conversionCount']), si(ls['conversionCount'])) +
    kpi_row('Media Payout', lambda x: f"${x:,.2f}", sf(ts['mediaPayout']), sf(ys['mediaPayout']), sf(ls['mediaPayout'])) +
    kpi_row('Aff Payout', lambda x: f"${x:,.2f}", sf(ts['affPayout']), sf(ys['affPayout']), sf(ls['affPayout'])) +
    kpi_row('Total Clicks', lambda x: f"{int(x):,}", si(ts['totalClickCount']), si(ys['totalClickCount']), si(ls['totalClickCount'])) +
    kpi_row('CR (%)', lambda x: f"{x:.2f}%", sf(ts['cr']), sf(ys['cr']), sf(ls['cr'])) +
    kpi_row('EPC', lambda x: f"${x:.4f}", sf(ts['epc']), sf(ys['epc']), sf(ls['epc'])) +
    kpi_row('VPN Rate (%)', lambda x: f"{x:.2f}%", sf(ts['vpnRate']), sf(ys['vpnRate']), sf(ls['vpnRate']))
)

# ─── External Channel Table (no Revenue/Payout) ─────────────────
def chan_table_v3(aff_map_today, prev_map, prev_wk_map):
    ext = sorted(aff_map_today.values(), key=lambda x: x['rev'], reverse=True)
    if not ext:
        return '', 0, 0, 0

    rows = ''
    total_conv = 0
    total_rev = 0
    total_gp = 0
    total_clk = 0
    for i, e in enumerate(ext):
        aid = e['aid']
        name = e['name'][:30]
        prev = prev_map.get(aid) if prev_map else None
        pw = prev_wk_map.get(aid) if prev_wk_map else None
        d_str, dc = fmt_pct(e['rev'], prev['rev']) if prev else ('-', 'gray')
        w_str, wc = fmt_pct(e['rev'], pw['rev']) if pw else ('-', 'gray')
        total_conv += e['conv']
        total_rev += e['rev']
        total_gp += e['gp']
        total_clk += e['clk']
        rows += (
            f"<tr><td>{i+1}</td>"
            f"<td><strong>{aid}</strong><br><span class='sub'>{name}</span></td>"
            f"<td class='num'>${e['gp']:,.2f}</td>"
            f"<td class='num'>${e['epc']:.4f}</td>"
            f"<td class='num'>{e['cr']:.2f}%</td>"
            f"<td class='num'>{e['vpn']:.1f}%</td>"
            f"<td class='num'>{e['conv']}</td>"
            f"<td class='num {dc}'>{d_str}</td>"
            f"<td class='num {wc}'>{w_str}</td></tr>"
        )

    total_epc = total_rev / total_clk if total_clk else 0
    total_cr = total_conv / total_clk * 100 if total_clk else 0
    total_row = (
        f"<tr style='background:#fef3c7;font-weight:600;'>"
        f"<td colspan=2>Total ({len(ext)} channels)</td>"
        f"<td class='num'>${total_gp:,.2f}</td>"
        f"<td class='num'>${total_epc:.4f}</td>"
        f"<td class='num'>{total_cr:.2f}%</td>"
        f"<td class='num'>-</td>"
        f"<td class='num'>{total_conv}</td>"
        f"<td class='num gray'>-</td>"
        f"<td class='num gray'>-</td></tr>"
    )
    return rows + total_row, total_conv, total_rev, total_gp

chan_rows_v3, ext_total_conv, ext_total_rev, ext_total_gp = chan_table_v3(
    today_ex, yday_aff, lwk_aff
)

# ─── Internal Channel Table ───────────────────────────────────────
def internal_table(aff_map):
    inn = sorted(aff_map.values(), key=lambda x: x['rev'], reverse=True)
    rows = ''
    for i, e in enumerate(inn):
        rows += (
            f"<tr><td>{i+1}</td>"
            f"<td><strong>{e['aid']}</strong><br><span class='sub'>{e['name'][:30]}</span></td>"
            f"<td class='num'>${e['rev']:,.2f}</td>"
            f"<td class='num'>${e['gp']:,.2f}</td>"
            f"<td class='num'>{e['conv']}</td>"
            f"<td class='num'>${e['epc']:.4f}</td></tr>"
        )
    return rows

internal_rows = internal_table(today_in)

# ─── Top 5 Offers per External Channel (with Total) ─────────────
offer_sections = ''
for e in sorted(today_ex.values(), key=lambda x: x['rev'], reverse=True):
    offs = sorted(e['offers'].values(), key=lambda x: x['conv'], reverse=True)[:5]
    orows = ''
    total_off_conv = 0
    total_off_rev = 0
    total_off_gp = 0
    for j, o in enumerate(offs):
        nm = o['name'][:50]
        total_off_conv += o['conv']
        total_off_rev += o['rev']
        total_off_gp += o['gp']
        orows += (
            f"<tr><td>{j+1}</td><td>{nm}</td>"
            f"<td class='num'>{o['conv']}</td>"
            f"<td class='num'>${o['rev']:,.2f}</td>"
            f"<td class='num'>${o['gp']:,.2f}</td></tr>"
        )
    if offs:
        orows += (
            f"<tr style='background:#f0fdf4;font-weight:600;'>"
            f"<td colspan=2>Total</td>"
            f"<td class='num'>{total_off_conv}</td>"
            f"<td class='num'>${total_off_rev:,.2f}</td>"
            f"<td class='num'>${total_off_gp:,.2f}</td></tr>"
        )
    else:
        orows = "<tr><td colspan=5>无数据</td></tr>"
    offer_sections += (
        f"<div class='offer-section'>"
        f"<div class='offer-header' onclick=\"toggle('offers-{e['aid']}')\">"
        f"<span>[{e['aid']}] {e['name'][:40]}</span>"
        f"<span id='arr-offers-{e['aid']}' class='arrow'>&#9660;</span>"
        f"</div>"
        f"<div id='offers-{e['aid']}' style='display:none;'>"
        f"<table class='data-table'>"
        f"<thead><tr><th>#</th><th>Offer Name</th><th>Conv</th><th>Revenue</th><th>GP</th></tr></thead>"
        f"<tbody>{orows}</tbody></table>"
        f"</div></div>"
    )

# ─── Advertiser Daily Ranking (with Total) ───────────────────────
def adv_daily_table_with_total(adv_map, prev_map, prev_wk_map):
    lst = sorted(adv_map.values(), key=lambda x: x['rev'], reverse=True)
    rows = ''
    total_rev = 0; total_gp = 0; total_conv = 0; total_mp = 0; total_clk = 0
    for i, e in enumerate(lst):
        name = e['name'][:35]
        prev = prev_map.get(e['aid']) if prev_map else None
        pw = prev_wk_map.get(e['aid']) if prev_wk_map else None
        d_str, dc = fmt_pct(e['rev'], prev['rev']) if prev else ('-', 'gray')
        w_str, wc = fmt_pct(e['rev'], pw['rev']) if pw else ('-', 'gray')
        margin = e['gp']/e['rev']*100 if e['rev'] else 0
        total_rev += e['rev']
        total_gp += e['gp']
        total_conv += e['conv']
        total_mp += e['mp']
        total_clk += e['clk']
        rows += (
            f"<tr><td>{i+1}</td>"
            f"<td><strong>{e['aid']}</strong><br><span class='sub'>{name}</span></td>"
            f"<td class='num'>${e['rev']:,.2f}</td>"
            f"<td class='num'>${e['gp']:,.2f}</td>"
            f"<td class='num'>{margin:.1f}%</td>"
            f"<td class='num'>{e['conv']}</td>"
            f"<td class='num'>${e['mp']:,.2f}</td>"
            f"<td class='num {dc}'>{d_str}</td>"
            f"<td class='num {wc}'>{w_str}</td></tr>"
        )
    total_margin = total_gp/total_rev*100 if total_rev else 0
    rows += (
        f"<tr style='background:#fef3c7;font-weight:600;'>"
        f"<td colspan=2>Total ({len(lst)} 广告主)</td>"
        f"<td class='num'>${total_rev:,.2f}</td>"
        f"<td class='num'>${total_gp:,.2f}</td>"
        f"<td class='num'>{total_margin:.1f}%</td>"
        f"<td class='num'>{total_conv}</td>"
        f"<td class='num'>${total_mp:,.2f}</td>"
        f"<td class='num gray'>-</td>"
        f"<td class='num gray'>-</td></tr>"
    )
    return rows

adv_daily_rows = adv_daily_table_with_total(today_adv, yday_adv, lwk_adv)

# ─── Advertiser MTD Table (with Total) ──────────────────────────
def adv_mtd_table_with_total(mtd_map, today_map):
    lst = sorted(mtd_map.values(), key=lambda x: x['rev'], reverse=True)
    rows = ''
    total_rev = 0; total_gp = 0; total_conv = 0; total_mp = 0; total_clk = 0
    for i, e in enumerate(lst):
        today_e = today_map.get(e['aid'])
        margin = e['gp']/e['rev']*100 if e['rev'] > 0 else 0
        epc = e['rev']/e['clk'] if e['clk'] > 0 else 0
        name = e['name'][:35]
        today_rev = today_e['rev'] if today_e else 0
        total_rev += e['rev']
        total_gp += e['gp']
        total_conv += e['conv']
        total_mp += e['mp']
        total_clk += e['clk']
        rows += (
            f"<tr><td>{i+1}</td>"
            f"<td><strong>{e['aid']}</strong><br><span class='sub'>{name}</span></td>"
            f"<td class='num'>${e['rev']:,.2f}</td>"
            f"<td class='num'>${e['gp']:,.2f}</td>"
            f"<td class='num'>{margin:.1f}%</td>"
            f"<td class='num'>{e['conv']}</td>"
            f"<td class='num'>${e['mp']:,.2f}</td>"
            f"<td class='num'>${epc:.4f}</td>"
            f"<td class='num'>${today_rev:,.2f}</td></tr>"
        )
    total_margin = total_gp/total_rev*100 if total_rev else 0
    total_epc = total_rev/total_clk if total_clk else 0
    today_total_rev = sum(
        (today_map.get(e['aid'], {}) or {}).get('rev', 0) for e in lst
    )
    rows += (
        f"<tr style='background:#fef3c7;font-weight:600;'>"
        f"<td colspan=2>Total ({len(lst)} 广告主)</td>"
        f"<td class='num'>${total_rev:,.2f}</td>"
        f"<td class='num'>${total_gp:,.2f}</td>"
        f"<td class='num'>{total_margin:.1f}%</td>"
        f"<td class='num'>{total_conv}</td>"
        f"<td class='num'>${total_mp:,.2f}</td>"
        f"<td class='num'>${total_epc:.4f}</td>"
        f"<td class='num'>${today_total_rev:,.2f}</td></tr>"
    )
    return rows

mtd_rows = adv_mtd_table_with_total(mtd_adv, today_adv)

# ─── Key Metrics for Summary ────────────────────────────────────
rev_t = sf(ts['revenue']); rev_y = sf(ys['revenue']); rev_w = sf(ls['revenue'])
gp_t = sf(ts['gp']); gp_y = sf(ys['gp']); gp_w = sf(ls['gp'])
conv_t = si(ts['conversionCount']); conv_y = si(ys['conversionCount']); conv_w = si(ls['conversionCount'])
mp_t = sf(ts['mediaPayout']); ap_t = sf(ts['affPayout'])
margin_t = gp_t/rev_t*100 if rev_t else 0
margin_y = gp_y/rev_y*100 if rev_y else 0

ext_sorted = sorted(today_ex.values(), key=lambda x: x['rev'], reverse=True)
best_ch = ext_sorted[0] if ext_sorted else None
adv_sorted = sorted(today_adv.values(), key=lambda x: x['rev'], reverse=True)
best_adv = adv_sorted[0] if adv_sorted else None
mtd_sorted = sorted(mtd_adv.values(), key=lambda x: x['rev'], reverse=True)
mtd_best_adv = mtd_sorted[0] if mtd_sorted else None

# ─── Summary Text ───────────────────────────────────────────────
summary_text = (
    f"<p><strong>一、整体表现：</strong></p>"
    f"<p>{main_display} CPL整体 Revenue <strong>${rev_t:,.2f}</strong>，"
    f"GP <strong>${gp_t:,.2f}</strong>（毛利率 {margin_t:.1f}%），"
    f"Conversions <strong>{conv_t:,}</strong>，"
    f"Media Payout <strong>${mp_t:,.2f}</strong>，"
    f"Aff Payout <strong>${ap_t:,.2f}</strong>。</p>"
    f"<p>环比 {yd_display}：Revenue {pct(rev_t, rev_y):+.1f}%，"
    f"GP <strong>{pct(gp_t, gp_y):+.1f}%</strong>"
    f"（毛利率从 {margin_y:.1f}% 升至 {margin_t:.1f}%），"
    f"Conversions {pct(conv_t, conv_y):+.1f}%。</p>"
)
if rev_w > 0:
    summary_text += (
        f"<p>对比上周同日 {lw_display}："
        f"Revenue {pct(rev_t, rev_w):+.1f}%，"
        f"GP {pct(gp_t, gp_w):+.1f}%，"
        f"Conversions {pct(conv_t, conv_w):+.1f}%。</p>"
    )

if best_ch:
    summary_text += (
        f"<p><strong>二、外部渠道表现：</strong></p>"
        f"<p>共 <strong>{len(ext_sorted)}</strong> 个外部渠道，"
        f"Revenue 最高为 <strong>[{best_ch['aid']}] {best_ch['name']}</strong>"
        f"（${best_ch['rev']:,.2f}，GP ${best_ch['gp']:,.2f}）。</p>"
    )

if best_adv:
    summary_text += (
        f"<p><strong>三、广告主表现（当日）：</strong></p>"
        f"<p>共 <strong>{len(adv_sorted)}</strong> 个广告主产生转化。"
        f"Revenue 最高为 <strong>[{best_adv['aid']}] {best_adv['name']}</strong>"
        f"（${best_adv['rev']:,.2f}，GP ${best_adv['gp']:,.2f}）。</p>"
    )

if mtd_best_adv:
    summary_text += (
        f"<p><strong>四、广告主月累计（{mtd_range}）：</strong></p>"
        f"<p>MTD 总 Revenue <strong>${sf(ms['revenue']):,.2f}</strong>，"
        f"GP <strong>${sf(ms['gp']):,.2f}</strong>，"
        f"Conversions <strong>{si(ms['conversionCount']):,}</strong>。"
        f"Top 广告主为 <strong>[{mtd_best_adv['aid']}] {mtd_best_adv['name']}</strong>"
        f"（${mtd_best_adv['rev']:,.2f}）。</p>"
    )

# ─── Dates for output ────────────────────────────────────────────
gen_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
gen_time_cst = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')

# ─── HTML ───────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CPL 日度分析报告 - {MAIN_DATE}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif; background:#f5f7fa; color:#1a1a2e; padding:20px; }}
.container {{ max-width:1200px; margin:0 auto; }}

h1 {{ font-size:22px; margin-bottom:4px; }}
h2 {{ font-size:17px; color:#333; border-bottom:2px solid #4f46e5; padding-bottom:8px; margin:28px 0 14px; }}
.subtitle {{ font-size:13px; color:#888; margin-bottom:20px; }}

.kpi-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:20px; }}
.kpi-card {{ background:#fff; border-radius:10px; padding:14px; box-shadow:0 1px 3px rgba(0,0,0,.08); text-align:center; }}
.kpi-card .kpi-label {{ font-size:11px; color:#888; text-transform:uppercase; letter-spacing:.5px; margin-bottom:4px; }}
.kpi-card .kpi-value {{ font-size:20px; font-weight:700; }}
.kpi-card .kpi-sub {{ font-size:11px; color:#999; margin-top:2px; }}
.kpi-card.revenue .kpi-value {{ color:#4f46e5; }}
.kpi-card.gp .kpi-value {{ color:#059669; }}
.kpi-card.conv .kpi-value {{ color:#d97706; }}
.kpi-card.payout .kpi-value {{ color:#dc2626; }}
.kpi-card.clicks .kpi-value {{ color:#2563eb; }}

.table-wrap {{ overflow-x:auto; background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,.08); padding:12px; margin-bottom:18px; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.data-table th {{ background:#f1f5f9; padding:9px 7px; text-align:left; font-size:11px; text-transform:uppercase; color:#64748b; white-space:nowrap; }}
.data-table td {{ padding:7px; border-bottom:1px solid #f1f5f9; }}
.data-table tr:hover {{ background:#f8fafc; }}
.data-table tr:last-child td {{ border-bottom:none; }}
.num {{ text-align:right !important; font-variant-numeric:tabular-nums; }}
.green {{ color:#16a34a !important; }}
.red {{ color:#dc2626 !important; }}
.gray {{ color:#94a3b8 !important; }}
.sub {{ font-size:11px; color:#94a3b8; }}

.mtd-badge {{ display:inline-block; background:#fef3c7; color:#92400e; font-size:11px; padding:2px 8px; border-radius:4px; margin-left:8px; }}

.offer-section {{ margin-bottom:4px; }}
.offer-header {{ background:#f8fafc; padding:10px 14px; border-radius:8px; cursor:pointer; display:flex; justify-content:space-between; font-size:13px; font-weight:500; }}
.offer-header:hover {{ background:#eef2ff; }}

.summary-box {{ background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,.08); padding:18px; line-height:1.8; font-size:14px; margin-bottom:20px; }}
.summary-box p {{ margin-bottom:8px; }}

.internal-collapse {{ margin-top:10px; }}
.internal-header {{ background:#f8fafc; padding:8px 12px; border-radius:8px; cursor:pointer; font-size:12px; color:#666; display:flex; justify-content:space-between; }}
.internal-body {{ display:none; margin-top:8px; }}

@media (max-width:900px) {{
    .kpi-grid {{ grid-template-columns:repeat(3,1fr); }}
}}
</style>
</head>
<body>
<div class="container">

<h1>CPL 日度分析报告</h1>
<div class="subtitle">数据日期：{main_display}（GMT时区） | 生成时间：{gen_time_cst} CST
<br>外部渠道：ID 白名单共 {len(EXT_IDS)} 个 | 新增含"外放"名字的渠道自动归为外部</div>

<!-- KPI 总览 -->
<div class="kpi-grid">
    <div class="kpi-card revenue"><div class="kpi-label">Revenue</div><div class="kpi-value">${rev_t:,.2f}</div></div>
    <div class="kpi-card gp"><div class="kpi-label">GP</div><div class="kpi-value">${gp_t:,.2f}</div><div class="kpi-sub">毛利率 {margin_t:.1f}%</div></div>
    <div class="kpi-card conv"><div class="kpi-label">Conversions</div><div class="kpi-value">{conv_t:,}</div></div>
    <div class="kpi-card payout"><div class="kpi-label">Media Payout</div><div class="kpi-value">${mp_t:,.2f}</div><div class="kpi-sub">Aff ${ap_t:,.2f}</div></div>
    <div class="kpi-card clicks"><div class="kpi-label">Total Clicks</div><div class="kpi-value">{si(ts['totalClickCount']):,}</div><div class="kpi-sub">EPC ${sf(ts['epc']):.4f} | CR {sf(ts['cr']):.2f}%</div></div>
</div>

<!-- 整体对比表 -->
<h2>一、整体数据对比</h2>
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>指标</th><th>{main_display}</th><th>{yd_display}</th><th>日环比</th><th>{lw_display}</th><th>周环比</th></tr></thead>
        <tbody>{kpi_rows}</tbody>
    </table>
</div>

<!-- 外部渠道排名（无 Revenue/Payout 列） -->
<h2>二、外部渠道排名 <span class="mtd-badge">共 {len(ext_sorted)} 个</span></h2>
<p style="color:#888;font-size:12px;margin-bottom:10px;">按 Revenue 降序 | 日环比 = vs {yd_display} | 周环比 = vs {lw_display}</p>
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>#</th><th>渠道</th><th>GP</th><th>EPC</th><th>CR</th><th>VPN</th><th>Conv</th><th>日环比</th><th>周环比</th></tr></thead>
        <tbody>{chan_rows_v3}</tbody>
    </table>
</div>

<!-- 内部渠道（折叠） -->
<div class="internal-collapse">
    <div class="internal-header" onclick="toggle('internal-channels')">
        <span>内部渠道（{len(today_in)} 个，点击展开）</span>
        <span id="arr-internal-channels" class="arrow">&#9660;</span>
    </div>
    <div id="internal-channels" style="display:none;">
        <div class="table-wrap" style="margin-top:8px;">
            <table class="data-table">
                <thead><tr><th>#</th><th>渠道</th><th>Revenue</th><th>GP</th><th>Conv</th><th>EPC</th></tr></thead>
                <tbody>{internal_rows}</tbody>
            </table>
        </div>
    </div>
</div>

<!-- 每个外部渠道 Top Offers -->
<h2>三、外部渠道 Top Offers（按 Conversions）</h2>
{offer_sections}

<!-- 广告主当日排名 -->
<h2>四、广告主当日排名</h2>
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>#</th><th>广告主</th><th>Revenue</th><th>GP</th><th>毛利率</th><th>Conv</th><th>Media Payout</th><th>日环比</th><th>周环比</th></tr></thead>
        <tbody>{adv_daily_rows}</tbody>
    </table>
</div>

<!-- 广告主月累计 -->
<h2>五、广告主月累计 <span class="mtd-badge">{mtd_range}</span></h2>
<p style="color:#888;font-size:12px;margin-bottom:10px;">
    MTD 总 Revenue <strong>${sf(ms['revenue']):,.2f}</strong> | GP <strong>${sf(ms['gp']):,.2f}</strong> | Conv <strong>{si(ms['conversionCount']):,}</strong> | 日均 <strong>${sf(ms['revenue'])/max(mtd_days,1):,.2f}</strong>
</p>
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>#</th><th>广告主</th><th>MTD Revenue</th><th>MTD GP</th><th>毛利率</th><th>Conv</th><th>MTD Payout</th><th>EPC</th><th>当日 Revenue</th></tr></thead>
        <tbody>{mtd_rows}</tbody>
    </table>
</div>

<!-- 总结 -->
<h2>六、总结</h2>
<div class="summary-box">{summary_text}</div>

</div>

<script>
function toggle(id) {{
    const el = document.getElementById(id);
    const arr = document.getElementById('arr-' + id);
    if (!el || !arr) return;
    if (el.style.display === 'none') {{
        el.style.display = 'block';
        arr.innerHTML = '&#9650;';
    }} else {{
        el.style.display = 'none';
        arr.innerHTML = '&#9660;';
    }}
}}
</script>
</body>
</html>"""

out_path = f'{ROOT}/report.html'
with open(out_path, 'w') as f:
    f.write(html)

print(f"Report saved to {out_path}")
print(f"File size: {os.path.getsize(out_path):,} bytes")
print(f"External channels: {len(ext_sorted)}")
print(f"Advertisers (today): {len(adv_sorted)}")
print(f"Advertisers (MTD): {len(mtd_sorted)}")
