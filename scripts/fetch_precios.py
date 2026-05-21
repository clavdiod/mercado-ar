#!/usr/bin/env python3
import json, time, logging, ssl, urllib.request
from datetime import datetime, date, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR     = Path(__file__).parent.parent / "docs" / "data" / "historico"
SUMMARY_FILE = Path(__file__).parent.parent / "docs" / "data" / "resumen.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = "U24YTBW2AQC8Q7EE"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

TICKERS = {
    "acciones": ["GGAL.BA","YPF.BA","BMA.BA","PAMP.BA","TXAR.BA","ALUA.BA","CRES.BA",
                 "SUPV.BA","CEPU.BA","COME.BA","TECO2.BA","LOMA.BA","MIRG.BA","TGSU2.BA",
                 "VALO.BA","METR.BA","HARG.BA","BYMA.BA","CVH.BA","EDN.BA","TGNO4.BA",
                 "AGRO.BA","BBAR.BA","MOLI.BA","RICH.BA"],
    "cedears":  ["AAPL.BA","MSFT.BA","GOOGL.BA","AMZN.BA","TSLA.BA","META.BA","NVDA.BA",
                 "JPM.BA","KO.BA","DIS.BA","WMT.BA","MELI.BA","GLOB.BA","DESP.BA",
                 "NFLX.BA","BIDU.BA","GOLD.BA","ARCO.BA","BIOX.BA","CAAP.BA"],
    "bonos":    ["AL29.BA","AL30.BA","AL35.BA","AL41.BA","GD29.BA","GD30.BA",
                 "GD35.BA","GD38.BA","GD41.BA","GD46.BA","AE38.BA"],
    "letras":   ["S31E5.BA","S28F5.BA","S31M5.BA","T17O5.BA","T31O5.BA"],
}

def fetch_av(ticker):
    """Alpha Vantage GLOBAL_QUOTE"""
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={API_KEY}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as r:
            d = json.loads(r.read().decode("utf-8"))
        q = d.get("Global Quote", {})
        price = q.get("05. price")
        change = q.get("10. change percent", "").replace("%","")
        vol = q.get("06. volume")
        name = ticker.replace(".BA","")
        if not price or price == "0.0000": return None
        return {
            "ticker":    ticker.replace(".BA",""),
            "nombre":    name,
            "cierre":    round(float(price), 2),
            "variacion": round(float(change), 2) if change else None,
            "volumen":   float(vol) if vol else None,
        }
    except Exception as e:
        log.warning(f"  {ticker}: {e}")
        return None

def last_bday():
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def main():
    date_str = last_bday().isoformat()
    out_file = DATA_DIR / f"{date_str}.json"
    log.info(f"=== {date_str} ===")
    todos = []

    for cat, tickers in TICKERS.items():
        log.info(f"→ {cat} ({len(tickers)} tickers)")
        for t in tickers:
            item = fetch_av(t)
            if item:
                item["categoria"] = cat
                todos.append(item)
                log.info(f"  ✓ {t}: {item['cierre']}")
            else:
                log.info(f"  ✗ {t}")
            time.sleep(12)  # Alpha Vantage free = 5 llamadas/min

    log.info(f"Total: {len(todos)} instrumentos")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"fecha": date_str, "total": len(todos), "instrumentos": todos},
                  f, ensure_ascii=False, separators=(",",":"))

    fechas = sorted(p.stem for p in DATA_DIR.glob("*.json"))
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "ultima_fecha":   fechas[-1] if fechas else None,
            "fechas":         fechas,
            "total_fechas":   len(fechas),
            "actualizado_en": datetime.now().isoformat() + "Z"
        }, f, ensure_ascii=False, separators=(",",":"))

    log.info(f"Guardado en docs/data/ — {len(fechas)} fechas")

if __name__ == "__main__":
    main()
