#!/usr/bin/env python3
"""
fetch_precios.py
Descarga precios de cierre del mercado argentino y los guarda en data/historico/
Fuentes: Bolsar API (acciones, cedears, bonos, ON, letras) + CAFCI (FCI)
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "historico"
SUMMARY_FILE = Path(__file__).parent.parent / "data" / "resumen.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MercadoAR/1.0)",
    "Accept": "application/json",
}

BOLSAR_ENDPOINTS = {
    "acciones": "https://api.bolsar.info/mercado/acciones/panel/general",
    "cedears":  "https://api.bolsar.info/mercado/cedears/panel/general",
    "bonos":    "https://api.bolsar.info/mercado/bonos/panel/bonos-soberanos-en-pesos",
    "on":       "https://api.bolsar.info/mercado/obligaciones-negociables/panel/general",
    "letras":   "https://api.bolsar.info/mercado/letras/panel/general",
}

CAFCI_URL = "https://api.cafci.org.ar/fondo?estado=1"


def fetch_json(url, retries=3, delay=5):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning(f"Intento {attempt+1}/{retries} fallido para {url}: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return None


def parse_bolsar(data, categoria):
    items = data if isinstance(data, list) else data.get("data", data.get("items", []))
    result = []
    for item in items:
        ticker  = item.get("simbolo") or item.get("ticker") or item.get("symbol") or ""
        nombre  = item.get("descripcion") or item.get("nombre") or item.get("name") or ticker
        cierre  = item.get("ultimoPrecio") or item.get("ultimo") or item.get("close") or item.get("precioUltimo")
        var     = item.get("variacion") or item.get("variacionPorcentual") or item.get("changePercent")
        volumen = item.get("volumen") or item.get("volume") or item.get("cantidadNominal")

        if cierre is None:
            continue
        try:
            cierre = float(cierre)
        except (ValueError, TypeError):
            continue

        result.append({
            "ticker":    ticker.upper(),
            "nombre":    nombre,
            "categoria": categoria,
            "cierre":    round(cierre, 4),
            "variacion": round(float(var), 4) if var is not None else None,
            "volumen":   float(volumen) if volumen is not None else None,
        })
    return result


def parse_cafci(data):
    fondos = data.get("data", data) if isinstance(data, dict) else data
    result = []
    for f in fondos:
        nombre = f.get("nombre") or f.get("name") or ""
        fid    = str(f.get("id") or "")
        cuota  = f.get("ultimoCuotaparte") or f.get("cuotaparte")
        var    = f.get("variacion")
        patrim = f.get("patrimonio")

        if cuota is None:
            continue
        try:
            cuota = float(cuota)
        except (ValueError, TypeError):
            continue

        result.append({
            "ticker":    fid,
            "nombre":    nombre,
            "categoria": "fci",
            "cierre":    round(cuota, 6),
            "variacion": round(float(var), 4) if var is not None else None,
            "volumen":   float(patrim) if patrim is not None else None,
        })
    return result


def last_business_day():
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:  # sab=5, dom=6
        d -= timedelta(days=1)
    return d


def main():
    target_date = last_business_day()
    date_str = target_date.isoformat()   # "2025-05-13"
    out_file = DATA_DIR / f"{date_str}.json"

    # Evitar re-fetch si ya existe
    if out_file.exists():
        log.info(f"Ya existe {out_file}, saltando fetch.")
    else:
        log.info(f"Descargando precios para {date_str}...")
        todos = []

        for cat, url in BOLSAR_ENDPOINTS.items():
            log.info(f"  → {cat} ...")
            raw = fetch_json(url)
            if raw is None:
                log.warning(f"  ✗ Sin datos para {cat}")
                continue
            items = parse_bolsar(raw, cat)
            log.info(f"  ✓ {len(items)} instrumentos en {cat}")
            todos.extend(items)

        log.info("  → fci ...")
        raw_fci = fetch_json(CAFCI_URL)
        if raw_fci:
            fci_items = parse_cafci(raw_fci)
            log.info(f"  ✓ {len(fci_items)} fondos en fci")
            todos.extend(fci_items)
        else:
            log.warning("  ✗ Sin datos FCI")

        payload = {
            "fecha":        date_str,
            "generado_en":  datetime.utcnow().isoformat() + "Z",
            "total":        len(todos),
            "instrumentos": todos,
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        log.info(f"Guardado: {out_file} ({len(todos)} instrumentos)")

    # Actualizar resumen (índice de fechas disponibles)
    fechas = sorted([p.stem for p in DATA_DIR.glob("*.json")])
    resumen = {
        "ultima_fecha":    fechas[-1] if fechas else None,
        "fechas":          fechas,
        "total_fechas":    len(fechas),
        "actualizado_en":  datetime.utcnow().isoformat() + "Z",
    }
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, separators=(",", ":"))
    log.info(f"Resumen actualizado: {len(fechas)} fechas disponibles")


if __name__ == "__main__":
    main()
