# Manuale Utente

## Wi-Fi Setup

Versione documento: 1.11.0
Data: 7 luglio 2026

## 1. Scopo

Questo manuale descrive come installare, configurare e utilizzare il portale Wi-Fi per Raspberry Pi 5.

Il sistema crea un hotspot temporaneo chiamato `Pi-Setup` quando il Raspberry non e' ancora collegato alla rete finale. Da smartphone o tablet e' possibile aprire una pagina web locale, inserire i dati della rete aziendale e lasciare che il Raspberry provi automaticamente la connessione.

## 2. Funzioni principali

- hotspot temporaneo per il primo accesso
- pagina web locale protetta da password per la configurazione
- versione applicazione visibile per verificare gli aggiornamenti installati
- scheda accesso stampabile o salvabile in PDF dal browser
- scansione manuale delle reti Wi-Fi disponibili dal portale
- scansione completa con riavvio temporaneo hotspot quando si usa una sola radio Wi-Fi
- separazione opzionale tra hotspot e Wi-Fi client con due interfacce
- supporto reti Open
- supporto reti WPA2/WPA3 Personal
- supporto base reti aziendali 802.1X: `PEAP`, `TTLS`, `TLS`
- visualizzazione indirizzi IPv4 correnti di Wi-Fi e LAN
- configurazione IPv4 DHCP/statico per interfacce non usate dall'hotspot attivo
- installazione guidata con parametri interattivi
- installazione non interattiva per provisioning ripetibili
- servizio `systemd` per avvio automatico

## 3. Requisiti

### Hardware

- Raspberry Pi 5
- alimentazione stabile
- microSD con Raspberry Pi OS
- smartphone, tablet o PC con Wi-Fi

### Software

- Raspberry Pi OS aggiornato
- `NetworkManager`
- `python3`
- accesso terminale sul Raspberry

## 4. Contenuto del pacchetto

Il progetto include:

- applicazione Flask
- script di installazione
- script di packaging
- file di configurazione esempio
- servizio `systemd`

## 5. Procedura di installazione

### 5.0 Installazione rapida da GitHub

Se il progetto e' gia' pubblicato su GitHub:

```bash
sudo apt-get update
sudo apt-get install -y git
cd /tmp
git clone https://github.com/andreakys/raspberry-wifi-portal.git
cd raspberry-wifi-portal
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh --interactive
```

L'installazione guidata chiede:

- SSID dell'hotspot temporaneo
- password dell'hotspot temporaneo
- password di accesso al portale, oppure la genera automaticamente se lasci vuoto
- porta HTTP del portale
- profilo recovery: `stable`, `balanced` o `unstable`

Per installazione non interattiva:

```bash
sudo ./scripts/install.sh --ssid Pi-Setup --password 'ChangeMe123!' --portal-password 'CambiaQuestaPassword!' --profile balanced
```

Per un flusso ancora piu' rapido:

```bash
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced
```

### 5.1 Preparare il pacchetto sul PC Windows

Apri PowerShell nella cartella del progetto ed esegui:

```powershell
cd "C:\Users\Desktop-user\PROGETTI\SVILUPPO\Scheda prodotto editor\raspberry-wifi-portal"
.\scripts\package_release.ps1
```

Il comando crea un archivio `.tar.gz` nella cartella `release`.

### 5.2 Copiare il pacchetto sul Raspberry

Esempio:

```bash
scp /percorso/del/pacchetto/raspberry-wifi-portal-YYYYMMDD-HHMMSS.tar.gz pi@raspberrypi.local:/tmp/
```

### 5.3 Installare sul Raspberry

Accedi al Raspberry e lancia:

```bash
ssh pi@raspberrypi.local
cd /tmp
tar -xzf raspberry-wifi-portal-YYYYMMDD-HHMMSS.tar.gz
cd raspberry-wifi-portal
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh --interactive
```

L'installer:

- installa le dipendenze richieste
- copia i file in `/opt/raspberry-wifi-portal` usando una cartella temporanea di staging
- crea la virtual environment Python
- crea il file `/etc/raspberry-wifi-portal/portal.env`
- conserva `portal.env` durante reinstallazioni e aggiornamenti
- puo' essere rilanciato anche da `/opt/raspberry-wifi-portal`
- accetta opzioni `--ssid`, `--password`, `--portal-password`, `--port`, `--profile`, `--skip-apt` e `--no-start`
- registra e avvia il servizio

Esempio non interattivo:

```bash
sudo ./scripts/install.sh --ssid Pi-Setup --password 'ChangeMe123!' --portal-password 'CambiaQuestaPassword!' --port 80 --profile balanced
```

## 6. Configurazione iniziale

### 6.1 File principale di configurazione

Il file da modificare e':

```text
/etc/raspberry-wifi-portal/portal.env
```

Esempio:

```dotenv
PORTAL_HOST=0.0.0.0
PORTAL_PORT=80
PORTAL_DEBUG=false
PORTAL_TITLE=Wi-Fi Setup
APP_VERSION=
PORTAL_PASSWORD=password-di-accesso-al-portale
PORTAL_SESSION_SECRET=chiave-sessione-generata
WIFI_INTERFACE=wlan0
HOTSPOT_INTERFACE=wlan0
CLIENT_WIFI_INTERFACE=wlan0
HOTSPOT_CONNECTION_NAME=Pi Setup AP
HOTSPOT_SSID=Pi-Setup
HOTSPOT_PASSWORD=ChangeMe123!
HOTSPOT_ADDRESS=192.168.4.1/24
CONNECTION_WAIT_SECONDS=45
AUTO_RECOVERY_ENABLED=true
RECOVERY_CHECK_INTERVAL_SECONDS=5
BOOT_CONNECTION_GRACE_SECONDS=75
RECONNECT_GRACE_SECONDS=45
DISCONNECT_HOTSPOT_THRESHOLD_SECONDS=180
HOTSPOT_COOLDOWN_SECONDS=90
```

### 6.2 Scenari con una o due interfacce Wi-Fi

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

I nomi reali possono cambiare in base al dongle. Verifica sul Raspberry con:

```bash
nmcli device status
```

Se non imposti `HOTSPOT_INTERFACE` e `CLIENT_WIFI_INTERFACE`, entrambe usano il valore di `WIFI_INTERFACE`.

### 6.3 Riavvio del servizio

Dopo ogni modifica:

```bash
sudo systemctl restart raspberry-wifi-portal.service
```

### 6.4 Verifica stato

```bash
sudo systemctl status raspberry-wifi-portal.service
sudo journalctl -u raspberry-wifi-portal.service -f
```

### 6.5 Recovery automatico dell'hotspot

Il sistema controlla periodicamente lo stato della rete e distingue:

- boot senza Wi-Fi client valida
- perdita temporanea della Wi-Fi aziendale
- perdita prolungata della Wi-Fi aziendale

La LAN cablata viene trattata come connettivita' separata: se `eth0` e' collegata, il portale mostra che la LAN e' presente, ma la sola LAN non blocca piu' il recovery dell'hotspot quando la Wi-Fi client non e' configurata o non e' connessa.

Matrice recovery LAN/Wi-Fi:

- LAN presente, Wi-Fi client connessa: non apre `Pi-Setup`, perche' la Wi-Fi client e' ok.
- LAN presente, Wi-Fi client configurata ma non connessa al boot: attende il grace al boot, poi apre `Pi-Setup`.
- LAN presente, Wi-Fi client persa dopo una connessione valida: attende la soglia di perdita prolungata, poi apre `Pi-Setup`.
- LAN presente, Wi-Fi client non configurata: attende il grace al boot, poi apre `Pi-Setup` anche se la LAN funziona.
- LAN assente, Wi-Fi client connessa: non apre `Pi-Setup`, perche' la Wi-Fi client e' ok.
- LAN assente, Wi-Fi client configurata ma router non disponibile al boot: attende il grace al boot, poi apre `Pi-Setup`.
- LAN assente, Wi-Fi client persa dopo una connessione valida: attende la soglia di perdita prolungata, poi apre `Pi-Setup`.
- LAN assente, Wi-Fi client non configurata: attende il grace al boot, poi apre `Pi-Setup`.

Valori consigliati:

- `BOOT_CONNECTION_GRACE_SECONDS=75`
- `RECONNECT_GRACE_SECONDS=45`
- `DISCONNECT_HOTSPOT_THRESHOLD_SECONDS=180`
- `HOTSPOT_COOLDOWN_SECONDS=90`

Interpretazione pratica:

- se il Raspberry si accende e non riesce a collegarsi, attende circa 75 secondi prima di riaprire `Pi-Setup`
- se la rete cade per pochi secondi o NetworkManager sta ancora tentando il recupero, l'hotspot non viene riattivato
- se la perdita supera circa 3 minuti, il Raspberry riattiva automaticamente l'hotspot

### 6.6 Profili pronti di recovery

Il progetto include tre profili:

- `stable`
- `balanced`
- `unstable`

Applicazione sul Raspberry:

```bash
cd /opt/raspberry-wifi-portal
sudo chmod +x scripts/apply_recovery_profile.sh
sudo ./scripts/apply_recovery_profile.sh balanced
```

Uso consigliato:

- `stable` per reti abbastanza affidabili
- `balanced` per uso generale
- `unstable` per reti con blackout o roaming piu' frequenti

### 6.7 Gestione indirizzi IP LAN

Se il Raspberry e' collegato anche con cavo Ethernet, il portale mostra una sezione `Indirizzi IP`.

Per ogni interfaccia vengono mostrati:

- nome interfaccia, ad esempio `eth0` o `wlan0`
- tipo e stato
- profilo NetworkManager attivo
- indirizzi IPv4 correnti
- gateway
- DNS
- metodo IPv4, ad esempio `auto` o `manual`

Dalla stessa sezione puoi configurare una interfaccia in:

- `DHCP automatico`
- `Indirizzo statico`

Per un indirizzo statico usa il formato:

```text
192.168.1.50/24
```

Gateway e DNS sono opzionali. I DNS possono essere separati da virgola, spazio o punto e virgola.

Nota di sicurezza operativa: l'interfaccia che sta servendo l'hotspot temporaneo viene mostrata ma non puo' essere modificata finche' l'hotspot e' attivo. Questo evita di perdere il portale durante il setup. La funzione e' pensata soprattutto per configurare la LAN cablata, ad esempio `eth0`.

## 7. Utilizzo dal telefono

### 7.1 Collegamento all'hotspot

Quando il Raspberry non e' collegato a una rete valida, espone un hotspot temporaneo:

- SSID: `Pi-Setup`
- Password: definita in `portal.env`

### 7.2 Apertura del portale

Apri il browser e digita:

```text
http://192.168.4.1
```

Il portale mostra prima la pagina di accesso. Inserisci la password `PORTAL_PASSWORD`.
In alto viene mostrata anche la versione applicazione: usala per verificare che il Raspberry stia eseguendo davvero l'ultima release installata.

Se hai usato l'installazione guidata e hai lasciato vuota la password portale, lo script ne ha generata una automaticamente e l'ha stampata alla fine dell'installazione. La puoi ritrovare o cambiare in:

```text
/etc/raspberry-wifi-portal/portal.env
```

### 7.3 Scheda accesso stampabile

Dopo il login, la sezione `Scheda accesso` mostra il pulsante `Stampa/PDF`.

Il pulsante apre una pagina semplice, pensata per essere stampata o salvata come PDF dal browser, con:

- nome hotspot temporaneo
- password hotspot
- indirizzo portale, ad esempio `http://192.168.4.1`
- password portale
- interfacce Wi-Fi rilevate

La scheda contiene password operative: stampala o inviala solo a persone autorizzate.

Flusso consigliato:

1. Apri `Scheda accesso`.
2. Premi `Stampa/PDF`.
3. Stampa la pagina oppure scegli `Salva come PDF` nel browser.
4. Usa la scheda per collegarti all'hotspot e aprire il portale.

### 7.4 Scansione reti Wi-Fi

Nella sezione `Reti visibili` premi `Scansiona`.

Il Raspberry forza una nuova scansione sull'interfaccia `CLIENT_WIFI_INTERFACE` e aggiorna la lista senza ricaricare tutta la pagina. Toccando una rete rilevata, il campo `SSID` viene compilato automaticamente.

Se `HOTSPOT_INTERFACE` e `CLIENT_WIFI_INTERFACE` sono la stessa radio, per esempio `wlan0`, la scansione live puo' vedere solo `Pi-Setup` mentre l'hotspot e' attivo. In questo caso il portale mostra anche `Scansione completa`.

Se accedi al portale da un PC collegato via cavo LAN e la LAN e' presente, il pulsante `Scansiona` puo' fare direttamente una scansione completa: il portale spegne l'hotspot per pochi secondi, cerca le reti e aggiorna la lista restando raggiungibile tramite LAN.

Nota versione: dalla versione `1.11.0` il portale riconosce anche le installazioni in cui `nmcli` indica le connessioni Wi-Fi come `802-11-wireless`, mostra quante interfacce Wi-Fi sono rilevate e distingue la scansione da LAN cablata.

Quando premi `Scansione completa`:

1. il portale avvia la scansione in background
2. l'hotspot `Pi-Setup` viene spento per pochi secondi
3. il Raspberry cerca le reti Wi-Fi vicine
4. l'hotspot viene riattivato automaticamente
5. devi ricollegarti a `Pi-Setup` e aggiornare la pagina

Con due interfacce Wi-Fi, ad esempio hotspot su `wlan0` e client su `wlan1`, non serve spegnere l'hotspot: la scansione live usa direttamente la radio client.

Per capire se hai una seconda interfaccia Wi-Fi, guarda il riquadro `Interfacce Wi-Fi` nella parte alta del portale. Se mostra `2` e nomi come `wlan0, wlan1`, il Raspberry vede anche il dongle USB. In quel caso puoi configurare `HOTSPOT_INTERFACE=wlan0` e `CLIENT_WIFI_INTERFACE=wlan1` in `/etc/raspberry-wifi-portal/portal.env`.

### 7.5 Configurazione di una rete WPA2/WPA3 Personal

Compila:

- `SSID`
- `Password Wi-Fi`
- `Sicurezza = WPA2/WPA3 Personal`

Poi premi `Salva e connetti`.

### 7.6 Configurazione di una rete aziendale 802.1X

Compila:

- `SSID`
- `Sicurezza = WPA2/WPA3 Enterprise (802.1X)`
- `Metodo EAP`
- `Identita' utente`
- `Password enterprise` per `PEAP` o `TTLS`
- eventuale `CA certificate`
- eventuale `Domain suffix match`

Per `TLS` servono anche:

- `Client certificate`
- `Private key`
- facoltativamente `Private key password`

## 8. Cosa succede quando si preme "Salva e connetti"

1. Il Raspberry riceve i dati dal form.
2. Disattiva l'hotspot temporaneo.
3. Crea o aggiorna il profilo di rete.
4. Tenta la connessione alla rete indicata.
5. Se la connessione riesce, resta sulla nuova rete.
6. Se fallisce, il portale puo' essere riattivato per un nuovo tentativo.

Nota: usando una sola interfaccia Wi-Fi, il telefono perde la rete `Pi-Setup` durante il tentativo di connessione. Con due interfacce separate, l'hotspot puo' restare attivo mentre l'altra radio prova la rete finale.

## 9. Comandi utili

### 9.1 Riavvio servizio

```bash
sudo systemctl restart raspberry-wifi-portal.service
```

### 9.2 Arresto servizio

```bash
sudo systemctl stop raspberry-wifi-portal.service
```

### 9.3 Avvio servizio

```bash
sudo systemctl start raspberry-wifi-portal.service
```

### 9.4 Log in tempo reale

```bash
sudo journalctl -u raspberry-wifi-portal.service -f
```

### 9.5 Disinstallazione

```bash
cd /tmp/raspberry-wifi-portal
sudo chmod +x scripts/uninstall.sh
sudo ./scripts/uninstall.sh
```

## 10. Risoluzione problemi

### Il portale non si apre

- verifica di essere collegato all'SSID corretto
- controlla che l'indirizzo sia `http://192.168.4.1`
- verifica lo stato del servizio con `systemctl`

### Il Raspberry non si collega alla rete aziendale

- verifica `SSID` e password
- controlla il metodo EAP corretto
- controlla certificati e percorsi file in caso di `TLS`
- leggi i log del servizio

### La rete aziendale usa un captive portal

Il Raspberry puo' collegarsi al Wi-Fi ma restare con connettivita' limitata. In questo caso e' necessario completare il captive portal con il metodo previsto dall'azienda.

### La rete cade ogni tanto ma non voglio riattivare subito l'hotspot

Aumenta questi valori nel file `portal.env`:

- `RECONNECT_GRACE_SECONDS`
- `DISCONNECT_HOTSPOT_THRESHOLD_SECONDS`

Esempio prudente:

```dotenv
RECONNECT_GRACE_SECONDS=90
DISCONNECT_HOTSPOT_THRESHOLD_SECONDS=300
```

In questo modo il Raspberry aspetta piu' a lungo prima di rientrare in modalita' setup.

### Serve piu' affidabilita'

Per ambienti produttivi si consiglia:

- una seconda chiavetta Wi-Fi USB se vuoi mantenere l'hotspot disponibile durante i tentativi di connessione
- password portale lunga e diversa dalla password dell'hotspot
- upload sicuro dei certificati
- backup del file `portal.env`

## 11. Manutenzione

Per aggiornare l'applicazione:

1. crea un nuovo archivio dal PC
2. copialo sul Raspberry
3. estrailo
4. riesegui `sudo ./scripts/install.sh --profile balanced`

Il file `/etc/raspberry-wifi-portal/portal.env` viene mantenuto.
Se il titolo e' ancora il vecchio default `Raspberry Pi Wi-Fi Setup`, l'installer lo aggiorna automaticamente a `Wi-Fi Setup`. I titoli personalizzati non vengono sovrascritti.

Se dopo l'aggiornamento l'interfaccia sembra vecchia:

```bash
cd /opt/raspberry-wifi-portal
sudo ./scripts/install.sh --profile balanced
sudo systemctl restart raspberry-wifi-portal.service
```

Verifica nel portale la presenza di:

- badge `Versione`
- pulsante `Scansiona`
- tasto `Esci`
- riquadro `Interfacce Wi-Fi`
- sezione `Scheda accesso`

## 12. Pubblicazione su GitHub

Per semplificare installazione e aggiornamenti sul Raspberry, e' consigliato pubblicare il progetto su GitHub come repository dedicato.

### 12.1 Inizializzazione locale

Da PowerShell:

```powershell
cd "C:\Users\Desktop-user\PROGETTI\SVILUPPO\Scheda prodotto editor\raspberry-wifi-portal"
git init
git add .
git commit -m "Initial Raspberry Wi-Fi portal"
```

### 12.2 Creazione repository remoto

Crea su GitHub un repository chiamato per esempio:

```text
raspberry-wifi-portal
```

### 12.3 Push verso GitHub

Repository pubblicato:

```powershell
git remote add origin https://github.com/andreakys/raspberry-wifi-portal.git
git branch -M main
git push -u origin main
```

### 12.4 Installazione dal repository GitHub sul Raspberry

```bash
sudo apt-get update
sudo apt-get install -y git
cd /tmp
git clone https://github.com/andreakys/raspberry-wifi-portal.git
cd raspberry-wifi-portal
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh --interactive
```

### 12.4.b Bootstrap diretto da GitHub

```bash
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced
```

### 12.5 Aggiornamento dal repository GitHub

```bash
cd /tmp/raspberry-wifi-portal
git pull
sudo ./scripts/install.sh --profile balanced
```

## 13. Riepilogo rapido

- installa il pacchetto sul Raspberry
- controlla `portal.env`
- collega il telefono a `Pi-Setup`
- apri `http://192.168.4.1`
- accedi con la password portale
- controlla il badge versione
- usa `Scheda accesso` se devi stampare o salvare in PDF i dati di accesso
- premi `Scansiona` per aggiornare le reti disponibili
- se sei collegato via LAN, `Scansiona` puo' fare la scansione completa senza perdere la pagina
- se vedi solo `Pi-Setup` e hai una sola radio Wi-Fi, usa `Scansione completa`
- inserisci i dati della rete finale
- attendi il tentativo di connessione
