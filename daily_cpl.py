#!/usr/bin/env python3
"""
CPL Daily Report - Cloud Edition
Runs on GitHub Actions. Auto-dates, fetches, aggregates, outputs JSON.
"""
import requests, json, time, os, sys
from datetime import datetime, timedelta, timezone

BASE = 'https://mng.touchpointcorp.com'
COLS = ("offerId,offerName,affiliateId,affiliateName,advertiserId,advertiserName,dataTime,"
        "totalClickCount,successClickCount,uniqueClickCount,failedClickCount,"
        "mediaClickCount,conversionCount,revenue,mediaPayout,affPayout,"
        "cpa,affConversionCount,mediaImpressionCount,landingPageViewCount,"
        "lpCr,ctr,cpc,cr,affCr,gp,pnlRatio,realCpa,uniqueEpc,vpnRate,successClickRate,epc")

ROOT = os.environ.get('GITHUB_WORKSPACE', os.path.dirname(os.path.abspath(__file__)))

# ── Credentials from env vars (set in GitHub Secrets) ──
USER = os.environ.get('CPL_USER', 'freda@touchpointcorp.com')
PASS = os.environ.get('CPL_PASS', 'Freda6666')
AUTH_ROUTE = os.environ.get('CPL_AUTH', 'FAXX7UPNAE7O4BTRM2AS6UN4CMBIL5JC')
JSESSIONID = os.environ.get('CPL_JSESSIONID', '63f86c47-724c-4d93-829b-312c4dfb0919')

# ── Dates (GMT) ──
utc = datetime.now(timezone.utc)
today_gmt = utc.date()
yd = today_gmt - timedelta(days=1)          # analysis date
db = yd - timedelta(days=1)                 # day-before
lw = yd - timedelta(days=7)                 # last-week
m1 = yd.replace(day=1)                      # MTD start

MAIN = yd.strftime('%Y-%m-%d')
DB = db.strftime('%Y-%m-%d')
LW = lw.strftime('%Y-%m-%d')
M1 = m1.strftime('%Y-%m-%d')
ME = yd.strftime('%Y-%m-%d')

weekday_names = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
MAIN_DISPLAY = f"{yd.strftime('%m/%d')} ({weekday_names[yd.weekday()]})"

print(f"=== CPL Daily Report (Cloud) ===")
print(f"  Analysis: {MAIN} ({MAIN_DISPLAY})")
print(f"  Day Before: {DB} | Last Week: {LW}")
print(f"  MTD: {M1} ~ {ME}")

# ── Auth ──
s = requests.Session()
s.headers.update({
    'accept': 'application/json, text/plain, */*',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/148.0.0.0 Safari/537.36',
    'dnt': '1',
    'referer': BASE + '/',
})

# Use cached JSESSIONID
s.cookies.set('JSESSIONID', JSESSIONID)

# Try to refresh login
try:
    r = s.get(f'{BASE}/api/debug/login/auth/{AUTH_ROUTE}')
    jr = r.json()
    ac = None
    if isinstance(jr, dict):
        res = jr.get('result')
        if isinstance(res, str): ac = res
    if ac:
        r2 = s.post(f'{BASE}/api/authLogin', json={
            'username': USER, 'password': PASS, 'authCode': ac, 'platform': 'web'
        })
        if r2.json().get('success'):
            new_jsid = s.cookies.get('JSESSIONID', '')
            print(f"  Login refreshed: {new_jsid[:16]}...")
            # Update env for potential reuse
            if new_jsid:
                with open(os.environ.get('GITHUB_ENV', '/dev/null'), 'a') as f:
                    f.write(f'CPL_JSESSIONID={new_jsid}\n')
        else:
            print(f"  Login API failed (using cached): {r2.json().get('message')}")
    else:
        print("  No auth code, using cached session")
except Exception as e:
    print(f"  Login attempt failed (using cached): {e}")

# ── Fetch ──
def fetch(sd, ed):
    items = []; p = 1; su = {}
    while True:
        r = s.get(f'{BASE}/api/report/cpl/common', params={
            'columns': COLS, 'fromDate': sd, 'endDate': ed,
            'sorting': 'dataTime', 'timezone': '+00:00',
            'page': p, 'pageSize': 1000, 't': str(int(time.time()*1000))
        }, timeout=60)
        d = r.json()
        if not d.get('success'):
            print(f"  ERR p{p}: {d}")
            break
        res = d['result']; deets = res.get('details', [])
        su = res.get('summary', {}); items.extend(deets)
        print(f"  p{p}: +{len(deets)} | total {len(items)}")
        if len(deets) < 1000: break
        p += 1; time.sleep(0.3)
    return {'summary': su, 'details': items}

data = {}
for label, d in [('today', MAIN), ('yesterday', DB), ('last_week', LW)]:
    print(f"Fetch {label}: {d}")
    data[label] = fetch(d, d)

print(f"Fetch MTD: {M1} ~ {ME}")
mtd = fetch(M1, ME)

with open(f'{ROOT}/cpl_raw_data.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open(f'{ROOT}/cpl_mtd_raw.json', 'w') as f:
    json.dump(mtd, f, ensure_ascii=False, indent=2)
print("Raw data saved.")

# ── Aggregate ──
def sf(v, d=0):
    try: return float(v) if v else d
    except: return d
def si(v, d=0):
    try: return int(v) if v else d
    except: return d
def pct(c, pr):
    return round((c-pr)/pr*100, 1) if pr else None

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
        a = si(r.get('affiliateId'))
        if not a: continue
        nm = r.get('affiliateName', ''); ct = classify(nm)
        rv = sf(r.get('revenue')); gp = sf(r.get('gp'))
        cv = si(r.get('conversionCount')); cl = si(r.get('totalClickCount'))
        mp = sf(r.get('mediaPayout')); ap = sf(r.get('affPayout'))
        uc = si(r.get('uniqueClickCount'))
        oi = str(r.get('offerId', '')); on = r.get('offerName', '')
        if a not in m:
            m[a] = {'aid': a, 'name': nm, 'cat': ct,
                    'rev': 0, 'gp': 0, 'conv': 0, 'clk': 0,
                    'mp': 0, 'ap': 0, 'uc': 0, 'offers': {}}
        e = m[a]
        e['rev'] += rv; e['gp'] += gp; e['conv'] += cv; e['clk'] += cl
        e['mp'] += mp; e['ap'] += ap; e['uc'] += uc
        if oi not in e['offers']:
            e['offers'][oi] = {'name': on, 'rev': 0, 'gp': 0, 'conv': 0, 'ap': 0}
        e['offers'][oi]['rev'] += rv; e['offers'][oi]['gp'] += gp
        e['offers'][oi]['conv'] += cv; e['offers'][oi]['ap'] += ap
    for v in m.values():
        v['epc'] = v['rev'] / v['clk'] if v['clk'] else 0
        v['cr'] = v['conv'] / v['clk'] * 100 if v['clk'] else 0
        v['vpn'] = v['uc'] / v['clk'] * 100 if v['clk'] else 0
    return m

def agg_adv(details):
    m = {}
    for r in details:
        a = si(r.get('advertiserId'))
        if not a: continue
        rv = sf(r.get('revenue')); gp = sf(r.get('gp'))
        cv = si(r.get('conversionCount')); mp = sf(r.get('mediaPayout'))
        ap = sf(r.get('affPayout')); cl = si(r.get('totalClickCount'))
        if a not in m:
            m[a] = {'aid': a, 'name': r.get('advertiserName', ''),
                    'rev': 0, 'gp': 0, 'conv': 0, 'mp': 0, 'ap': 0, 'clk': 0}
        e = m[a]
        e['rev'] += rv; e['gp'] += gp; e['conv'] += cv; e['mp'] += mp; e['ap'] += ap; e['clk'] += cl
    return {k: v for k, v in m.items() if v['conv'] > 0}

ta = agg_aff(data['today']['details'])
ya = agg_aff(data['yesterday']['details'])
la = agg_aff(data['last_week']['details'])
tex = {k: v for k, v in ta.items() if v['cat'] == '外部'}
tav = agg_adv(data['today']['details'])
yav = agg_adv(data['yesterday']['details'])
mav = agg_adv(mtd['details'])

ts = data['today']['summary']; ys = data['yesterday']['summary']
ls = data['last_week']['summary']; ms = mtd['summary']

ext_s = sorted(tex.values(), key=lambda x: x['rev'], reverse=True)
adv_s = sorted(tav.values(), key=lambda x: x['rev'], reverse=True)
mtd_s = sorted(mav.values(), key=lambda x: x['rev'], reverse=True)

summary = {
    'main_date': MAIN,
    'main_display': MAIN_DISPLAY,
    'revenue': round(sf(ts['revenue']), 2),
    'gp': round(sf(ts['gp']), 2),
    'margin': round(sf(ts['gp']) / sf(ts['revenue']) * 100, 1) if sf(ts['revenue']) else 0,
    'conversions': si(ts['conversionCount']),
    'media_payout': round(sf(ts['mediaPayout']), 2),
    'epc': round(sf(ts['epc']), 4),
    'cr': round(sf(ts['cr']), 2),
    'vpn_rate': round(sf(ts['vpnRate']), 2),
    'dod_rev': pct(sf(ts['revenue']), sf(ys['revenue'])),
    'dod_gp': pct(sf(ts['gp']), sf(ys['gp'])),
    'dod_conv': pct(si(ts['conversionCount']), si(ys['conversionCount'])),
    'wow_rev': pct(sf(ts['revenue']), sf(ls['revenue'])),
    'wow_gp': pct(sf(ts['gp']), sf(ls['gp'])),
    'ext_top10': [{'rank': i+1, 'id': e['aid'], 'name': e['name'],
                    'rev': round(e['rev'], 2), 'gp': round(e['gp'], 2),
                    'conv': e['conv'], 'epc': round(e['epc'], 4),
                    'cr': round(e['cr'], 2)} for i, e in enumerate(ext_s[:10])],
    'adv_top10': [{'rank': i+1, 'id': e['aid'], 'name': e['name'],
                    'rev': round(e['rev'], 2), 'gp': round(e['gp'], 2),
                    'conv': e['conv'],
                    'margin': round(e['gp'] / e['rev'] * 100, 1) if e['rev'] else 0}
                  for i, e in enumerate(adv_s[:10])],
    'mtd_rev': round(sf(ms['revenue']), 2),
    'mtd_gp': round(sf(ms['gp']), 2),
    'mtd_conv': si(ms['conversionCount']),
    'mtd_days': (yd - m1).days + 1,
    'mtd_daily_avg': round(sf(ms['revenue']) / ((yd - m1).days + 1), 2),
    'mtd_top_adv': {'id': mtd_s[0]['aid'], 'name': mtd_s[0]['name'],
                    'rev': round(mtd_s[0]['rev'], 2)} if mtd_s else None,
    'ext_count': len(ext_s),
    'total_clicks': si(ts['totalClickCount']),
}

with open(f'{ROOT}/cpl_summary.json', 'w') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"  CPL Summary — {MAIN}")
print(f"  Rev: ${summary['revenue']:,.2f} | GP: ${summary['gp']:,.2f} ({summary['margin']}%)")
print(f"  Conv: {summary['conversions']:,}")
print(f"  DoD: Rev {summary['dod_rev']}% | GP {summary['dod_gp']}%")
print(f"  WoW: Rev {summary['wow_rev']}% | GP {summary['wow_gp']}%")
print(f"{'='*60}")
print("Done. cpl_summary.json ready.")
