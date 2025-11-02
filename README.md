# Olis Dashboard – Lokale Installation und Betrieb

![Dashboard UI](dashboard.jpg?raw=true)

## Überblick
Dieses Projekt stellt ein vollständiges Monitoring-Dashboard für Heimnetzwerke bereit. Es kombiniert mehrere Docker-Container (Prometheus, Grafana, Exporter) und stellt eine vorkonfigurierte Bedienoberfläche zur Verfügung. Diese Anleitung erklärt Schritt für Schritt, wie Sie die Umgebung unter Windows und Linux einrichten, wie Sie Zugänge nutzen und wie Sie IP-Adressen sowie Anmeldedaten anpassen.

## Voraussetzungen
1. **Hardware**: 64-Bit-Rechner mit mindestens 4 GB RAM und 10 GB freiem Speicher.
2. **Betriebssystem**:
    - Windows 10/11 (Empfehlung: mit aktiviertem WSL 2).
    - Linux-Distribution mit Bash (z. B. Ubuntu, Debian, Fedora).
3. **Software**:
    - [Docker Desktop](https://www.docker.com/products/docker-desktop/) für Windows (Docker Compose ist enthalten).
    - Docker Engine ≥ 24 und Docker Compose-Plugin ≥ 2.20 für Linux. Installation z. B. über `sudo apt install docker.io docker-compose-plugin`.
4. **Benutzerrechte**:
    - Windows: PowerShell mit Administratorrechten, Docker Desktop muss laufen.
    - Linux: Nutzer muss `docker`-Befehle ausführen können (ggf. `sudo usermod -aG docker <BENUTZER>` und abmelden/anmelden).

## Projekt klonen
```bash
# Windows (PowerShell) oder Linux (Bash)
git clone https://github.com/PhilippElhaus/OlisDashboard.git
cd OlisDashboard
```

## Initiale Konfiguration verstehen
- `.env`: Enthält die Variable `GRAFANA_ADMIN_PASSWORD`. Standardwert ist `admin`. Ändern Sie den Wert vor dem ersten Start, wenn Sie ein eigenes Passwort wünschen.
- `fritz/fritz.yml`: Hinterlegt die Fritz!Box-Anmeldedaten. Passen Sie `hostname`, `username` und `password` an Ihr Gerät an.
- `prometheus/prometheus.yml`: Enthält die vorkonfigurierten Scrape-Ziele (z. B. `fritz:18000`, `blackbox:18001`). Änderungen an Zielen erfolgen nach dem ersten Start in `config/prometheus/prometheus.yml`.

> **Hinweis**: Die Skripte `bootstrap` legen beim ersten Lauf einen lokalen `config/`-Ordner an. Ab dann bearbeiten Sie nur noch Dateien in `config/`, nicht in den Ursprungsordnern.

## Windows: Start mit `bootstrap.ps1`
1. Docker Desktop starten und sicherstellen, dass der Status `Running` angezeigt wird.
2. PowerShell als Administrator öffnen und in das Projektverzeichnis wechseln.
3. Skript ausführen:
    ```powershell
    ./bootstrap.ps1
    ```
    - Schritt 1: Baut das Initialisierungs-Image (`init`).
    - Schritt 2: Erstellt einmalig den Ordner `config/` mit Prometheus- und Grafana-Dateien.
    - Schritt 3: Startet alle Dienste im Hintergrund.
4. Der Abschluss zeigt `docker compose ps`. Alle Services sollten den Status `running` haben.

## Linux: Start mit `bootstrap.sh`
1. Terminal öffnen und ins Projektverzeichnis wechseln.
2. Skript ausführbar machen (nur beim ersten Mal erforderlich):
    ```bash
    chmod +x bootstrap.sh cleanup.sh
    ```
3. Skript ausführen:
    ```bash
    ./bootstrap.sh
    ```
    - Baut und startet denselben Ablauf wie die PowerShell-Variante.
4. Prüfen Sie die Container:
    ```bash
    docker compose ps
    ```
    Alle Einträge sollten `Up` anzeigen.

## Dienste und Ports
| Service       | Zweck                                  | Port lokal | Container-Port |
|---------------|----------------------------------------|------------|----------------|
| `fritz`       | Fritz!Box Prometheus Exporter          | 18000      | 18000          |
| `blackbox`    | ICMP/HTTP-Checks via Blackbox Exporter | 18001      | 18001          |
| `ip`          | Öffentliche/Netzwerk-IP Exporter       | 18002      | 18002          |
| `prometheus`  | Zeitreihendatenbank                    | 18003      | 18003          |
| `grafana`     | Dashboard-Oberfläche                   | 18004      | 18004          |

Grafana erreichen Sie nach dem Start über `http://localhost:18004` (oder die IP Ihres Docker-Hosts, falls nicht lokal).

## Erstanmeldung in Grafana
1. Öffnen Sie `http://localhost:18004` im Browser.
2. Anmeldung mit:
    - Benutzer: `admin`
    - Passwort: Wert aus `.env` (`admin`, falls nicht geändert).
3. Nach der Anmeldung über „Passwort ändern“ sofort ein eigenes Passwort setzen.
4. Alle vorkonfigurierten Dashboards finden Sie unter **Dashboards → Browse**.
5. Änderungen an Dashboards können direkt im Browser vorgenommen und als Kopie gespeichert werden. Standard-Dashboards sind schreibgeschützt; speichern Sie angepasste Varianten unter neuem Namen.

## Konfiguration anpassen
Nach dem ersten erfolgreichen Start befinden sich die aktiven Konfigurationen in `config/`.

### Fritz!Box-Ziel anpassen
1. Datei `config/prometheus/prometheus.yml` öffnen.
2. Abschnitt `job_name: 'fritz'` suchen.
3. Falls der Container-Name anders lautet (z. B. mehrere Fritz!Boxen), fügen Sie weitere Ziele hinzu:
    ```yaml
    - job_name: 'fritz'
      static_configs:
          - targets: ['fritz:18000']
          - targets: ['fritz_neu:18000']
    ```
4. Die tatsächliche Fritz!Box-IP konfigurieren Sie direkt in `fritz/fritz.yml`, denn diese Datei wird in den Container eingebunden. Beispiel:
    ```yaml
    devices:
        - name: FritzBoxWohnung
          hostname: 192.168.178.1
          username: meinbenutzer
          password: geheim
    ```
    - `hostname`: IP-Adresse oder Hostname Ihrer Fritz!Box (z. B. `192.168.178.1` oder `fritz.box`).
    - `username`/`password`: Ein Benutzerkonto, das in der Fritz!Box für den Zugriff auf Statistiken berechtigt ist.
5. Datei speichern und Stack neu laden:
    ```bash
    docker compose up -d fritz
    docker compose restart prometheus
    ```

### Weitere IPs für Blackbox-Checks
1. Datei `config/prometheus/prometheus.yml`.
2. Abschnitt `job_name: 'blackbox_icmp'` erweitern, um zusätzliche Ziele (z. B. andere Router, Switches) zu überwachen:
    ```yaml
    static_configs:
        - targets:
            - 192.168.178.1
            - 1.1.1.1
            - 8.8.8.8
    ```
3. Speichern und Prometheus neu laden:
    ```bash
    docker compose exec prometheus kill -HUP 1
    ```

### Grafana-Dashboards bearbeiten
1. Änderungen im Browser vornehmen und per „Save As…“ sichern.
2. Exportieren Sie angepasste Dashboards als JSON und legen Sie sie unter `config/grafana/provisioning/dashboards/` ab, um sie bei Neustarts automatisch zu laden.

## Wartung und Neustart
- Status prüfen: `docker compose ps`.
- Logs anzeigen: `docker compose logs -f <service>`.
- Stack neu starten: `docker compose restart` oder `docker compose down && docker compose up -d`.

## Aufräumen mit `cleanup`
### Windows
```powershell
./cleanup.ps1
```
- Stoppt und entfernt Container, lokale Volumes und Images.
- Löscht den Ordner `config/`.
- Führt optional `docker volume/image/network prune` aus.

### Linux
```bash
./cleanup.sh
```
- Identischer Funktionsumfang wie unter Windows.

> **Achtung**: Nach dem Cleanup ist die Konfiguration gelöscht. Beim nächsten Start wird sie durch `bootstrap` neu erzeugt.

## Fehlerbehebung
| Problem | Ursache | Lösung |
|---------|---------|--------|
| `docker: command not found` | Docker/Compose nicht installiert | Voraussetzungen prüfen und installieren |
| Container bleiben im Status `Exit` | Fehlende Berechtigungen oder Ports blockiert | Docker Desktop neu starten / Ports freigeben |
| Fritz!Box-Daten werden nicht angezeigt | Falsche IP oder Zugangsdaten | `fritz/fritz.yml` korrigieren, `docker compose restart fritz` |
| Grafana meldet falsches Passwort | `.env`-Passwort geändert? | Neues Passwort in `.env` setzen, `docker compose up -d grafana` |

## Nächste Schritte
- Nach erfolgreichem Setup regelmäßige Backups des Ordners `config/` anlegen.
- Eigene Dashboards erstellen und bei Bedarf weitere Exporter in `docker-compose.yml` ergänzen.
