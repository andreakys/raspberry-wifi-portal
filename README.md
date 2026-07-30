# VT Network Manager

<p align="center">
  <img src="static/visualtronics-logo.png" alt="Visualtronics" width="250">
</p>
<p align="center">
  <strong>Visualtronics s.a.s.</strong><br>
  Via Galimberti, 75/2 &ndash; 10040 Piobesi Torinese<br>
  C.F./P.I. 02638430047 &ndash; <a href="mailto:info@visualtronics.com">info@visualtronics.com</a>
</p>

Portale di gestione rete per display a LED: configura hotspot, Wi-Fi client, LAN cablata, indirizzi IP e stato del dispositivo, inclusi i casi base `WPA2/WPA3 Personal` e `802.1X`.

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
sudo ./scripts/install.sh --ssid Pi-Setup --password 'ChangeMe123!' --portal-password 'CambiaQuestaPassword!' --profile balanced
```

### Bootstrap quasi one-line da GitHub

Se vuoi un flusso ancora piu' semplice, puoi pubblicare anche `scripts/bootstrap_from_github.sh` e usarlo cosi':

```bash
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced
```

### Dopo l'installazione

1. collega il telefono a `Pi-Setup`
2. apri `http://192.168.4.1`
3. accedi con la password portale stampata dall'installer
4. verifica che in alto compaia la versione corrente del portale
5. premi `Scansiona reti` per aggiornare le reti visibili
6. inserisci o seleziona i dati della rete finale
7. scegli un profilo recovery `stable`, `balanced` o `unstable` se necessario

## Funzioni principali

- hotspot temporaneo per onboarding senza cavo Ethernet
- portale web locale da smartphone o tablet
- accesso protetto da password del portale
- numero versione visibile in login, dashboard e API status
- logo e riferimenti Visualtronics nel portale e nei documenti
- temperatura scheda visibile nella dashboard
- pulsante di riavvio protetto da login
- scheda accesso con link e QR cliccabili, scaricabile direttamente in PDF
- pulsante di scansione reti Wi-Fi disponibili
- scansione adattiva con riavvio temporaneo hotspot soltanto quando la radio selezionata lo richiede
- separazione opzionale tra interfaccia hotspot e interfaccia Wi-Fi client
- priorita' automatica al dongle `wlan1` per il client quando sono presenti entrambe le radio
- supporto `WPA2/WPA3 Personal`
- supporto base `802.1X` con `PEAP`, `TTLS`, `TLS`
- visualizzazione degli indirizzi IPv4 correnti di Wi-Fi e LAN
- visualizzazione dei MAC address di LAN e radio Wi-Fi
- configurazione IPv4 DHCP/statico per interfacce non usate dall'hotspot attivo
- recovery automatico dell'hotspot dopo boot fallito o perdita prolungata rete
- spegnimento automatico di `Pi-Setup` dopo Wi-Fi client o LAN stabili
- tentativi periodici delle reti salvate quando hotspot e client condividono `wlan0`
- installazione da archivio o da repository GitHub
- profili pronti per reti stabili o instabili
- server TCP locale di sola lettura con riepilogo rete ogni 30 secondi

## Obiettivo

Quando il Raspberry Pi non ha ancora una connessione valida:

1. attiva un hotspot temporaneo `Pi-Setup`
2. espone una pagina web locale
3. riceve i parametri della rete aziendale
4. salva la configurazione tramite `NetworkManager`
5. tenta la connessione alla rete aziendale
6. spegne l'hotspot quando la nuova connessione o la LAN risultano stabili

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
|   |-- hotspot_recovery.py
|   |-- network_manager.py
|   |-- network_status_tcp.py
|   |-- scan_policy.py
|   `-- user_documents.py
|-- static/
|   |-- styles.css
|   `-- visualtronics-logo.png
|-- systemd/
|   `-- raspberry-wifi-portal.service
|-- templates/
|   |-- _brand.html
|   |-- access_sheet.html
|   |-- index.html
|   |-- login.html
|   |-- quick_guide.html
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
  Centralizza configurazione di rete, credenziali, branding aziendale, porta HTTP e timeout.

- `services/network_manager.py`
  Incapsula tutte le chiamate a `nmcli`:
  - scansione delle reti
  - creazione e avvio hotspot
  - creazione connessioni WPA-PSK
  - creazione connessioni `802.1X` `PEAP`, `TTLS` e `TLS`
  - lettura dello stato IPv4 delle interfacce
  - configurazione IPv4 DHCP/statico tramite `NetworkManager`
  - verifica stato e connettivita'

- `services/network_status_tcp.py`
  Compone il riepilogo testuale e gestisce il server TCP locale sulla porta `6001`.

- `services/scan_policy.py`
  Decide se la radio selezionata richiede lo spegnimento dell'hotspot e se il browser dispone di un collegamento alternativo sicuro.

- `services/user_documents.py`
  Genera QR SVG e PDF A4 della guida rapida e della scheda accesso, mantenendo cliccabili link e QR.

- `templates/index.html`
  Pagina principale con form di configurazione, documenti PDF e scansione reti.

- `templates/_brand.html`
  Fascia riutilizzabile con logo, ragione sociale, indirizzo, partita IVA ed email.

- `templates/access_sheet.html`
  Anteprima pulita dei dati di accesso con link e QR cliccabili.

- `templates/quick_guide.html`
  Anteprima della guida operativa stabile, senza valori live del dispositivo.

- `templates/login.html`
  Pagina di accesso protetto prima delle impostazioni.

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
  - permette installazione non interattiva con `--ssid`, `--password`, `--portal-password`, `--port` e `--profile`
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

Il servizio parte come `root`, distingue LAN cablata e Wi-Fi client, e attiva l'hotspot se la Wi-Fi client non e' disponibile dopo le soglie configurate.

### 2. Accesso da smartphone

Lo smartphone si collega all'SSID `Pi-Setup`, poi apre:

```text
http://192.168.4.1
```

Il portale richiede la password amministrativa `PORTAL_PASSWORD`. Se non viene indicata durante l'installazione, `install.sh` ne genera una sicura e la stampa a fine procedura.
Nel login e nei campi password Wi-Fi/802.1X e' disponibile il pulsante `Mostra`, utile per controllare la password prima di inviarla.

Dopo il login, la sezione `Documenti utente` permette di aprire:

- una guida rapida stabile per configurare LAN, Wi-Fi, radio e recovery, senza valori live che possono cambiare
- la scheda accesso con i dati operativi, il link e il QR del portale

La scheda accesso contiene:

- SSID hotspot temporaneo
- password hotspot
- indirizzo del portale
- password portale
- QR cliccabile per aprire il portale
- MAC address delle interfacce LAN e Wi-Fi presenti

I pulsanti `Scarica PDF` generano direttamente documenti A4 pronti da inviare o stampare. Nella scheda accesso, sia l'indirizzo sia il QR restano cliccabili anche dentro il PDF. E' comunque disponibile l'anteprima HTML con il comando `Stampa`. La scheda contiene password operative, quindi va condivisa solo con persone autorizzate.

La dashboard mostra la `Temperatura dispositivo`, letta da `/sys/class/thermal/thermal_zone0/temp`, e la classifica come `Normale`, `Sotto osservazione`, `Alta` o `Critica`. Il Wi-Fi attivo puo' aggiungere un po' di calore, soprattutto con traffico continuo, ma in un tabellone chiuso incidono maggiormente alimentatori LED, pannelli, carico del processore, temperatura ambiente e ventilazione.

Raspberry Pi applica una riduzione progressiva delle prestazioni tra 80 C e 85 C; il portale segnala quindi come critica la temperatura da 80 C. Vedi la [documentazione termica ufficiale](https://www.raspberrypi.com/documentation/hardware/raspberrypi/power.html).

### 3. Configurazione

La pagina consente tre modalita':

- `Open`
- `WPA2/WPA3 Personal`
- `WPA2/WPA3 Enterprise (802.1X)`

Per `802.1X` supporta questi profili base:

- `PEAP`
- `TTLS`
- `TLS`

La sezione `Reti visibili` include un solo pulsante `Scansiona reti`, che usa sempre l'interfaccia scelta nel form `Configura collegamento Wi-Fi` e aggiorna la lista senza ricaricare tutta la pagina. La lista mostra tutte le celle rilevate da NetworkManager, incluse quelle con segnale debole e piu' access point con lo stesso SSID; quando disponibili vengono mostrati anche canale e BSSID. Se l'elenco e' lungo, il riquadro resta compatto e la lista diventa scorrevole.

Se la radio selezionata sta anche gestendo l'hotspot, ad esempio `wlan0`, il portale adatta automaticamente l'azione. Dal telefono mostra una conferma, spegne l'hotspot per pochi secondi, cerca le reti, riattiva `Pi-Setup` e conserva il risultato; il telefono deve poi ricollegarsi e aggiornare la pagina.

Se accedi dal PC tramite cavo LAN, lo stesso pulsante puo' spegnere temporaneamente l'hotspot e aggiornare direttamente la lista senza perdere la pagina. Se invece selezioni `wlan1` mentre l'hotspot usa `wlan0`, esegue una normale scansione sulla seconda radio e l'hotspot rimane attivo. Avviso e comportamento cambiano subito quando scegli una radio diversa.

Per capire se hai una seconda interfaccia Wi-Fi, guarda il riquadro `Interfacce Wi-Fi` in alto: `1` indica solo la radio della scheda, `2` con nomi come `wlan0, wlan1` indica anche un dongle USB. Quando entrambe sono presenti, il portale seleziona automaticamente `wlan1` per scansione e connessione finale e riserva `wlan0` all'hotspot.

Se con entrambe le radio il form permette ancora di usare `wlan0` per il client, verifica che il portale mostri almeno la versione `1.15.0`. La versione `1.16.0` aggiunge la gestione automatica di accensione e spegnimento di `Pi-Setup`; la `1.17.0` aggiunge i PDF diretti e i collegamenti QR cliccabili; la `1.18.0` mostra i MAC address delle interfacce.

### 4. Provisioning

Il backend crea una nuova connessione `NetworkManager`, restituisce subito una pagina di attesa e poi prova ad attivare la nuova rete in background. Con la sola wlan0 il telefono perde temporaneamente il portale; con il dongle, Pi-Setup resta attivo fino alla verifica di stabilita' della connessione su wlan1.

### 5. Esito

- Con la sola wlan0, l'hotspot viene spento prima del tentativo e resta spento se la connessione riesce.
- Con wlan0 e wlan1, l'hotspot resta disponibile durante il tentativo e viene spento dopo 30 secondi di connessione client stabile.
- Se il tentativo fallisce, l'hotspot resta disponibile e l'utente puo' ritentare.

## Variabili d'ambiente

| Variabile | Default | Significato |
| --- | --- | --- |
| `PORTAL_HOST` | `0.0.0.0` | Host Flask |
| `PORTAL_PORT` | `80` | Porta HTTP |
| `PORTAL_TITLE` | `VT Network Manager` | Titolo mostrato nel portale |
| `APP_VERSION` | versione del codice | Versione mostrata nel portale |
| `COMPANY_NAME` | `Visualtronics s.a.s.` | Ragione sociale mostrata nel branding |
| `COMPANY_ADDRESS` | indirizzo Visualtronics | Indirizzo mostrato nel portale e nei documenti |
| `COMPANY_REGISTRATION` | `C.F./P.I. 02638430047` | Identificativo fiscale aziendale |
| `COMPANY_EMAIL` | `info@visualtronics.com` | Email aziendale cliccabile |
| `PORTAL_PASSWORD` | generata dall'installer | Password di accesso al portale web |
| `PORTAL_SESSION_SECRET` | generata dall'installer | Chiave server per firmare la sessione di login |
| `WIFI_INTERFACE` | `wlan0` | Interfaccia Wi-Fi storica, usata come default per hotspot e client |
| `HOTSPOT_INTERFACE` | valore di `WIFI_INTERFACE` | Interfaccia Wi-Fi dedicata all'hotspot temporaneo |
| `CLIENT_WIFI_INTERFACE` | valore di `WIFI_INTERFACE` | Fallback per la radio client; con `wlan0` e `wlan1` presenti viene usata sempre `wlan1` |
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
| `WIFI_CLIENT_STABLE_SECONDS` | `30` | Stabilita' Wi-Fi client richiesta prima di spegnere `Pi-Setup` |
| `LAN_STABLE_SECONDS` | `120` | Stabilita' LAN richiesta prima di spegnere `Pi-Setup` |
| `NO_ACCESS_HOTSPOT_DELAY_SECONDS` | `20` | Attesa prima di riaprire l'hotspot dopo la perdita della sola LAN |
| `HOTSPOT_CLIENT_RETRY_INTERVAL_SECONDS` | `300` | Intervallo dei tentativi Wi-Fi con la sola `wlan0` |
| `HOTSPOT_MINIMUM_UP_SECONDS` | `30` | Tempo minimo di permanenza dell'hotspot dopo l'attivazione |
| `MANUAL_HOTSPOT_HOLD_SECONDS` | `600` | Durata del mantenimento manuale di `Pi-Setup` |
| `NETWORK_STATUS_TCP_ENABLED` | `true` | Abilita il server TCP locale di stato rete |
| `NETWORK_STATUS_TCP_PORT` | `6001` | Porta TCP in ascolto solo su `127.0.0.1` |
| `NETWORK_STATUS_TCP_INTERVAL_SECONDS` | `30` | Intervallo tra due messaggi per i client collegati |

Le variabili vengono lette da:

```text
/etc/raspberry-wifi-portal/portal.env
```

Questo file viene preservato durante reinstallazioni o aggiornamenti.

### Server TCP locale di stato rete

VT Network Manager apre un server TCP di sola lettura su `127.0.0.1:6001`. La socket non e' raggiungibile dalla LAN o dall'hotspot: e' destinata a un altro processo in esecuzione sullo stesso dispositivo, ad esempio il software del display.

Quando un client si collega riceve subito una riga UTF-8 terminata da `\n`; finche' resta collegato riceve una nuova riga ogni 30 secondi. Sono supportati piu' client contemporanei. In assenza di client il servizio non esegue i controlli dedicati al messaggio TCP.

Esempio con Ethernet, hotspot su `wlan0` e Wi-Fi client su `wlan1`:

```text
internet: si, eth-ip: 192.168.1.14, eth-mode: DHCP, wi-fi enable: si, hot-spot: Pi-Setup / 192.168.4.1, wlan1: Azienda / 10.0.0.23
```

Esempio con radio Wi-Fi disabilitata:

```text
internet: si, eth-ip: 192.168.1.14, eth-mode: static, wi-fi enable: no, wi-fi off
```

Regole del formato:

- i campi sono separati da virgola e spazio
- gli indirizzi sono riportati senza prefisso CIDR
- `eth-mode` vale `DHCP`, `static` oppure `n/d`
- `internet: si` indica che il controllo di connettivita' di NetworkManager e' `full`; reti locali, captive portal e connettivita' limitata producono `no`
- con hotspot attivo compare `hot-spot: SSID / IP portale`
- ogni altra radio rilevata compare come `wlanX: SSID / IP`; se non e' connessa, SSID o IP possono valere `n/d`
- eventuali virgole contenute nei valori, ad esempio nell'SSID, vengono sostituite da spazi per non rompere la separazione dei campi

Prova locale, leggendo il primo messaggio e chiudendo la connessione:

```bash
python3 -c "import socket; s=socket.create_connection(('127.0.0.1', 6001)); print(s.recv(4096).decode().strip()); s.close()"
```

### Scenari con una o due interfacce Wi-Fi

Il dongle Wi-Fi USB non e' obbligatorio. Il portale funziona anche con la sola radio Wi-Fi integrata.

Nell'interfaccia `wlan0` e' indicata come `Wi-Fi integrata`. `wlan1` e' indicata come `dongle USB Wi-Fi` e viene mostrata soltanto quando NetworkManager la rileva realmente. Se il dongle non e' presente, wlan1 non compare e il portale usa wlan0 sia per hotspot sia per client.

Scenario con sola Wi-Fi integrata:

```dotenv
HOTSPOT_INTERFACE=wlan0
CLIENT_WIFI_INTERFACE=wlan0
```

In questo caso `wlan0` viene usata prima come hotspot temporaneo e poi come client verso la rete finale. Durante il tentativo di connessione il telefono perde temporaneamente `Pi-Setup`. Se esiste una rete salvata, il recovery sospende l'hotspot ogni 5 minuti per un tentativo controllato; se la rete non e' disponibile, `Pi-Setup` viene riaperto immediatamente.

Scenario con Wi-Fi integrata e dongle USB:

```dotenv
HOTSPOT_INTERFACE=wlan0
CLIENT_WIFI_INTERFACE=wlan1
```

Con questa configurazione:

- `wlan0` mantiene attivo l'hotspot temporaneo `Pi-Setup`
- `wlan1` scansiona le reti e prova la connessione alla rete finale
- `wlan0` non puo' essere selezionata come radio client finche' entrambe sono presenti
- il telefono puo' restare collegato al portale mentre il Raspberry tenta la connessione con l'altra interfaccia
- quando `wlan1` resta connessa per 30 secondi, l'hotspot temporaneo viene spento automaticamente

La scelta e' automatica anche se il file `portal.env` contiene ancora `CLIENT_WIFI_INTERFACE=wlan0`: quando NetworkManager rileva sia wlan0 sia wlan1, il portale usa sempre wlan1. All'avvio, i profili Wi-Fi creati dal portale vengono associati alla radio client rilevata. Se il dongle viene rimosso, gli stessi profili tornano automaticamente su wlan0.

I nomi reali possono cambiare in base al dongle e alle regole di sistema. Sul Raspberry verifica con:

```bash
nmcli device status
```

Con la sola wlan0, `CLIENT_WIFI_INTERFACE` e `WIFI_INTERFACE` continuano a funzionare come fallback. La priorita' automatica a wlan1 si applica soltanto quando entrambe le radio sono realmente rilevate.

## Recovery automatico hotspot

Il monitor in background distingue la disponibilita' della Wi-Fi client dalla presenza di una via di amministrazione alternativa:

- `boot senza Wi-Fi client`: il Raspberry attende `BOOT_CONNECTION_GRACE_SECONDS` prima di riaprire `Pi-Setup`
- `perdita temporanea Wi-Fi`: se la Wi-Fi aziendale cade per pochi secondi o NetworkManager sta ancora tentando il recupero, l'hotspot non viene riattivato
- `perdita prolungata Wi-Fi`: se la Wi-Fi client resta assente oltre `DISCONNECT_HOTSPOT_THRESHOLD_SECONDS`, l'hotspot viene riaperto automaticamente
- `LAN stabile`: dopo `LAN_STABLE_SECONDS` l'hotspot viene spento, perche' il portale resta raggiungibile via Ethernet
- `wlan1 stabile`: dopo `WIFI_CLIENT_STABLE_SECONDS` l'hotspot su wlan0 viene spento
- `sola wlan0`: con una rete gestita salvata, ogni `HOTSPOT_CLIENT_RETRY_INTERVAL_SECONDS` l'hotspot viene sospeso brevemente per tentare la riconnessione

Una LAN e' considerata disponibile soltanto quando l'interfaccia Ethernet e' `connected` e possiede un indirizzo IPv4. Non e' richiesto l'accesso a Internet.

### Matrice recovery LAN/Wi-Fi

| LAN cablata | Wi-Fi client | `Pi-Setup` |
| --- | --- | --- |
| Presente e stabile | Connessa | Spento |
| Presente e stabile | Assente | Spento dopo 120 secondi; portale disponibile via LAN |
| Appena collegata | Assente | Resta attivo durante la verifica di stabilita' |
| Assente | `wlan1` connessa | Spento dopo 30 secondi di stabilita' |
| Assente | Nessuna client | Attivo dopo il tempo di recovery |
| Appena persa | Nessuna client | Si riattiva dopo 20 secondi se l'ultima via era la LAN |

Con la sola wlan0 e una rete gestita salvata:

1. `Pi-Setup` resta disponibile per 5 minuti.
2. Il servizio spegne temporaneamente l'hotspot, esegue una scansione e prova fino a due profili visibili, dando priorita' all'ultima rete usata.
3. Se il tentativo riesce, wlan0 resta client e l'hotspot rimane spento.
4. Se fallisce, `Pi-Setup` viene riattivato immediatamente.

Il portale mostra il motivo dello stato corrente e il tempo previsto alla prossima azione. I comandi manuali permettono di mantenere `Pi-Setup` per 10 minuti oppure spegnerlo quando esiste gia' un collegamento alternativo.

Le operazioni automatiche restano sospese durante provisioning, scansione completa e cooldown, evitando cambi di modalita' mentre l'utente sta configurando la rete.

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

## Interfacce di rete e indirizzi IP

Subito sotto il riepilogo iniziale, il portale mostra la sezione `Interfacce di rete e indirizzi IP`. Se il Raspberry e' collegato anche con cavo Ethernet, qui trovi:

- nome interfaccia, ad esempio `eth0` o `wlan0`
- tipo e stato
- MAC address
- profilo NetworkManager attivo
- indirizzi IPv4 correnti
- gateway
- DNS
- metodo IPv4, ad esempio `auto` o `manual`

Nel form `Modifica indirizzo IP` puoi impostare:

- `DHCP automatico`
- `Indirizzo statico`, nel formato `192.168.1.50/24`
- gateway opzionale
- DNS opzionali separati da virgola, spazio o punto e virgola

Il pulsante di conferma e' `Applica configurazione IP`.

Per evitare di perdere l'accesso al portale durante il setup, l'interfaccia che sta servendo l'hotspot temporaneo viene mostrata ma non puo' essere modificata finche' l'hotspot e' attivo. La configurazione e' pensata soprattutto per la LAN cablata, ad esempio `eth0`.

La sottosezione `Connessioni salvate dal portale` permette di eliminare profili Wi-Fi o LAN creati dal portale, cioe' quelli con nome `setup-*`, per poi ricrearli da zero. I profili di sistema non creati dal portale, ad esempio `netplan-*`, non vengono proposti per la cancellazione.

## Dipendenze

### Sistema

- `python3`
- `python3-pip`
- `network-manager`

### Python

- `Flask`
- `ReportLab`

## Installer diretto

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

### 2. Copiare il pacchetto sul dispositivo

Esempio con `scp`:

```bash
scp release/raspberry-wifi-portal-YYYYMMDD-HHMMSS.tar.gz pi@raspberrypi.local:/tmp/
```

### 3. Installare sul dispositivo

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
sudo ./scripts/install.sh --ssid Pi-Setup --password 'ChangeMe123!' --portal-password 'CambiaQuestaPassword!' --port 80 --profile balanced
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

Se dopo un aggiornamento l'interfaccia sembra vecchia, controlla:

```bash
cd /opt/raspberry-wifi-portal
git rev-parse --short HEAD 2>/dev/null || true
grep -E 'PORTAL_TITLE|APP_VERSION' /etc/raspberry-wifi-portal/portal.env
sudo systemctl restart raspberry-wifi-portal.service
```

Il portale aggiornato mostra un badge `Versione 1.19.0`, il logo e i contatti Visualtronics, lo stato `Gestione automatica hotspot`, i comandi `Attiva 10 min` e `Spegni`, temperatura, MAC address e i pulsanti `Scarica PDF`. Con due radio, wlan1 e' selezionata automaticamente e wlan0 appare riservata all'hotspot. Se non trovi queste funzioni, il servizio sta ancora usando una copia precedente o non e' stato reinstallato/riavviato.

## Aggiornamento da archivio

Per aggiornare:

1. crea un nuovo archivio
2. copialo sul Raspberry
3. estrailo
4. rilancia `sudo ./scripts/install.sh`

Il file `/etc/raspberry-wifi-portal/portal.env` viene mantenuto.
L'installer aggiorna automaticamente i vecchi titoli di default `Raspberry Pi Wi-Fi Setup`, `Wi-Fi Setup` e `Pi Network Manager` in `VT Network Manager`; eventuali titoli personalizzati vengono lasciati invariati.

## Pubblicazione su GitHub

Per facilitare l'installazione su Raspberry, la strada migliore e' pubblicare direttamente la cartella `raspberry-wifi-portal` come repository GitHub dedicato.

### 1. Inizializzare il repository locale

Da PowerShell:

```powershell
cd "C:\Users\Desktop-user\PROGETTI\SVILUPPO\Raspberry-wifi-portal"
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

### 4. Installare dal repository GitHub sul dispositivo

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

Metodo consigliato, indipendente dalla presenza del vecchio clone:

```bash
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced
```

Il bootstrap scarica la branch `main`, reinstalla il servizio e conserva `/etc/raspberry-wifi-portal/portal.env`. Se hai ancora il clone originale, puoi anche eseguire `git pull` in quella cartella e rilanciare `sudo ./scripts/install.sh --profile balanced`.

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
- aggiungere gestione utenti o cambio password direttamente dalla pagina
- esporre un pulsante fisico GPIO per riaprire il portale di setup
