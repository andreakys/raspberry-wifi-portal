# Manuale Utente

## VT Network Manager

Versione documento: 1.18.0
Data: 30 luglio 2026

## 1. Scopo

Questo manuale descrive come installare, configurare e utilizzare il portale di gestione rete del display a LED.

Il sistema crea un hotspot temporaneo chiamato `Pi-Setup` quando il Raspberry non e' ancora collegato alla rete finale. Da smartphone o tablet e' possibile aprire una pagina web locale, inserire i dati della rete aziendale e lasciare che il Raspberry provi automaticamente la connessione.

## 2. Funzioni principali

- hotspot temporaneo per il primo accesso
- pagina web locale protetta da password per la configurazione
- versione applicazione visibile per verificare gli aggiornamenti installati
- temperatura scheda visibile nella dashboard
- pulsante di riavvio protetto da login
- scheda accesso con link e QR cliccabili, scaricabile direttamente in PDF
- scansione manuale delle reti Wi-Fi disponibili dal portale
- scansione adattiva con riavvio temporaneo hotspot soltanto quando la radio selezionata lo richiede
- separazione opzionale tra hotspot e Wi-Fi client con due interfacce
- utilizzo automatico del dongle wlan1 per il client quando entrambe le radio sono presenti
- spegnimento automatico di `Pi-Setup` dopo Wi-Fi client o LAN stabili
- tentativo periodico delle reti salvate quando hotspot e client condividono wlan0
- supporto reti Open
- supporto reti WPA2/WPA3 Personal
- supporto base reti aziendali 802.1X: `PEAP`, `TTLS`, `TLS`
- visualizzazione indirizzi IPv4 correnti di Wi-Fi e LAN
- visualizzazione MAC address delle interfacce LAN e Wi-Fi
- configurazione IPv4 DHCP/statico per interfacce non usate dall'hotspot attivo
- installazione guidata con parametri interattivi
- installazione non interattiva per provisioning ripetibili
- servizio `systemd` per avvio automatico
- server TCP locale di sola lettura con riepilogo rete ogni 30 secondi

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

### 5.2 Copiare il pacchetto sul dispositivo

Esempio:

```bash
scp /percorso/del/pacchetto/raspberry-wifi-portal-YYYYMMDD-HHMMSS.tar.gz pi@raspberrypi.local:/tmp/
```

### 5.3 Installare sul dispositivo

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
PORTAL_TITLE=VT Network Manager
APP_VERSION=
PORTAL_PASSWORD=password-di-accesso-al-portale
PORTAL_SESSION_SECRET=chiave-sessione-generata
NETWORK_STATUS_TCP_ENABLED=true
NETWORK_STATUS_TCP_PORT=6001
NETWORK_STATUS_TCP_INTERVAL_SECONDS=30
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
WIFI_CLIENT_STABLE_SECONDS=30
LAN_STABLE_SECONDS=120
NO_ACCESS_HOTSPOT_DELAY_SECONDS=20
HOTSPOT_CLIENT_RETRY_INTERVAL_SECONDS=300
HOTSPOT_MINIMUM_UP_SECONDS=30
MANUAL_HOTSPOT_HOLD_SECONDS=600
```

### 6.2 Scenari con una o due interfacce Wi-Fi

Il dongle Wi-Fi USB non e' obbligatorio. Il portale funziona anche con la sola radio Wi-Fi integrata. Quando invece NetworkManager rileva sia wlan0 sia wlan1, la regola operativa e' fissa: wlan0 resta all'hotspot e wlan1 viene usata per scansione e connessione finale.

Nel portale le radio vengono indicate cosi':

- `wlan0 - Wi-Fi integrata`: radio presente sulla scheda
- `wlan1 - dongle USB Wi-Fi`: seconda radio, mostrata solo quando il dongle e' realmente rilevato

Scenario con sola Wi-Fi integrata:

```dotenv
HOTSPOT_INTERFACE=wlan0
CLIENT_WIFI_INTERFACE=wlan0
```

In questo caso `wlan0` viene usata prima come hotspot temporaneo e poi come client verso la rete finale. Le due modalita' non possono funzionare insieme. Se una rete gestita e' salvata, ogni 5 minuti il recovery sospende brevemente `Pi-Setup` e tenta la connessione. Se fallisce, l'hotspot viene riattivato immediatamente.

Scenario con Wi-Fi integrata e dongle USB:

```dotenv
HOTSPOT_INTERFACE=wlan0
CLIENT_WIFI_INTERFACE=wlan1
```

Con questa configurazione:

- `wlan0` mantiene attivo l'hotspot temporaneo `Pi-Setup`
- `wlan1` scansiona le reti e prova la connessione alla rete finale
- `wlan0` viene mostrata come riservata all'hotspot e non puo' essere scelta nel form client
- il telefono puo' restare collegato al portale mentre il Raspberry tenta la connessione con l'altra interfaccia
- quando wlan1 resta connessa per 30 secondi, l'hotspot temporaneo viene spento automaticamente

La versione `1.16.0` associa automaticamente i profili gestiti alla radio client rilevata. Con entrambe le radio li sposta su wlan1; se il dongle viene rimosso, li riporta su wlan0 al successivo avvio del servizio.

I nomi reali possono cambiare in base al dongle. Verifica sul Raspberry con:

```bash
nmcli device status
```

Con la sola wlan0, `CLIENT_WIFI_INTERFACE` e `WIFI_INTERFACE` restano i valori di fallback. La priorita' wlan1 viene applicata soltanto quando entrambe le radio sono rilevate.

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
- Wi-Fi client stabile
- LAN cablata stabile
- assenza completa di un percorso per raggiungere il portale

La Wi-Fi client resta distinta dalla LAN. La LAN non indica che la Wi-Fi sia configurata, ma rappresenta una via alternativa per amministrare il display. Per questo, quando Ethernet e' `connected` e possiede un IPv4 per 120 secondi, `Pi-Setup` viene spento. Non serve che la LAN abbia accesso a Internet.

Matrice recovery LAN/Wi-Fi:

- LAN stabile, Wi-Fi client connessa: `Pi-Setup` spento.
- LAN stabile, Wi-Fi client assente: `Pi-Setup` spento dopo 120 secondi; il portale resta raggiungibile via LAN.
- LAN appena collegata, Wi-Fi client assente: `Pi-Setup` resta attivo durante la verifica della stabilita'.
- LAN assente, wlan1 connessa: `Pi-Setup` spento dopo 30 secondi di connessione stabile.
- LAN assente, nessuna Wi-Fi client: `Pi-Setup` attivo dopo il tempo di recovery.
- LAN appena persa, nessuna Wi-Fi client: `Pi-Setup` viene riaperto dopo 20 secondi.

Valori consigliati:

- `BOOT_CONNECTION_GRACE_SECONDS=75`
- `RECONNECT_GRACE_SECONDS=45`
- `DISCONNECT_HOTSPOT_THRESHOLD_SECONDS=180`
- `HOTSPOT_COOLDOWN_SECONDS=90`
- `WIFI_CLIENT_STABLE_SECONDS=30`
- `LAN_STABLE_SECONDS=120`
- `NO_ACCESS_HOTSPOT_DELAY_SECONDS=20`
- `HOTSPOT_CLIENT_RETRY_INTERVAL_SECONDS=300`
- `HOTSPOT_MINIMUM_UP_SECONDS=30`
- `MANUAL_HOTSPOT_HOLD_SECONDS=600`

Interpretazione pratica:

- se il Raspberry si accende e non riesce a collegarsi, attende circa 75 secondi prima di riaprire `Pi-Setup`
- se la rete cade per pochi secondi o NetworkManager sta ancora tentando il recupero, l'hotspot non viene riattivato
- se la perdita supera circa 3 minuti, il Raspberry riattiva automaticamente l'hotspot
- con wlan1 connessa stabilmente, spegne l'hotspot dopo 30 secondi
- con LAN stabile, spegne l'hotspot dopo 2 minuti
- con la sola wlan0 e reti gestite salvate, ogni 5 minuti prova fino a due profili visibili, partendo dall'ultimo usato, e ripristina subito `Pi-Setup` se fallisce

Nella parte alta del portale, `Gestione automatica hotspot` mostra la motivazione dello stato e il tempo alla prossima azione. `Attiva 10 min` mantiene manualmente `Pi-Setup`; `Spegni` compare solo quando esiste un collegamento alternativo.

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

### 6.7 Interfacce di rete e indirizzi IP

Subito sotto il riepilogo iniziale, il portale mostra la sezione `Interfacce di rete e indirizzi IP`. In questo modo puoi controllare prima LAN, gateway, DNS e metodo IPv4, poi configurare il collegamento Wi-Fi.

Per ogni interfaccia vengono mostrati:

- nome interfaccia, ad esempio `eth0` o `wlan0`
- tipo e stato
- MAC address dell'interfaccia
- profilo NetworkManager attivo
- indirizzi IPv4 correnti
- gateway
- DNS
- metodo IPv4, ad esempio `auto` o `manual`

Dalla stessa sezione puoi usare `Modifica indirizzo IP` per configurare una interfaccia in:

- `DHCP automatico`
- `Indirizzo statico`

Per un indirizzo statico usa il formato:

```text
192.168.1.50/24
```

Gateway e DNS sono opzionali. I DNS possono essere separati da virgola, spazio o punto e virgola.

Il MAC address identifica la scheda di rete anche quando l'indirizzo IP cambia. `eth0` identifica la LAN cablata, `wlan0` la radio Wi-Fi integrata e `wlan1` il dongle USB quando presente. Se il dongle non e' collegato, wlan1 non viene mostrata.

Nota di sicurezza operativa: l'interfaccia che sta servendo l'hotspot temporaneo viene mostrata ma non puo' essere modificata finche' l'hotspot e' attivo. Questo evita di perdere il portale durante il setup. La funzione e' pensata soprattutto per configurare la LAN cablata, ad esempio `eth0`.

### 6.8 Stato rete per il software del display via TCP

VT Network Manager espone un server TCP di sola lettura su `127.0.0.1:6001`. Il collegamento e' disponibile soltanto sul dispositivo locale: un PC sulla LAN o un telefono collegato all'hotspot non possono aprire direttamente questa socket.

Il software del display puo' collegarsi alla porta `6001`. Riceve subito una riga UTF-8 terminata da `\n` e, finche' mantiene aperto il collegamento, un nuovo riepilogo ogni 30 secondi. Il server supporta piu' client contemporanei e non accetta comandi.

Esempio con Ethernet, hotspot su `wlan0` e client Wi-Fi su `wlan1`:

```text
internet: si, eth-ip: 192.168.1.14, eth-mode: DHCP, wi-fi enable: si, hot-spot: Pi-Setup / 192.168.4.1, wlan1: Azienda / 10.0.0.23
```

Esempio con Wi-Fi disabilitato:

```text
internet: si, eth-ip: 192.168.1.14, eth-mode: static, wi-fi enable: no, wi-fi off
```

Significato dei campi:

- `internet`: `si` solo quando NetworkManager verifica connettivita' completa; `no` per rete locale, captive portal, connettivita' limitata o assente
- `eth-ip`: indirizzo IPv4 attuale di `eth0`, senza prefisso CIDR; `n/d` se assente
- `eth-mode`: `DHCP`, `static` oppure `n/d`
- `wi-fi enable`: stato della radio Wi-Fi
- `hot-spot`: SSID hotspot e indirizzo del portale, quando l'hotspot e' attivo
- `wlan0`, `wlan1` e altre radio: SSID e IPv4 attuali; `n/d` indica un dato non disponibile o un'interfaccia non connessa
- le virgole presenti nei valori vengono convertite in spazi, perche' la virgola separa i campi

Le impostazioni sono:

```dotenv
NETWORK_STATUS_TCP_ENABLED=true
NETWORK_STATUS_TCP_PORT=6001
NETWORK_STATUS_TCP_INTERVAL_SECONDS=30
```

Per leggere il primo messaggio direttamente dal dispositivo:

```bash
python3 -c "import socket; s=socket.create_connection(('127.0.0.1', 6001)); print(s.recv(4096).decode().strip()); s.close()"
```

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

Il portale mostra prima la pagina di accesso. Inserisci la password `PORTAL_PASSWORD`. Usa il pulsante `Mostra` se vuoi controllare la password digitata prima di entrare.
In alto viene mostrata anche la versione applicazione: usala per verificare che il Raspberry stia eseguendo davvero l'ultima release installata.

Se hai usato l'installazione guidata e hai lasciato vuota la password portale, lo script ne ha generata una automaticamente e l'ha stampata alla fine dell'installazione. La puoi ritrovare o cambiare in:

```text
/etc/raspberry-wifi-portal/portal.env
```

### 7.3 Documenti PDF e guida rapida

Dopo il login, la sezione `Documenti utente` permette di consultare due documenti:

- `Guida rapida configurazione`, con i passaggi per LAN, Wi-Fi, radio, recovery e profili salvati
- `Scheda accesso`, con SSID hotspot, password, indirizzo, QR e MAC address del dispositivo

Per ogni documento sono disponibili:

- `Apri`, per consultare l'anteprima HTML e usare eventualmente la stampa del browser
- `Scarica PDF`, per generare direttamente un PDF A4 con impaginazione costante da telefono o PC

La scheda accesso e' una pagina semplice con:

- nome hotspot temporaneo
- password hotspot
- indirizzo portale, ad esempio `http://192.168.4.1`
- password portale
- QR del portale
- MAC address di eth0 e delle radio Wi-Fi presenti

Nel PDF della scheda sia l'indirizzo testuale sia il QR sono cliccabili. Il QR apre il portale dopo che il telefono o il PC e' stato collegato a `Pi-Setup`.
La sezione `Identificazione hardware` permette di riconoscere la scheda anche dopo un cambio IP. wlan1 compare soltanto quando il dongle USB Wi-Fi e' realmente collegato.

La scheda contiene password operative: stampala o inviala solo a persone autorizzate.

La guida rapida non incorpora temperatura, stato corrente di Pi-Setup o radio rilevate in quel momento. Questi dati cambiano durante il funzionamento e restano visibili nella dashboard. Il PDF contiene invece procedure, differenza tra wlan0 e wlan1 e regole di recovery, quindi puo' essere conservato e distribuito senza diventare subito obsoleto.

Flusso consigliato per la documentazione utente:

1. Premi `Scarica PDF` accanto a `Guida rapida configurazione` per consegnare le istruzioni operative.
2. Scarica `Scheda accesso` solo se devi consegnare anche SSID e password.
3. Verifica il link o tocca il QR nel PDF della scheda.
4. Conserva la scheda accesso con maggiore attenzione perche' contiene password.

La scheda accesso si trova in fondo alla pagina principale, dopo le sezioni operative di rete e Wi-Fi.

### 7.4 Temperatura del display e riavvio

Nella parte alta del portale viene mostrata la `Temperatura dispositivo`, letta dal sensore termico della scheda. Se il dato non e' disponibile, viene mostrato `n/d`.

Il portale usa soglie preventive pensate per un controller installato nel vano di un tabellone a LED:

- sotto `60 C`: `Normale`
- da `60 C` a `69.9 C`: `Sotto osservazione`; controlla prese d'aria e polvere
- da `70 C` a `79.9 C`: `Alta`; migliora ventilazione e raffreddamento
- da `80 C`: `Critica`; controlla subito ventole e flusso d'aria

Il Wi-Fi attivo puo' aumentare leggermente la temperatura, soprattutto con traffico continuo, ma normalmente non e' la fonte principale. In un tabellone chiuso incidono maggiormente temperatura ambiente, alimentatori LED, pannelli, carico del processore e ricambio d'aria.

La documentazione ufficiale indica che tra `80 C` e `85 C` il processore riduce progressivamente le prestazioni e a `85 C` applica una limitazione piu' forte. Per questo il portale segnala la condizione critica gia' da `80 C`.

Riferimento ufficiale: `https://www.raspberrypi.com/documentation/hardware/raspberrypi/power.html`

Il pulsante `Riavvia` esegue un reboot del Raspberry tramite `systemctl reboot`. Il comando e' disponibile solo dopo il login e richiede conferma nel browser.

### 7.5 Scansione reti Wi-Fi

Nella sezione `Reti visibili` premi `Scansiona reti`.

Il dispositivo usa sempre l'interfaccia radio selezionata nel form `Configura collegamento Wi-Fi` e aggiorna la lista senza ricaricare tutta la pagina. Toccando una rete rilevata, il campo `SSID` viene compilato automaticamente.

La lista mostra tutte le celle Wi-Fi rilevate da NetworkManager, anche quelle con segnale debole. Se piu' access point trasmettono lo stesso SSID, vengono mostrati separatamente con segnale, canale e BSSID quando disponibili. Quando l'elenco e' lungo, il riquadro resta compatto e puoi scorrere solo la lista delle reti senza perdere il resto della pagina.

Se la radio selezionata sta gestendo anche l'hotspot, per esempio `wlan0`, il portale adatta automaticamente il pulsante. Dal telefono chiede conferma prima di spegnere temporaneamente l'hotspot; dopo la scansione devi ricollegarti a `Pi-Setup` e aggiornare la pagina.

Se accedi al portale da un PC collegato via cavo LAN, lo stesso pulsante spegne l'hotspot per pochi secondi quando necessario, cerca le reti e aggiorna la lista restando raggiungibile tramite LAN.

Nota versione: dalla versione `1.16.0`, Pi-Setup viene spento automaticamente dopo una via di accesso stabile e i profili tornano su wlan0 se il dongle viene rimosso. Dalla versione `1.15.0`, con entrambe le radio presenti, wlan1 e' obbligatoria per il client.

Quando `Scansiona reti` deve interrompere temporaneamente l'hotspot:

1. il portale avvia la scansione in background
2. l'hotspot `Pi-Setup` viene spento per pochi secondi
3. il Raspberry cerca le reti Wi-Fi vicine
4. l'hotspot viene riattivato automaticamente
5. devi ricollegarti a `Pi-Setup` e aggiornare la pagina

Con due interfacce Wi-Fi, wlan1 viene selezionata automaticamente: non serve spegnere l'hotspot e l'avviso non compare. wlan0 resta visibile nello stato delle interfacce, ma nel form client e' disabilitata e indicata come riservata all'hotspot.

Per capire se hai una seconda interfaccia Wi-Fi, guarda il riquadro `Interfacce Wi-Fi` nella parte alta del portale. `wlan0 - Wi-Fi integrata` e' la radio della scheda. `wlan1 - dongle USB Wi-Fi` compare solo quando il dongle e' presente e rilevato. Se wlan1 non compare, non devi configurarla.

### 7.6 Configura collegamento Wi-Fi

La sezione `Configura collegamento Wi-Fi` raccoglie interfaccia radio, SSID, tipo di sicurezza e credenziali della rete finale.

Nel campo `Interfaccia radio` viene applicata questa regola:

- con la sola radio integrata viene usata `wlan0`
- con wlan0 e wlan1 presenti viene selezionata e accettata soltanto `wlan1 - dongle USB Wi-Fi`
- wlan0 resta visibile ma disabilitata come radio client, perche' e' riservata all'hotspot temporaneo

Per una rete WPA2/WPA3 Personal compila:

- `SSID`
- `Interfaccia radio`
- `Password Wi-Fi`
- `Sicurezza = WPA2/WPA3 Personal`

Puoi premere `Mostra` accanto alla password per verificare eventuali errori di battitura.

Poi premi `Salva e connetti`.

### 7.7 Configurazione di una rete aziendale 802.1X

Compila:

- `SSID`
- `Interfaccia radio`
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

Anche i campi password 802.1X hanno il pulsante `Mostra` per controllare cosa hai digitato.

### 7.8 Connessioni salvate dal portale

Nella sezione `Interfacce di rete e indirizzi IP` trovi anche `Connessioni salvate dal portale`.

Qui puoi eliminare profili Wi-Fi o LAN creati dal portale, cioe' quelli con nome `setup-*`, per poi ricrearli con nuovi parametri.

Per sicurezza il portale non mostra come eliminabili i profili di sistema non creati da lui, ad esempio profili `netplan-*`, e non permette di cancellare la connessione hotspot temporanea.

## 8. Cosa succede quando si preme "Salva e connetti"

1. Il Raspberry riceve i dati dal form.
2. Crea o aggiorna il profilo di rete.
3. Con la sola wlan0, disattiva l'hotspot per liberare la radio.
4. Con il dongle, mantiene Pi-Setup su wlan0 e usa wlan1 per il tentativo.
5. Tenta la connessione alla rete indicata.
6. Se wlan1 resta stabile per 30 secondi, spegne automaticamente Pi-Setup.
7. Se il tentativo fallisce, il portale resta o torna disponibile per un nuovo tentativo.

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

### Il dispositivo non si collega alla rete aziendale

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
Se il titolo e' ancora un vecchio default, come `Raspberry Pi Wi-Fi Setup`, `Wi-Fi Setup` o `Pi Network Manager`, l'installer lo aggiorna automaticamente a `VT Network Manager`. I titoli personalizzati non vengono sovrascritti.

Se dopo l'aggiornamento l'interfaccia sembra vecchia:

```bash
cd /opt/raspberry-wifi-portal
sudo ./scripts/install.sh --profile balanced
sudo systemctl restart raspberry-wifi-portal.service
```

Verifica nel portale la presenza di:

- badge `Versione`
- pulsante unico `Scansiona reti`
- pulsante `Riavvia`
- tasto `Esci`
- riquadro `Temperatura dispositivo` con stato termico
- riquadro `Interfacce Wi-Fi`
- campo `Interfaccia radio` nella configurazione Wi-Fi
- scheda `Radio Wi-Fi client` che mostra wlan1 come dongle prioritario quando presente
- sezione `Interfacce di rete e indirizzi IP` subito sotto il riepilogo iniziale
- lista `Reti visibili` compatta e scorrevole quando ci sono molte reti
- pulsante `Mostra` sui campi password
- sezione `Connessioni salvate dal portale`
- stato `Gestione automatica hotspot` con motivazione e conto alla rovescia
- comandi `Attiva 10 min` e `Spegni` per Pi-Setup
- sezione `Documenti utente` con download PDF diretto
- scheda accesso con link e QR cliccabili
- MAC address visibile per LAN e radio Wi-Fi
- guida rapida senza dati live di temperatura o stato corrente

## 12. Pubblicazione su GitHub

Per semplificare installazione e aggiornamenti sul Raspberry, e' consigliato pubblicare il progetto su GitHub come repository dedicato.

### 12.1 Inizializzazione locale

Da PowerShell:

```powershell
cd "C:\Users\Desktop-user\PROGETTI\SVILUPPO\Raspberry-wifi-portal"
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

### 12.4 Installazione dal repository GitHub sul dispositivo

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
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced
```

Il bootstrap scarica una copia pulita della branch `main`, reinstalla il servizio e conserva `/etc/raspberry-wifi-portal/portal.env`. Se hai ancora il clone originale, puoi in alternativa eseguire `git pull` in quella cartella e poi `sudo ./scripts/install.sh --profile balanced`. Non usare `git pull` dentro `/opt/raspberry-wifi-portal` quando la cartella e' stata creata dall'installer, perche' la copia installata non contiene la directory `.git`.

## 13. Riepilogo rapido

- installa il pacchetto sul Raspberry
- controlla `portal.env`
- collega il telefono a `Pi-Setup`
- apri `http://192.168.4.1`
- accedi con la password portale
- controlla il badge versione
- scarica il PDF `Guida rapida configurazione` per consegnare all'utente le istruzioni dell'interfaccia web
- scarica `Scheda accesso` se devi consegnare i dati di accesso e il QR cliccabile
- premi `Scansiona reti` per aggiornare le reti disponibili
- se sei collegato via LAN, il pulsante puo' spegnere temporaneamente l'hotspot senza perdere la pagina
- se sei collegato tramite hotspot sulla stessa radio, conferma la breve disconnessione e poi ricollegati
- inserisci i dati della rete finale
- attendi il tentativo di connessione
