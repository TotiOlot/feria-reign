#!/usr/bin/env python3
"""Genera agenda.json (raíz del repo) a partir de los eventos de Outlook.

Uso: python3 agenda/build_agenda.py eventos.json [eventos2.json ...]
Cada fichero es la lista de eventos tal como la devuelve outlook_calendar_search
(start/end en {dateTime,timeZone}). Escribe agenda.json solo si cambia el contenido.
"""
import json, re, sys, unicodedata, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "agenda/config.json").read_text(encoding="utf-8"))
MAPA = json.loads((ROOT / "agenda/mapa.json").read_text(encoding="utf-8"))["reglas"]
TZ = ZoneInfo(CFG["zona_horaria"])
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
STAND = re.compile(r"\(?\b(?:Hall\s?|H)(\d{1,2})\s*[/\- ]?\s*([A-Z])\s*-?\s*(\d{1,4}(?:-\d+)?)\b\)?", re.I)

def norm(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()

def to_local(t):
    raw = t["dateTime"].split(".")[0]
    tzname = t.get("timeZone") or "UTC"
    d = dt.datetime.fromisoformat(raw)
    d = d.replace(tzinfo=ZoneInfo("UTC") if tzname.upper() in ("UTC", "Z") else ZoneInfo(tzname))
    return d.astimezone(TZ)

def short_loc(loc):
    if not loc: return ""
    loc = loc.split("(")[0].split(",")[0].strip()
    m = re.match(r"^(.+?)\s+\1$", loc)
    return m.group(1) if m else loc

def regla(ev):
    texto = norm(ev.get("subject", "") + " " + (ev.get("organizerName") or ""))
    for r in MAPA:
        if any(norm(k) in texto for k in r["buscar"]):
            return r
    return None

def item(ev):
    s, e = to_local(ev["start"]), to_local(ev["end"])
    subject = (ev.get("subject") or "").strip()
    loc = ev.get("location") or ""
    teams = "teams" in norm(loc)
    partes = []
    if norm(subject).startswith("vuelo"):
        vuelo = re.search(r"\b([A-Z0-9]{2}\s?\d{3,4})\b", subject)
        titulo = re.sub(r"\s*-\s*[A-Z0-9]{2}\s?\d{3,4}\b", "", subject).replace("MEDICA", "").replace("()", "")
        titulo = re.sub(r"\s+", " ", titulo).strip(" -")
        if vuelo: partes.append(vuelo.group(1))
        if loc: partes.append("Salida " + short_loc(loc))
        partes.append("Llega " + e.strftime("%H:%M"))
        return s, {"time": s.strftime("%H:%M"), "subj": "✈️ " + titulo, "sub": " · ".join(partes), "clickable": False}, None
    m = STAND.search(subject) or STAND.search(loc)
    stand = f"H{m.group(1)}/{m.group(2).upper()}{m.group(3)}" if m else None
    limpio = STAND.sub("", subject)
    pendiente = "pending" in norm(limpio) or "pendiente" in norm(limpio)
    limpio = re.sub(r"\((?:location )?pending\)|\(pendiente\)|\(\s*\)", "", limpio, flags=re.I)
    trozos = [t.strip() for t in re.split(r"\s+[-–]\s+", limpio) if t.strip(" -–")]
    r = regla(ev)
    titulo = (r or {}).get("titulo") or (trozos[0] if trozos else subject)
    gente = [t for t in trozos[1:] if norm(t) not in norm(titulo)]
    if stand: partes.append("Stand " + stand)
    if gente: partes.append(", ".join(gente))
    if teams: partes.append("Reunión Teams")
    elif loc and not (m and STAND.search(loc)) and "medica" not in norm(loc): partes.append(short_loc(loc))
    elif loc and "reign" in norm(loc): partes.append("En stand REIGN")
    if pendiente: partes.append("Ubicación pendiente")
    if (ev.get("showAs") or "").lower() == "tentative": partes.append("Provisional")
    dur = int((e - s).total_seconds() // 60)
    if dur >= 90: partes.append(f"{s:%H:%M}–{e:%H:%M}")
    it = {"time": s.strftime("%H:%M"), "subj": titulo.strip(), "sub": " · ".join(partes) or "Reunión en feria", "clickable": False}
    key = None
    if r and r.get("clientKey"):
        it.update(clickable=True, clientKey=r["clientKey"], tab=r.get("tab", "clientes"))
        key = r["clientKey"]
    return s, it, key

def main(paths):
    evs = []
    for p in paths:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        evs += data if isinstance(data, list) else data.get("events", [])
    desde = dt.date.fromisoformat(CFG["desde"]); hasta = dt.date.fromisoformat(CFG["hasta"])
    vistos, dias = set(), {}
    for ev in evs:
        if not isinstance(ev, dict) or "start" not in ev: continue
        if ev.get("isAllDay") or ev.get("isCancelled"): continue
        if ev.get("id") in vistos: continue
        vistos.add(ev.get("id"))
        s, it, key = item(ev)
        if not (desde <= s.date() <= hasta): continue
        lista = dias.setdefault(s.date(), [])
        dup = next((x for x in lista if key and x[1].get("clientKey") == key and x[0] == s), None)
        if dup:
            if len(it["sub"]) > len(dup[1]["sub"]): lista[lista.index(dup)] = (s, it)
            continue
        lista.append((s, it))
    fechas = sorted(dias)
    out_days = []
    for i, f in enumerate(fechas):
        extremo = i in (0, len(fechas) - 1)
        out_days.append({
            "day": f"{DIAS[f.weekday()]} {f.day} {MESES[f.month-1]}",
            "icon": "✈️" if extremo else "🌟",
            "color": "gold" if i % 2 == 0 else "blue",
            "items": [it for _, it in sorted(dias[f], key=lambda x: x[0])],
        })
    dest = ROOT / "agenda.json"
    nuevo = {"feria": CFG["feria"], "days": out_days}
    previo = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else {}
    if {k: previo.get(k) for k in ("feria", "days")} == nuevo:
        print("SIN_CAMBIOS"); return
    nuevo["updated"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    dest.write_text(json.dumps(nuevo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ACTUALIZADO", sum(len(d["items"]) for d in out_days), "eventos")

if __name__ == "__main__":
    main(sys.argv[1:])
