# Raspberry Pi Wi-Fi Setup Portal

Prototipo reale per Raspberry Pi 5 che espone un hotspot temporaneo con portale web locale per configurare il collegamento Wi-Fi del dispositivo, inclusi i casi base `WPA2/WPA3 Personal` e `802.1X`.

## Documentazione

- [Installazione rapida](INSTALL.md)
- [Manuale utente Markdown](docs/manuale-utente.md)
- [Manuale utente PDF](docs/manuale-utente-raspberry-wifi-portal.pdf)

## Quick Start

Per i dettagli completi vedi [INSTALL.md](INSTALL.md).

### Installazione guidata da repository GitHub

Sul Raspberry:

```bash
sudo apt-get update
sudo apt-get install -y git
cd /tmp
git clone https://github.com/andreakys/raspberry-wifi-portal.git
cd raspberry-wifi-portal
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh --interactive
```

Per un'installazione non interattiva:

```bash
sudo ./scripts/install.sh --ssid Pi-Setup --password 'ChangeMe123!' --profile balanced
```

### Bootstrap quasi one-line da GitHub

Se vuoi un flusso ancora piu' semplice, puoi pubblicare anche `scripts/bootstrap_from_github.sh` e usarlo cosi':

```bash
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced
```

### Dopo l'installazione

1. collega il telefono a `Pi-Setup`
2. apri `http://192.168.4.1`
3. inserisci i dati della rete finale
4. scegli un profilo recovery `stable`, `balanced` o `unstable` se necessario

## Funzioni principali

- hotspot temporaneo per onboarding senza cavo Ethernet
- portale web locale da smartphone o tablet
- separazione opzionale tra interfaccia hotspot e interfaccia Wi-Fi client
- supporto `WPA2/WPA3 Personal`
- supporto base `802.1X` con `PEAP`, `TTLS`, `TLS`
- visualizzazione degli indirizzi IPv4 correnti di Wi-Fi e LAN
- configurazione IPv4 DHCP/statico per interfacce non usate dall'hotspot attivo
- recovery automatico dell'hotspot dopo boot fallito o perdita prolungata rete
- installazione da archivio o da repository GitHub
- profili pronti per reti stabili o instabili

## Obiettivo

Quando il Raspberry Pi non ha ancora una connessione valida:

1. attiva un hotspot temporaneo `Pi-Setup`
2. espone una pagina web locale
3. riceve i parametri della rete aziendale
4. salva la configurazione tramite `NetworkManager`
5. tenta la connessione alla rete aziendale
6. spegne l'hotspot se la connessione riesce

## Struttura file

```text
raspberry-wifi-portal/
|-- .gitignore
|-- INSTALL.md
|-- app.py
|-- config.py
|-- deploy/
|   |-- portal.env.example
|   `-- profiles/
|       |-- balanced.env
|       |-- stable.env
|       `-- unstable.env
|-- requirements.txt
|-- services/
|   |-- __init__.py
|   `-- network_manager.py
|-- static/
|   `-- styles.css
|-- systemd/
|   `-- raspberry-wifi-portal.service
|-- templates/
|   |-- index.html
|   `-- status.html
`-- scripts/
    |-- apply_recovery_profile.sh
    |-- bootstrap_from_github.sh
    |-- install.sh
    |-- package_release.sh
    `-- start.sh
```

## Componenti

- `app.py`
  Avvia Flask, espone il form HTML e richiama il service layer per scansione Wi-Fi, hotspot e provisioning della rete.

- `config.py`
  Centralizza la configurazione da variabili d'ambiente: interfaccia Wi-Fi, SSID hotspot, password hotspot, porta HTTP e timeout.

- `services/network_manager.py`
  Incapsula tutte le chiamate a `nmcli`:
  - scansione delle reti
  - creazione e avvio hotspot
  - creazione connessioni WPA-PSK
  - creazione connessioni `802.1X` `PEAP`, `TTLS` e `TLS`
  - lettura dello stato IPv4 delle interfacce
  - configurazione IPv4 DHCP/statico tramite `NetworkManager`
  - verifica stato e connettivita'

- `templates/index.html`
  Pagina principale con form di configurazione.

- `templates/status.html`
  Pagina di esito dopo il tentativo di connessione.

- `static/styles.css`
  Stili del portale.

- `systemd/raspberry-wifi-portal.service`
  Esempio di unita' `systemd` per eseguire il portale automaticamente al boot.

- `scripts/install.sh`
  Script di installazione sul Raspberry Pi:
  - installa dipendenze di sistema
  - copia il progetto in `/opt` usando uno staging temporaneo, quindi puo' essere rilanciato anche da `/opt/raspberry-wifi-portal`
  - crea una virtual environment Python dedicata
  - crea `/etc/raspberry-wifi-portal/portal.env` se non esiste
  - permette installazione guidata con `--interactive`
  - permette installazione non interattiva con `--ssid`, `--password`, `--port` e `--profile`
  - installa la service unit
  - abilita il servizio

- `scripts/package_release.sh`
  Crea un archivio `.tar.gz` pronto da copiare sul Raspberry.

- `deploy/portal.env.example`
  File modello per i parametri installativi del portale.

- `deploy/profiles/*.env`
  Profili gia' pronti per il comportamento di recovery hotspot.

- `scripts/apply_recovery_profile.sh`
  Applica solo i parametri di recovery al file `/etc/raspberry-wifi-portal/portal.env` senza toccare SSID o password.

- `scripts/bootstrap_from_github.sh`
  Script di bootstrap per installare direttamente da un repository GitHub.

- `scripts/start.sh`
  Avvio manuale con variabili d'ambiente predefinite.

## Flusso operativo

### 1. Boot

Il servizio parte come `root`, verifica lo stato del Wi-Fi e attiva l'hotspot se non esiste gia' una connessione funzionante.

### 2. Accesso da smartphone

Lo smartphone si collega all'SSID `Pi-Setup`, poi apre:

```text
http://192.168.4.1
```

### 3. Configurazione

La pagina consente tre modalita':

- `Open`
- `WPA2/WPA3 Personal`
- `WPA2/WPA3 Enterprise (802.1X)`

Per `802.1X` supporta questi profili base:

- `PEAP`
- `TTLS`
- `TLS`

### 4. Provisioning

Il backend crea una nuova connessione `NetworkManager`, restituisce subito una pagina di attesa e poi prova ad attivare la nuova rete in background. Questo evita che lo smartphone perda il feedback visivo nel momento in cui il Raspberry disattiva l'hotspot.

### 5. Esito

- Se la connessione riesce, il Raspberry disattiva l'hotspot.
- Se fallisce, l'hotspot resta disponibile e l'utente puo' ritentare.

## Variabili d'ambiente

| Variabile | Default | Significato |
| --- | --- | --- |
| `PORTAL_HOST` | `0.0.0.0` | Host Flask |
| `PORTAL_PORT` | `80` | Porta HTTP |
| `WIFI_INTERFACE` | `wlan0` | Interfaccia Wi-Fi storica, usata come default per hotspot e client |
| `HOTSPOT_INTERFACE` | valore di `WIFI_INTERFACE` | Interfaccia Wi-Fi dedicata all'hotspot temporaneo |
| `CLIENT_WIFI_INTERFACE` | valore di `WIFI_INTERFACE` | Interfaccia Wi-Fi usata per scansione e connessione alla rete finale |
| `HOTSPOT_CONNECTION_NAME` | `Pi Setup AP` | Nome profilo NetworkManager |
| `HOTSPOT_SSID` | `Pi-Setup` | SSID dell'hotspot |
| `HOTSPOT_PASSWORD` | `ChangeMe123!` | Password WPA dell'hotspot |
| `HOTSPOT_ADDRESS` | `192.168.4.1/24` | IP del Raspberry in modalita' AP |
| `CONNECTION_WAIT_SECONDS` | `45` | Timeout per tentativo connessione |
| `AUTO_RECOVERY_ENABLED` | `true` | Attiva il monitor automatico di recovery hotspot |
| `RECOVERY_CHECK_INTERVAL_SECONDS` | `5` | Frequenza dei controlli di stato rete |
| `BOOT_CONNECTION_GRACE_SECONDS` | `75` | Attesa al boot prima di considerare fallita la connessione iniziale |
| `RECONNECT_GRACE_SECONDS` | `45` | Tempo minimo concesso a NetworkManager per i tentativi di riconnessione |
| `DISCONNECT_HOTSPOT_THRESHOLD_SECONDS` | `180` | Soglia di perdita prolungata della rete prima di riattivare l'hotspot |
| `HOTSPOT_COOLDOWN_SECONDS` | `90` | Pausa dopo provisioning o riattivazione hotspot per evitare rimbalzi |

Le variabili vengono lette da:

```text
/etc/raspberry-wifi-portal/portal.env
```

Questo file viene preservato durante reinstallazioni o aggiornamenti.

### Scenari con una o due interfacce Wi-Fi

Il dongle Wi-Fi USB non e' obbligatorio. Il portale funziona anche con la sola radio Wi-Fi integrata del Raspberry.

Scenario con sola Wi-Fi integrata:

```dotenv
HOTSPOT_INTERFACE=wlan0
CLIENT_WIFI_INTERFACE=wlan0
```

In questo caso `wlan0` viene usata prima come hotspot temporaneo e poi come client verso la rete finale. Durante il tentativo di connessione il telefono perde temporaneamente `Pi-Setup`; se la configurazione fallisce, il recovery puo' riaprire l'hotspot.

Scenario con Wi-Fi integrata e dongle USB:

```dotenv
HOTSPOT_INTERFACE=wlan0
CLIENT_WIFI_INTERFACE=wlan1
```

Con questa configurazione:

- `wlan0` mantiene attivo l'hotspot temporaneo `Pi-Setup`
- `wlan1` scansiona le reti e prova la connessione alla rete finale
- il telefono puo' restare collegato al portale mentre il Raspberry tenta la connessione con l'altra interfaccia
- se la connessione finale riesce, l'hotspot temporaneo viene spento come nel flusso standard

I nomi reali possono cambiare in base al dongle e alle regole di sistema. Sul Raspberry verifica con:

```bash
nmcli device status
```

Se non imposti `HOTSPOT_INTERFACE` e `CLIENT_WIFI_INTERFACE`, il comportamento resta quello storico: entrambe usano `WIFI_INTERFACE`.

## Recovery automatico hotspot

Il portale ora include un monitor in background che distingue tre casi:

- `boot senza rete`: il Raspberry attende `BOOT_CONNECTION_GRACE_SECONDS` prima di riaprire `Pi-Setup`
- `perdita temporanea`: se la Wi-Fi aziendale cade per pochi secondi o NetworkManager sta ancora tentando il recupero, l'hotspot non viene riattivato
- `perdita prolungata`: se la rete resta assente oltre `DISCONNECT_HOTSPOT_THRESHOLD_SECONDS`, l'hotspot viene riaperto automaticamente

La soglia piu' importante da tarare e':

- `DISCONNECT_HOTSPOT_THRESHOLD_SECONDS=180`

Con questo valore il Raspberry tollera circa 3 minuti di assenza rete prima di tornare in modalita' setup. E' una scelta prudente per ambienti con Wi-Fi instabile o AP che cambiano canale.

Per ambienti piu' sensibili:

- aumenta `RECONNECT_GRACE_SECONDS` se NetworkManager impiega tempo a riprendere la rete
- aumenta `DISCONNECT_HOTSPOT_THRESHOLD_SECONDS` se vuoi ignorare blackout piu' lunghi
- riduci `BOOT_CONNECTION_GRACE_SECONDS` solo se vuoi che l'hotspot compaia molto rapidamente al boot

### Profili pronti

Nel progetto trovi tre profili in `deploy/profiles/`:

- `stable.env`
  Per reti aziendali abbastanza stabili. Riapre l'hotspot piu' rapidamente.

- `balanced.env`
  Profilo consigliato di default. Buon compromesso tra recupero e tolleranza.

- `unstable.env`
  Per ambienti con disconnessioni piu' frequenti o AP che impiegano tempo a ristabilirsi.

Sul Raspberry puoi applicarli cosi':

```bash
cd /opt/raspberry-wifi-portal
sudo chmod +x scripts/apply_recovery_profile.sh
sudo ./scripts/apply_recovery_profile.sh balanced
```

Puoi sostituire `balanced` con `stable` oppure `unstable`.

## Gestione indirizzi IP LAN

Se il Raspberry e' collegato anche con cavo Ethernet, il portale mostra nella sezione `Indirizzi IP`:

- nome interfaccia, ad esempio `eth0` o `wlan0`
- tipo e stato
- profilo NetworkManager attivo
- indirizzi IPv4 correnti
- gateway
- DNS
- metodo IPv4, ad esempio `auto` o `manual`

Dalla stessa sezione puoi impostare:

- `DHCP automatico`
- `Indirizzo statico`, nel formato `192.168.1.50/24`
- gateway opzionale
- DNS opzionali separati da virgola, spazio o punto e virgola

Per evitare di perdere l'accesso al portale durante il setup, l'interfaccia che sta servendo l'hotspot temporaneo viene mostrata ma non puo' essere modificata finche' l'hotspot e' attivo. La configurazione e' pensata soprattutto per la LAN cablata, ad esempio `eth0`.

## Dipendenze

### Sistema

- `python3`
- `python3-pip`
- `network-manager`

### Python

- `Flask`

## Installer diretto per Raspberry Pi

Si', ora il progetto include un installer diretto. Il flusso consigliato e':

### 1. Preparare il pacchetto sul PC

Da questa cartella:

```bash
chmod +x scripts/package_release.sh
./scripts/package_release.sh
```

Su Windows PowerShell puoi usare direttamente:

```powershell
.\scripts\package_release.ps1
```

Otterrai un archivio in:

```text
release/raspberry-wifi-portal-YYYYMMDD-HHMMSS.tar.gz
```

### 2. Copiare il pacchetto sul Raspberry

Esempio con `scp`:

```bash
scp release/raspberry-wifi-portal-YYYYMMDD-HHMMSS.tar.gz pi@raspberrypi.local:/tmp/
```

### 3. Installare sul Raspberry

Sul Raspberry:

```bash
cd /tmp
tar -xzf raspberry-wifi-portal-YYYYMMDD-HHMMSS.tar.gz
cd raspberry-wifi-portal
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh --interactive
```

Per una reinstallazione ripetibile puoi saltare le domande:

```bash
sudo ./scripts/install.sh --ssid Pi-Setup --password 'ChangeMe123!' --port 80 --profile balanced
```

### 4. Personalizzare hotspot e porta dopo l'installazione

Modifica:

```text
/etc/raspberry-wifi-portal/portal.env
```

Poi riavvia il servizio:

```bash
sudo systemctl restart raspberry-wifi-portal.service
```

### 5. Verifica servizio

```bash
sudo systemctl status raspberry-wifi-portal.service
sudo journalctl -u raspberry-wifi-portal.service -f
```

## Aggiornamento

Per aggiornare:

1. crea un nuovo archivio
2. copialo sul Raspberry
3. estrailo
4. rilancia `sudo ./scripts/install.sh`

Il file `/etc/raspberry-wifi-portal/portal.env` viene mantenuto.

## Pubblicazione su GitHub

Per facilitare l'installazione su Raspberry, la strada migliore e' pubblicare direttamente la cartella `raspberry-wifi-portal` come repository GitHub dedicato.

### 1. Inizializzare il repository locale

Da PowerShell:

```powershell
cd "C:\Users\Desktop-user\PROGETTI\SVILUPPO\Scheda prodotto editor\raspberry-wifi-portal"
git init
git add .
git commit -m "Initial Raspberry Wi-Fi portal"
```

### 2. Creare il repository su GitHub

Su GitHub crea un nuovo repository, ad esempio:

```text
raspberry-wifi-portal
```

### 3. Collegare il repository locale a GitHub

Repository pubblicato:

```powershell
git remote add origin https://github.com/andreakys/raspberry-wifi-portal.git
git branch -M main
git push -u origin main
```

### 4. Installare dal repository GitHub sul Raspberry

Sul Raspberry:

```bash
sudo apt-get update
sudo apt-get install -y git
cd /tmp
git clone https://github.com/andreakys/raspberry-wifi-portal.git
cd raspberry-wifi-portal
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh --interactive
```

### 4.b Bootstrap diretto da GitHub

Dopo aver pubblicato il repository, puoi anche usare questo comando unico:

```bash
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced
```

### 5. Aggiornare dal repository GitHub

Sul Raspberry:

```bash
cd /tmp/raspberry-wifi-portal
git pull
sudo ./scripts/install.sh --profile balanced
```

Per semplificare il repository su GitHub ti consiglio anche:

- nome repo: `raspberry-wifi-portal`
- branch principale: `main`
- usare `Releases` per allegare l'archivio `.tar.gz`
- tenere nel repository solo il codice sorgente, non `output/`, `tmp/` o `release/`

Se vuoi distribuire versioni piu' stabili, puoi anche usare le `GitHub Releases` con l'archivio `.tar.gz` generato da `package_release.ps1`.

## Rimozione

Sul Raspberry:

```bash
sudo chmod +x scripts/uninstall.sh
sudo ./scripts/uninstall.sh
```

## Limiti attuali del prototipo

- Con una sola interfaccia Wi-Fi il Raspberry alterna modalita' `AP` e `client`.
- Con due interfacce Wi-Fi puoi dedicare una radio all'hotspot e una alla connessione finale.
- Non implementa un vero captive portal con redirect DNS automatico.
- Il supporto `802.1X` e' di base: copre `PEAP`, `TTLS` e `TLS`, ma alcune reti aziendali richiedono impostazioni piu' specifiche.
- I percorsi dei certificati per `TLS` devono gia' esistere sul Raspberry.

## Evoluzioni consigliate

Per un impianto piu' robusto:

- usare una chiavetta Wi-Fi USB per separare `hotspot` e `client` quando vuoi mantenere il portale sempre disponibile
- integrare `dnsmasq` per captive portal automatico
- memorizzare i certificati `802.1X` tramite upload sicuro
- aggiungere autenticazione amministrativa alla pagina
- esporre un pulsante fisico GPIO per riaprire il portale di setup
