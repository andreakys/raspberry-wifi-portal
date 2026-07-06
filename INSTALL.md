# Installazione rapida

Questa guida e' pensata per installare il portale direttamente su Raspberry Pi OS.

## Metodo consigliato: installazione guidata

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

Lo script chiede:

- SSID dell'hotspot temporaneo
- password dell'hotspot temporaneo
- password di accesso al portale, oppure la genera automaticamente se lasci vuoto
- porta HTTP del portale
- profilo recovery: `stable`, `balanced` o `unstable`

Alla fine collegati all'hotspot configurato e apri:

```text
http://192.168.4.1
```

Dopo il login il portale mostra anche due QR: uno per collegare rapidamente altri telefoni all'hotspot temporaneo e uno per aprire direttamente la pagina di configurazione.

## Installazione non interattiva

Utile per reinstallazioni o provisioning ripetibili:

```bash
sudo ./scripts/install.sh \
  --ssid Pi-Setup \
  --password 'ChangeMe123!' \
  --portal-password 'CambiaQuestaPassword!' \
  --profile balanced
```

Opzioni utili:

```text
--ssid VALUE        Imposta l'SSID dell'hotspot temporaneo
--password VALUE    Imposta la password dell'hotspot temporaneo
--portal-password VALUE
                    Imposta la password di accesso al portale web
--port VALUE        Imposta la porta HTTP del portale
--profile NAME      Applica stable, balanced o unstable
--skip-apt          Salta installazione pacchetti apt
--no-start          Non avvia subito il servizio
```

## One-line da GitHub

Dopo aver pubblicato il repository:

```bash
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced
```

Puoi aggiungere anche SSID, password hotspot e password portale:

```bash
curl -fsSL https://raw.githubusercontent.com/andreakys/raspberry-wifi-portal/main/scripts/bootstrap_from_github.sh | sudo bash -s -- https://github.com/andreakys/raspberry-wifi-portal.git main --ssid Pi-Setup --password 'ChangeMe123!' --portal-password 'CambiaQuestaPassword!' --profile balanced
```

## Aggiornamento

Se il progetto e' gia' installato in `/opt/raspberry-wifi-portal`, puoi rilanciare:

```bash
cd /opt/raspberry-wifi-portal
sudo ./scripts/install.sh --profile balanced
```

Il file `/etc/raspberry-wifi-portal/portal.env` viene conservato. Le opzioni passate allo script aggiornano solo i valori corrispondenti.

## Comandi di verifica

```bash
sudo systemctl status raspberry-wifi-portal.service
sudo journalctl -u raspberry-wifi-portal.service -f
```

## Rimozione

```bash
cd /opt/raspberry-wifi-portal
sudo ./scripts/uninstall.sh
```

La rimozione lascia intatto `/etc/raspberry-wifi-portal/portal.env`.
