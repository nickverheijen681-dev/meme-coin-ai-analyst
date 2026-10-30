
import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime, timezone

# ==================================
# MEME COIN AI ANALYST
# ==================================

st.set_page_config(
    page_title="Meme Coin AI Analyst",
    page_icon="🚀",
    layout="wide"
)

API = "https://api.dexscreener.com"

SCAN_INTERVAL = 120
MAX_AGE_DAYS = 7

CHAINS = ["solana", "ethereum"]

st.title("🚀 Meme Coin AI Analyst")
st.caption("Live scanner | Solana & Ethereum | Geen automatische transacties")

def get_json(url):
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return None


def get_new_tokens():
    tokens = []

    endpoints = [
        "/token-profiles/latest/v1",
        "/token-boosts/latest/v1"
    ]

    for endpoint in endpoints:
        data = get_json(API + endpoint)

        if isinstance(data, list):
            tokens.extend(data)

    unique = {}

    for token in tokens:
        chain = token.get("chainId")
        address = token.get("tokenAddress")

        if chain in CHAINS and address:
            unique[(chain, address)] = token

    return list(unique.values())


def analyse_pair(pair):
    liquidity = (pair.get("liquidity") or {}).get("usd") or 0
    volume = (pair.get("volume") or {}).get("h24") or 0
    price_change = (pair.get("priceChange") or {}).get("h24") or 0

    txns = pair.get("txns") or {}
    h1 = txns.get("h1") or {}

    buys = h1.get("buys") or 0
    sells = h1.get("sells") or 0
    total = buys + sells

    created = pair.get("pairCreatedAt")

    if not created:
        return None

    age_days = (
        datetime.now(timezone.utc).timestamp()
        - created / 1000
    ) / 86400

    if age_days < 0 or age_days > MAX_AGE_DAYS:
        return None

    score = 0

    # Liquiditeit
    if liquidity >= 50000:
        score += 25
    elif liquidity >= 20000:
        score += 18
    elif liquidity >= 5000:
        score += 10

    # Handelsvolume
    if volume >= 100000:
        score += 20
    elif volume >= 25000:
        score += 15
    elif volume >= 5000:
        score += 8

    # Koop- en verkoopactiviteit
    if total >= 100:
        score += 20
    elif total >= 30:
        score += 12
    elif total >= 10:
        score += 5

    # Koopdruk
    if total > 0 and buys / total >= 0.60:
        score += 15
    elif total > 0 and buys / total >= 0.50:
        score += 8

    # Positieve koersontwikkeling
    if 0 < price_change < 100:
        score += 10
    elif price_change >= 100:
        score += 5

    # Extra risicocontrole
    risks = []

    if liquidity < 5000:
        risks.append("Lage liquiditeit")

    if total < 10:
        risks.append("Weinig transacties")

    if price_change > 100:
        risks.append("Sterke koersstijging")

    if sells > buys:
        risks.append("Meer verkopen dan kopen")

    if not risks:
        risks.append("Geen directe waarschuwing")

    return {
        "Naam": (pair.get("baseToken") or {}).get("name", "Unknown"),
        "Symbool": (pair.get("baseToken") or {}).get("symbol", "?"),
        "Chain": pair.get("chainId", ""),
        "Leeftijd (dagen)": round(age_days, 2),
        "Prijs ($)": pair.get("priceUsd", "0"),
        "Liquiditeit ($)": round(liquidity),
        "Volume 24u ($)": round(volume),
        "Koers 24u (%)": round(price_change, 2),
        "Koop 1u": buys,
        "Verkoop 1u": sells,
        "Score": min(score, 100),
        "Risico": ", ".join(risks),
        "Link": pair.get("url", "")
    }


def scan_coins():
    tokens = get_new_tokens()
    addresses = {}

    for token in tokens:
        chain = token["chainId"]
        addresses.setdefault(chain, []).append(token["tokenAddress"])

    results = []

    for chain, token_addresses in addresses.items():
        # Maximaal 30 adressen per API-aanroep
        for start in range(0, len(token_addresses), 30):
            batch = token_addresses[start:start + 30]
            address_string = ",".join(batch)

            data = get_json(
                f"{API}/latest/dex/tokens/{address_string}"
            )

            if not data:
                continue

            for pair in data.get("pairs") or []:
                if pair.get("chainId") != chain:
                    continue

                result = analyse_pair(pair)

                if result:
                    results.append(result)

            time.sleep(0.3)

    # Dubbele coins verwijderen
    unique = {}

    for coin in results:
        key = (coin["Chain"], coin["Symbool"])
        if key not in unique or coin["Score"] > unique[key]["Score"]:
            unique[key] = coin

    return sorted(
        unique.values(),
        key=lambda x: x["Score"],
        reverse=True
    )


if "coins" not in st.session_state:
    st.session_state.coins = []

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

if st.button("🔄 Scan nu", type="primary"):
    with st.spinner("Memecoins analyseren..."):
        st.session_state.coins = scan_coins()
        st.session_state.last_scan = datetime.now().strftime(
            "%H:%M:%S"
        )

coins = st.session_state.coins

if st.session_state.last_scan:
    st.caption("Laatste scan: " + st.session_state.last_scan)

if coins:
    df = pd.DataFrame(coins)

    st.subheader("📊 Scanresultaten")

    col1, col2, col3 = st.columns(3)

    col1.metric("Coins gevonden", len(df))
    col2.metric("Hoogste score", int(df["Score"].max()))
    col3.metric("Coins boven 70", int((df["Score"] >= 70).sum()))

    st.dataframe(
        df.drop(columns=["Link"]),
        use_container_width=True,
        hide_index=True
    )

    st.subheader("🔎 Coin-details")

    for coin in coins[:10]:
        with st.expander(
            f'{coin["Symbool"]} | Score {coin["Score"]}/100'
        ):
            st.write("Naam:", coin["Naam"])
            st.write("Netwerk:", coin["Chain"])
            st.write("Liquiditeit: $", coin["Liquiditeit ($)"])
            st.write("Volume 24u: $", coin["Volume 24u ($)"])
            st.write("Risico:", coin["Risico"])

            st.markdown(f'[Bekijk op DexScreener]({coin["Link"]})')

else:
    st.info("Nog geen scan uitgevoerd. Druk op Scan nu.")

st.divider()

st.caption(
    "Score is een experimentele indicator, geen voorspelling. "
    "Token- en liquiditeitsrisico's kunnen niet volledig worden vastgesteld."
)

# Automatisch verversen
time.sleep(0.1)
st.markdown(
    f'<meta http-equiv="refresh" content="{SCAN_INTERVAL}">',
    unsafe_allow_html=True
)
