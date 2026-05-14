#!/usr/bin/env python3
import json, time, logging, ssl, urllib.request
from datetime import datetime, date, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR     = Path(__file__).parent.parent / "docs" / "data" / "historico"
SUMMARY_FILE = Path(__file__).parent.parent / "docs" / "data" / "resumen.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9",
    "Referer": "https://mercados.ambito.com/",
    "Origin":  "https://mercados.ambito.com",
}

URLS = {
    "acciones": "https://mercados.ambito.com//lider/sinIntegracion/detalle/paneles",
    "cedears":  "https://mercados.ambito.com//cedears/sinIntegracion/detalle/paneles",
    "bonos":    "https://mercados.ambito.com//bonos/sinIntegracion/detalle/paneles",
    "on":       "https://mercados.ambito.com//obligaciones/sinIntegracion/detalle/paneles",
    "letras":   "https://mercados.ambito.com//letras/sinIntegracion/detalle/paneles",
}

def fetch(url, retries=3, delay=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            log.warning(f"  intento {i+1}/{retries}: {e}")
            if i < retries-1: time.sleep(delay)
    return None

def clean(v):
    if v is None: return None
    try: return float(str(v).replace(",",".").replace("%","").strip())
    except: return None

def parse(data, cat):
    if not data: return []
    rows = data if isinstance(data, list) else data.get("data", data.get("resultado", []))
    out = []
    for item in (rows or []):
        if isinstance(item, dict):
            ticker = (item.get("simbolo") or item.get("symbol") or "").strip().upper()
            nombre = (item.get("nombre") or item.get("descripcion") or ticker).strip()
            cierre = clean(item.get("ultimo") or item.get("cierre"))
            var    = clean(item.get("variacion"))
            vol    = clean(item.get("volumen"))
        elif isinstance(item, list) and len(item) >= 3:
            ticker = str(item[0]).strip().upper()
            nombre = str(item[1]).strip()
            cierre = clean(item[2])
            var    = clean(item[3]) if len(item) > 3 else None
            vol    = clean(item[4]) if len(item) > 4 else None
        else:
            continue
        if not ticker or cierre is None: continue
        out.append({"ticker": ticker, "nombre": nombre, "categoria": cat,
                    "cierre": round(cierre,4),
                    "variacion": round(var,4) if var is not None else None,
                    "volumen": vol})
    return out

def last_bday():
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5: d -= timedelta(days=1)
    return d

def main():
    date_str = last_bday().isoformat()
    out_file = DATA_DIR / f"{date_str}.json"
    log.info(f"=== {date_str} ===")
    todos = []

    for cat, url in URLS.items():
        log.info(f"→ {cat}")
        raw = fetch(url)
        items = parse(raw, cat)
        log.info(f"  {'✓' if items else '✗'} {len(items)}")
        if raw and not items: log.info(f"  muestra: {str(raw)[:200]}")
        todos.extend(items)
        time.sleep(2)

    log.info(f"→ fci")
    raw = fetch("https://api.cafci.org.ar/fondo?estado=1")
    if raw:
        rows = raw.get("data", raw) if isinstance(raw, dict) else raw
        for f in (rows or []):
            c = clean(f.get("ultimoCuotaparte") or f.get("cuotaparte"))
            if c is None: continue
            todos.append({"ticker": str(f.get("id","")),
                          "nombre": (f.get("nombre") or "").strip(),
                          "categoria": "fci", "cierre": round(c,6),
                          "variacion": clean(f.get("variacion")),
                          "volumen": clean(f.get("patrimonio"))})

    seen, uniq = set(), []
    for i in todos:
        k=(i["ticker"],i["categoria"])
        if k not in seen: seen.add(k); uniq.append(i)
    todos = uniq

    log.info(f"Total: {len(todos)} instrumentos")
    with open(out_file,"w",encoding="utf-8") as f:
        json.dump({"fecha":date_str,"total":len(todos),"instrumentos":todos},f,ensure_ascii=False,separators=(",",":"))

    fechas = sorted(p.stem for p in DATA_DIR.glob("*.json"))
    with open(SUMMARY_FILE,"w",encoding="utf-8") as f:
        json.dump({"ultima_fecha":fechas[-1] if fechas else None,"fechas":fechas,
                   "total_fechas":len(fechas),"actualizado_en":datetime.now().isoformat()+"Z"},
                  f,ensure_ascii=False,separators=(",",":"))
    log.info(f"Guardado en docs/data/ — {len(fechas)} fechas")

if __name__ == "__main__":
    main()
