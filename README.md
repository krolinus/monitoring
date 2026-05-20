# Shop Login Monitor

Automatisches Monitoring von Shop-Logins via GitHub Actions.  
Alle 15 Minuten werden beide Shops geprüft. Bei einem Fehler wird automatisch ein GitHub Issue erstellt; sobald der Login wieder funktioniert, wird das Issue geschlossen.

## Überwachte Shops

| Name | URL | Erfolgs-Ziel |
|---|---|---|
| CHARISMA | vierlande-food.de/account/login | /b2bsalesrepresentative |
| FRISCH+FROST | frisch-frost.de/account/login | /b2bsalesrepresentative |

---

## Setup-Anleitung

### 1. Repository anlegen

```bash
git clone https://github.com/krolinus/monitoring.git
cd monitoring
```

### 2. Secrets hinterlegen

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Beschreibung |
|---|---|
| `VIERLANDE_EMAIL` | E-Mail für vierlande-food.de |
| `VIERLANDE_PASSWORD` | Passwort für vierlande-food.de |
| `FRISCHFROST_EMAIL` | E-Mail für frisch-frost.de |
| `FRISCHFROST_PASSWORD` | Passwort für frisch-frost.de |

`GITHUB_TOKEN` ist automatisch vorhanden – kein eigenes Secret nötig.

### 3. Label anlegen

**Issues → Labels → New label**

- Name: `shop-monitor`, Farbe: `#e11d48`
- Das Label `bug` muss ebenfalls vorhanden sein (standardmäßig vorhanden)

### 4. Workflow aktivieren

**Actions → "I understand my workflows, go ahead and enable them"**

Zum manuellen Test: **Actions → Shop Login Monitor → Run workflow**

---

## Dateistruktur

```
monitors/
├── base_monitor.py          # Basisklasse mit Login-Logik und GitHub-API
├── vierlande_monitor.py     # CHARISMA-Monitor
└── frischfrost_monitor.py   # FRISCH+FROST-Monitor
run_all.py                   # Startet alle Monitore, gibt Zusammenfassung aus
.github/workflows/monitor.yml
requirements.txt
```

## Beispiel-Ausgabe

```
================================
   MONITORING ZUSAMMENFASSUNG
================================
✅ CHARISMA           – OK
🔴 FRISCH+FROST       – FEHLER
================================
```

## Neuen Monitor hinzufügen

1. Neue Datei `monitors/meinshop_monitor.py` anlegen, `BaseMonitor` erben
2. `name`, `login_url`, `success_path`, `log_file` setzen
3. `email` und `password` aus Env-Variablen in `__init__` lesen
4. Klasse in `run_all.py` in die `MONITORS`-Liste eintragen
5. Secrets in GitHub hinterlegen

## Lokale Ausführung

```bash
pip install -r requirements.txt

export VIERLANDE_EMAIL="..." VIERLANDE_PASSWORD="..."
export FRISCHFROST_EMAIL="..." FRISCHFROST_PASSWORD="..."
export GITHUB_TOKEN="..."   # optional, für Issue-Erstellung

python run_all.py
```
