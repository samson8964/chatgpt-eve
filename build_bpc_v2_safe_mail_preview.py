from pathlib import Path
import html
import pandas as pd

SOURCE = Path('results/latest/ranked_opportunities_v2.csv')
OUT = Path('results/latest/bpc_v2_safe_mail_preview.html')
TOP = 10


def fmt_isk(v):
    try:
        x = float(v)
    except Exception:
        return '-'
    if abs(x) >= 1e9:
        return f'{x/1e9:.2f}B'
    if abs(x) >= 1e6:
        return f'{x/1e6:.1f}M'
    if abs(x) >= 1e3:
        return f'{x/1e3:.1f}K'
    return f'{x:,.0f}'


def select_safe(df):
    if df.empty:
        return df.copy()
    required = ['v2_status','v2_live_net_profit','v2_live_net_roi','v2_stress_net_profit','v2_orderbook_complete']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f'missing required columns: {missing}')
    safe = df[df['v2_status'].astype(str).eq('SAFE')].copy()
    safe = safe[pd.to_numeric(safe['v2_live_net_profit'], errors='coerce').fillna(0) >= 20_000_000]
    safe = safe[pd.to_numeric(safe['v2_live_net_roi'], errors='coerce').fillna(0) >= 0.10]
    safe = safe[pd.to_numeric(safe['v2_stress_net_profit'], errors='coerce').fillna(0) > 0]
    safe = safe[safe['v2_orderbook_complete'].astype(bool)]
    safe.sort_values(['v2_score','v2_live_net_profit'], ascending=[False,False], inplace=True)
    return safe.head(TOP)


def render(df):
    picked = select_safe(df)
    if picked.empty:
        return '<b>BPC V2 SAFE</b><br>本轮没有通过严格实时复核的制造机会。'
    parts = [f'<b>BPC V2 SAFE · {len(picked)}个</b><br>仅展示实时复核、压力测试和订单深度均通过的制造机会。<br><br>']
    for i, (_, r) in enumerate(picked.iterrows(), 1):
        name = html.escape(str(r.get('products','Unknown BPC')))
        cid = int(float(r.get('contract_id',0)))
        roi = float(r.get('v2_live_net_roi',0) or 0) * 100
        fill = float(r.get('v2_est_fill_days',0) or 0)
        parts.append(f'<b>{i}. [{html.escape(str(r.get("v2_grade","")))}] {name}</b><br>')
        parts.append(f'实时净利 {fmt_isk(r.get("v2_live_net_profit",0))} · ROI {roi:.1f}% · 评分 {float(r.get("v2_score",0) or 0):.1f}<br>')
        parts.append(f'压力测试利润 {fmt_isk(r.get("v2_stress_net_profit",0))} · 预计清算 {fill:.2f}天<br>')
        parts.append(f'成品VWAP {fmt_isk(r.get("v2_product_vwap",0))} · 成品滑点 {float(r.get("v2_product_slippage",0) or 0)*100:.2f}% · 材料最大滑点 {float(r.get("v2_material_max_slippage",0) or 0)*100:.2f}%<br>')
        parts.append(f'<url=contract:0//{cid}><b>打开合同</b></url><br><br>')
    return ''.join(parts)


def main():
    if not SOURCE.exists():
        raise RuntimeError(f'missing input: {SOURCE}')
    df = pd.read_csv(SOURCE)
    body = render(df)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body, encoding='utf-8')
    print(f'BPC V2 SAFE mail preview -> {OUT}')


if __name__ == '__main__':
    main()
