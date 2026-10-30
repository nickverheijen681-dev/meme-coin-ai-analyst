import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

st.set_page_config(page_title='Meme Coin AI Analyst', page_icon='🚀', layout='wide')
API = 'https://api.dexscreener.com'
SCAN_INTERVAL = 120
MAX_AGE_DAYS = 7
CHAINS = ['solana', 'ethereum']

st.title('🚀 Meme Coin AI Analyst')
st.caption('Top 10 groeisignalen | Solana & Ethereum | Geen automatische transacties')

@st.cache_data(ttl=SCAN_INTERVAL, show_spinner=False)
def get_json(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def get_new_tokens():
    tokens = {}
    for endpoint in ['/token-profiles/latest/v1', '/token-boosts/latest/v1']:
        data = get_json(API + endpoint)
        if isinstance(data, list):
            for token in data:
                chain, address = token.get('chainId'), token.get('tokenAddress')
                if chain in CHAINS and address:
                    tokens[(chain, address)] = token
    return list(tokens.values())


def analyse_pair(pair):
    try:
        created = pair.get('pairCreatedAt')
        if not created:
            return None
        age = (datetime.now(timezone.utc).timestamp() - float(created) / 1000) / 86400
        if not 0 <= age <= MAX_AGE_DAYS:
            return None
        liquidity = float((pair.get('liquidity') or {}).get('usd') or 0)
        volume = float((pair.get('volume') or {}).get('h24') or 0)
        change24 = float((pair.get('priceChange') or {}).get('h24') or 0)
        change1 = float((pair.get('priceChange') or {}).get('h1') or 0)
        h1 = (pair.get('txns') or {}).get('h1') or {}
        buys, sells = int(h1.get('buys') or 0), int(h1.get('sells') or 0)
        total = buys + sells
        ratio = buys / total if total else 0
        turnover = volume / liquidity if liquidity else 0
        reasons, risks = [], []
        score = 0
        if liquidity >= 50000:
            score += 20; reasons.append('Liquiditeit boven $50.000')
        elif liquidity >= 20000:
            score += 14
        elif liquidity >= 5000:
            score += 7
        else:
            risks.append('Lage liquiditeit')
        if volume >= 100000:
            score += 15; reasons.append('Hoog 24u-volume')
        elif volume >= 25000:
            score += 10
        elif volume >= 5000:
            score += 5
        if total >= 100:
            score += 15; reasons.append('Veel transacties in 1 uur')
        elif total >= 30:
            score += 9
        elif total >= 10:
            score += 4
        else:
            risks.append('Weinig transacties')
        if total >= 20 and ratio >= .60:
            score += 15; reasons.append('Koopdruk boven 60%')
        elif total >= 20 and ratio >= .50:
            score += 8
        if 2 <= change1 <= 30:
            score += 15; reasons.append('Positief 1u-momentum')
        elif 0 < change1 < 2:
            score += 5
        elif change1 > 50:
            risks.append('Extreme 1u-stijging')
        if 0 < change24 <= 100:
            score += 10
        elif change24 > 100:
            risks.append('Sterke 24u-stijging')
        if .5 <= turnover <= 10:
            score += 10; reasons.append('Actief volume t.o.v. liquiditeit')
        elif turnover > 20:
            risks.append('Uitzonderlijk hoog volume t.o.v. liquiditeit')
        if sells > buys and total >= 10:
            risks.append('Meer verkopen dan kopen')
        if liquidity < 10000:
            risks.append('Verhoogd slippagerisico')
        score = max(0, min(100, score - min(30, 10 * len(risks))))
        base = pair.get('baseToken') or {}
        return {
            'Naam': base.get('name') or 'Onbekend',
            'Symbool': base.get('symbol') or '?',
            'Netwerk': pair.get('chainId') or '',
            'Leeftijd (dagen)': round(age, 2),
            'Liquiditeit ($)': round(liquidity),
            'Volume 24u ($)': round(volume),
            'Koers 1u (%)': round(change1, 2),
            'Koers 24u (%)': round(change24, 2),
            'Kopen 1u': buys,
            'Verkopen 1u': sells,
            'Groeiscore': score,
            'Risico': 'Hoog' if len(risks) >= 2 else ('Let op' if risks else 'Niet vastgesteld'),
            'Waarom': ', '.join(reasons) if reasons else 'Onvoldoende positieve signalen',
            'Waarschuwingen': ', '.join(risks) if risks else 'Geen signalen binnen deze beperkte controles',
            'Adres': base.get('address') or '',
            'Link': pair.get('url') or ''
        }
    except (TypeError, ValueError, OverflowError):
        return None


def scan_coins():
    tokens = get_new_tokens()
    grouped = {}
    for token in tokens:
        grouped.setdefault(token['chainId'], []).append(token['tokenAddress'])
    unique = {}
    for chain, addresses in grouped.items():
        for i in range(0, len(addresses), 30):
            data = get_json(f"{API}/latest/dex/tokens/{','.join(addresses[i:i+30])}")
            for pair in (data or {}).get('pairs') or []:
                if pair.get('chainId') != chain:
                    continue
                coin = analyse_pair(pair)
                if not coin:
                    continue
                key = (chain, coin['Adres'] or (pair.get('pairAddress') or ''))
                if key not in unique or coin['Groeiscore'] > unique[key]['Groeiscore']:
                    unique[key] = coin
    return sorted(unique.values(), key=lambda c: c['Groeiscore'], reverse=True)


@st.fragment(run_every=f'{SCAN_INTERVAL}s')
def dashboard():
    if st.button('🔄 Scan nu', type='primary'):
        get_json.clear()
    with st.spinner('Nieuwe munten analyseren...'):
        coins = scan_coins()
    st.caption('Laatste scan: ' + datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
    if not coins:
        st.warning('Geen munten gevonden in de huidige DexScreener-selectie. Probeer later opnieuw.')
        return
    df = pd.DataFrame(coins)
    c1, c2, c3 = st.columns(3)
    c1.metric('Munten gevonden', len(df))
    c2.metric('Hoogste groeiscore', int(df['Groeiscore'].max()))
    c3.metric('Scores ≥ 70', int((df['Groeiscore'] >= 70).sum()))
    st.subheader('🏆 Top 10 groeisignalen')
    cols = ['Symbool', 'Netwerk', 'Groeiscore', 'Risico', 'Koers 1u (%)', 'Koers 24u (%)', 'Liquiditeit ($)', 'Volume 24u ($)']
    st.dataframe(df.head(10)[cols], use_container_width=True, hide_index=True)
    st.subheader('🔎 Waarom staan ze bovenaan?')
    for coin in coins[:10]:
        with st.expander(f"{coin['Symbool']} ({coin['Netwerk']}) — {coin['Groeiscore']}/100"):
            st.write('Positieve signalen:', coin['Waarom'])
            st.write('Risico-indicatie:', coin['Risico'])
            st.write('Waarschuwingen:', coin['Waarschuwingen'])
            st.write('Tokenadres:', coin['Adres'])
            if coin['Link']:
                st.link_button('Bekijk op DexScreener', coin['Link'])
    st.subheader('📊 Alle gevonden munten')
    st.dataframe(df[cols + ['Waarom', 'Waarschuwingen']], use_container_width=True, hide_index=True)


dashboard()
st.divider()
st.caption('Experimentele heuristische score, geen AI-voorspelling of koopadvies. DexScreener-profielen/boosts vormen geen volledige marktdekking. Tokencontracten, eigenaarschap, honeypots en liquiditeitslocks worden niet geverifieerd. Automatische scans werken zolang de Streamlit-sessie actief is; hosting kan slapen.')
