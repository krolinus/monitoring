# Shop Login Monitor

Automatisches Monitoring des Shop-Logins via GitHub Actions.  
Das Script meldet sich alle 15 Minuten bei `https://www.vierlande-food.de/account/login` an und protokolliert das Ergebnis. Bei einem Fehler wird automatisch ein GitHub Issue erstellt; sobald der Login wieder funktioniert, wird das Issue geschlossen.

---

## Setup-Anleitung

### 1. Repository anlegen

```bash
git clone https://github.com/<dein-username>/monitoring.git
cd monitoring
```

Oder erstelle ein neues Repository direkt auf GitHub und lade diesen Code hoch.

### 2. Secrets hinterlegen

Öffne dein Repository auf GitHub und navigiere zu:

**Settings → Secrets and variables → Actions → New repository secret**

Lege folgende Secrets an:

| Name            | Wert                        |
|-----------------|-----------------------------|
| `SHOP_EMAIL`    | Deine Shop-E-Mail-Adresse   |
| `SHOP_PASSWORD` | Dein Shop-Passwort          |

> Die Zugangsdaten werden ausschließlich als verschlüsselte GitHub Secrets gespeichert und niemals im Code oder in Logs angezeigt.

### 3. Workflow aktivieren

1. Navigiere im Repository zu **Actions**.
2. Falls GitHub Actions noch nicht aktiv ist, klicke auf **"I understand my workflows, go ahead and enable them"**.
3. Der Workflow `Shop Login Monitor` läuft automatisch alle 15 Minuten (Cron: `*/15 * * * *`).
4. Zum manuellen Testen: **Actions → Shop Login Monitor → Run workflow**.

---

## Funktionsweise

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub Actions (alle 15 min)                                   │
│                                                                 │
│  1. GET  /account/login   → CSRF-Token + Formularfelder lesen   │
│  2. POST /account/login   → Credentials absenden               │
│  3. GET  /account         → Erreichbarkeit nach Login prüfen   │
│                                                                 │
│  Erfolg → Log + Artefakt; offene Issues werden geschlossen      │
│  Fehler → Log + Artefakt + GitHub Issue erstellt               │
└─────────────────────────────────────────────────────────────────┘
```

### Log-Format (`shop_monitor.log`)

```
2026-05-20T10:00:01Z INFO Starting login check for https://...
2026-05-20T10:00:03Z INFO timestamp=... status=SUCCESS http_code=200 message=Login successful – account page accessible.
```

### Artefakte

Jede Ausführung speichert `shop_monitor.log` als GitHub-Artefakt mit einer Aufbewahrungsdauer von **30 Tagen** unter:  
**Actions → [Workflow-Run] → Artifacts → shop-monitor-log-\<run-id\>**

---

## Lokale Ausführung (zum Testen)

```bash
pip install -r requirements.txt

export SHOP_EMAIL="deine@email.de"
export SHOP_PASSWORD="deinspasswort"

python monitor.py
echo "Exit-Code: $?"
cat shop_monitor.log
```

---

## Issue-Labels

Der Workflow verwendet das Label `shop-monitor`. Lege es einmalig an:

**Issues → Labels → New label** → Name: `shop-monitor`, Farbe: `#e11d48`

Das Label `bug` muss standardmäßig bereits vorhanden sein.
