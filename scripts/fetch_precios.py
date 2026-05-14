#!/usr/bin/env python3
"""
fetch_precios.py - Mercado Argentino
Usa BYMA Data (open.bymadata.com.ar) como fuente principal + CAFCI para FCI.
"""

import json, time, logging, urllib.request, urllib.error
from datetime import datetime, date, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR     = Path(__file__).parent.parent / "data" / "historico"
SUMMARY_FILE = Path(__file__).parent.parent / "data" / "resumen.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9",
    "Referer":         "https://open.bymadata.com.ar/",
    "Origin":          "https://open.bymadata.com.ar",
}

def fetch_json(url, retries=3, delay=8):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.warning(f"  intento {attempt+1}/{retries} fallido ({e})")
            if attempt < retries - 1:
                time.sleep(delay)
    return None

BYMA_URLS = {
    "acciones": "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/equities",
    "cedears":  "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/cedears",
    "bonos":    "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/bonds",
    "letras":   "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/lebacs",
    "on":       "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/corporate-bonds",
}
CAFCI_URL = "https://api.cafci.org.ar/fondo?estado=1"

def clean(v):
    try:    return float(str(v).replace(",",".").strip())
    except: return None

def parse_byma(data, cat):
    if not data: return []
    rows = data if isinstance(data, list) else data.get("data", data.get("content", []))
    out  = []
    for item in (rows or []):
        ticker = (item.get("symbol") or item.get("descripcionAbreviada") or "").strip().upper()
        nombre = (item.get("description") or item.get("descripcion") or ticker).strip()
        cierre = clean(item.get("trade") or item.get("settlementPrice") or item.get("closingPrice") or item.get("last") or item.get("price"))
        var    = clean(item.get("changePercent") or item.get("imVar") or item.get("variation"))
        vol    = clean(item.get("volume") or item.get("totalNominalVolume") or item.get("quantityBuy"))
        if not ticker or cierre is None: continue
        out.append({"ticker": ticker, "nombre": nombre, "categoria": cat,
                    "cierre": round(cierre,4),
                    "variacion": round(var,4) if var is not None else None,
                    "volumen": vol})
    return out

def parse_cafci(data):
    if not data: return []
    rows = data.get("data", data) if isinstance(data, dict) else data
    out  = []
    for f in (rows or []):
        cuota = clean(f.get("ultimoCuotaparte") or f.get("cuotaparte"))
        if cuota is None: continue
        out.append({"ticker": str(f.get("id","")),
                    "nombre": (f.get("nombre") or f.get("name") or "").strip(),
                    "categoria": "fci",
                    "cierre": round(cuota,6),
                    "variacion": clean(f.get("variacion")),
                    "volumen": clean(f.get("patrimonio"))})
    return out

def last_bday():
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5: d -= timedelta(days=1)
    return d

def main():
    date_str = last_bday().isoformat()
    out_file = DATA_DIR / f"{date_str}.json"
    log.info(f"=== Fetch mercado AR · {date_str} ===")
    todos = []

    for cat, url in BYMA_URLS.items():
        log.info(f"→ {cat} ...")
        raw   = fetch_json(url)
        items = parse_byma(raw, cat)
        log.info(f"  {'✓' if items else '✗'} {len(items)} instrumentos")
        todos.extend(items)
        time.sleep(3)

    log.info("→ fci (CAFCI)...")
    raw   = fetch_json(CAFCI_URL)
    items = parse_cafci(raw)
    log.info(f"  {'✓' if items else '✗'} {len(items)} fondos")
    todos.extend(items)

    # deduplicar
    seen, uniq = set(), []
    for i in todos:
        k = (i["ticker"], i["categoria"])
        if k not in seen: seen.add(k); uniq.append(i)
    todos = uniq

    log.info(f"=== Total: {len(todos)} instrumentos ===")
    payload = {"fecha": date_str, "generado_en": datetime.utcnow().isoformat()+"Z",
               "total": len(todos), "instrumentos": todos}
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",",":"))
    log.info(f"Guardado → {out_file}")

    fechas = sorted(p.stem for p in DATA_DIR.glob("*.json"))
    resumen = {"ultima_fecha": fechas[-1] if fechas else None, "fechas": fechas,
               "total_fechas": len(fechas), "actualizado_en": datetime.utcnow().isoformat()+"Z"}
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, separators=(",",":"))
    log.info(f"Resumen actualizado: {len(fechas)} fechas")

    if not todos:
        log.error("Sin datos de ninguna fuente — revisar APIs")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
