# Chess Tutor locale (Stockfish + Python, offline)

App desktop per giocare a scacchi contro il computer con difficolta'
regolabile e un "tutor" (Stockfish) che, mossa dopo mossa, mostra la
valutazione della posizione e la mossa migliore. Funziona interamente
in locale, senza bisogno di connessione internet una volta installata.

---

## 0. Requisiti e scelte fatte

- **Python**: consigliato **3.12** (vedi punto 1 sul perche' non l'ultimissima versione).
- **Stockfish**: motore scacchistico open source, installato in locale.
- **Poetry**: gestione dipendenze e ambiente virtuale.
- **GUI**: Tkinter (incluso in Python, nessuna libreria grafica esterna da installare).
- **python-chess**: libreria per regole del gioco, notazione, comunicazione UCI con Stockfish.

---

## 1. Installazione di Python

Non conviene sempre installare l'ultimissima versione appena uscita: alcune
librerie (compresa Poetry o suoi plugin) a volte impiegano qualche settimana
per certificare la compatibilita'. Il consiglio pratico e':

- Usa **l'ultima versione stabile della serie precedente a quella "nuovissima"**,
  oggi tipicamente **Python 3.12.x**. E' compatibile al 100% con `python-chess`
  e con Poetry, quindi elimina rischi inutili.
- Se vuoi comunque provare l'ultima versione disponibile, non c'e' controindicazione
  seria per questo progetto (usa solo libreria standard + `python-chess`): puoi
  installare l'ultima e, se qualcosa non va con Poetry, ripiegare su 3.12.

### Come installare Python in modo pulito (consigliato: `pyenv`)

Usare `pyenv` (o `pyenv-win` su Windows) ti permette di avere piu' versioni di
Python installate senza sporcare il sistema, e di scegliere quella del progetto.

**macOS/Linux:**
```bash
curl https://pyenv.run | bash
# poi aggiungi pyenv al tuo shell profile (~/.bashrc o ~/.zshrc), come indicato
# a fine installazione, e riapri il terminale

pyenv install 3.12.6
pyenv local 3.12.6   # da eseguire dentro la cartella del progetto
python --version     # deve mostrare 3.12.6
```

**Windows (PowerShell):**
```powershell
# pyenv-win via pip, oppure installer da https://github.com/pyenv-win/pyenv-win
pip install pyenv-win --target $HOME\.pyenv
# aggiungi $HOME\.pyenv\pyenv-win\bin e \shims al PATH, poi riapri il terminale

pyenv install 3.12.6
pyenv local 3.12.6
```

In alternativa piu' semplice (se non vuoi usare pyenv): scarica l'installer
ufficiale da https://www.python.org/downloads/ (versione 3.12.x), e durante
l'installazione su Windows **spunta "Add python.exe to PATH"**.

---

## 2. Installazione di Stockfish in locale

Lo script `install.sh` (macOS/Linux) o `install.ps1` (Windows), forniti in
questa repo, lo fanno per te automaticamente dove possibile (vedi punto 4).
Se preferisci farlo a mano:

- **macOS** (con Homebrew): `brew install stockfish`
- **Linux (Debian/Ubuntu)**: `sudo apt install stockfish`
- **Linux (Fedora)**: `sudo dnf install stockfish`
- **Windows**: scarica l'eseguibile da https://stockfishchess.org/download/
  (build ufficiali, gratuite), estrai l'archivio e tieni da parte il percorso
  del file `stockfish-windows-*.exe`.

Il progetto si aspetta di trovare l'eseguibile in una cartella `engines/`
dentro la repo (`engines/stockfish` su macOS/Linux, `engines/stockfish.exe`
su Windows), oppure puoi indicare un percorso qualsiasi con la variabile
d'ambiente `STOCKFISH_PATH`.

---

## 3. Creazione della repo GitHub, collegamento a VS Code, ambiente Poetry

### 3.1 Crea la repo su GitHub
1. Vai su https://github.com/new
2. Nome repo, es. `chess-tutor`, visibilita' a piacere, **non** aggiungere
   README/gitignore/licenza automatici (li abbiamo gia' pronti qui sotto).
3. Crea la repo.

### 3.2 Prepara la cartella in locale e collegala
```bash
mkdir chess-tutor
cd chess-tutor
git init
git remote add origin https://github.com/<tuo-utente>/chess-tutor.git
```
Copia dentro questa cartella tutti i file dello scaffold che trovi allegato
a questo messaggio (struttura descritta al punto 5), poi:
```bash
git add .
git commit -m "Setup iniziale progetto chess tutor"
git branch -M main
git push -u origin main
```

### 3.3 Apri il progetto in VS Code
```bash
code .
```
Installa (se non li hai gia') questi due estensioni consigliate:
- **Python** (Microsoft)
- **Poetry** o almeno assicurati che VS Code rilevi l'interprete Poetry
  (dopo aver creato l'ambiente, in basso a destra in VS Code clicca sulla
  versione di Python e scegli l'interprete dentro `.venv` del progetto,
  oppure lascia che VS Code lo rilevi da solo tramite `poetry env info`).

### 3.4 Installa Poetry (se non l'hai gia')
```bash
curl -sSL https://install.python-poetry.org | python3 -
```
Verifica: `poetry --version`

Configura Poetry per creare il virtualenv **dentro** la cartella del progetto
(comodo per farlo riconoscere subito da VS Code):
```bash
poetry config virtualenvs.in-project true
```

### 3.5 Crea l'ambiente virtuale e installa le dipendenze
Dalla cartella del progetto (dove sta `pyproject.toml`):
```bash
poetry install
```
Questo crea `.venv/` dentro il progetto e installa `python-chess` e le
dipendenze di sviluppo (pytest, black).

Per lanciare comandi dentro l'ambiente:
```bash
poetry shell        # apre una shell con l'ambiente attivo
# oppure, senza attivare una shell dedicata:
poetry run chess-tutor
```

---

## 4. Script di installazione unico (per chi clona la repo)

Chi clona la repo deve poter fare tutto con un solo comando. Sono inclusi
due script:

- **`install.sh`** per macOS/Linux
- **`install.ps1`** per Windows (PowerShell)

Cosa fanno:
1. Verificano che Python sia installato.
2. Installano Poetry se manca.
3. Eseguono `poetry install` (dipendenze + ambiente virtuale).
4. Installano Stockfish con il gestore pacchetti del sistema (apt/brew) e
   copiano l'eseguibile dentro `engines/` del progetto. Su Windows, dato che
   Stockfish non ha un installer scriptabile in modo affidabile (il nome del
   file cambia a ogni release), lo script ti guida al download manuale in
   pochi click.

Uso, dopo aver clonato la repo:

**macOS/Linux:**
```bash
chmod +x install.sh
./install.sh
```

**Windows (PowerShell, eseguito come utente):**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

Al termine, per giocare:
```bash
poetry run chess-tutor
```

---

## 5. Struttura della repo

```
chess-tutor/
├── README.md
├── pyproject.toml          # dipendenze e script Poetry
├── install.sh               # installer macOS/Linux
├── install.ps1               # installer Windows
├── .gitignore
├── engines/                 # dove finisce l'eseguibile stockfish (non versionato)
├── src/
│   └── chess_tutor/
│       ├── __init__.py
│       ├── __main__.py       # punto di ingresso ("poetry run chess-tutor")
│       ├── config.py         # trova il percorso di stockfish
│       ├── engine_manager.py # comunicazione UCI con Stockfish (avversario + tutor)
│       └── gui.py            # interfaccia grafica Tkinter
└── tests/
    └── test_basic.py
```

---

## 6. Come funziona l'app (GUI, difficolta', tutor)

- **Scacchiera cliccabile**: clic su un pezzo per selezionarlo (le mosse
  legali vengono evidenziate), secondo clic sulla casella di destinazione
  per muovere.
- **Difficolta' regolabile**: slider da 0 a 20, mappato sul parametro UCI
  `Skill Level` di Stockfish (0 = molto debole, 20 = piena forza).
- **Tutor**: dopo ogni mossa (tua o del motore), il pannello laterale mostra
  la valutazione della posizione in "pedoni" (es. `+1.35` = il Bianco è
  avanti di circa un pedone e un terzo) e la mossa che Stockfish giudica
  migliore da quella posizione, calcolata **sempre a piena forza**
  indipendentemente dalla difficolta' dell'avversario, cosi' i consigli
  restano sempre affidabili.
- **Suggerisci mossa (hint)**: mostra subito la mossa migliore nella
  posizione corrente, utile mentre stai decidendo cosa giocare.
- **Annulla ultima mossa / Nuova partita**: controlli base di gestione partita.

### Possibili estensioni future
- Evidenziare sulla scacchiera, dopo ogni tua mossa, quanto hai perso in
  centipedoni rispetto alla mossa migliore (classificazione tipo
  "ottima / imprecisione / errore / svista", come fanno i siti online).
- Salvare le partite in formato PGN per rivederle.
- Aggiungere una barra di valutazione grafica invece del solo numero.
- Multi-tempo di pensiero del motore in base alla difficolta' (oggi e'
  fisso, solo la forza cambia).

---

## 7. Troubleshooting rapido

- **`ModuleNotFoundError: tkinter`** (tipico su Linux): installa il pacchetto
  di sistema, es. `sudo apt install python3-tk`.
- **Stockfish non trovato**: verifica che esista `engines/stockfish` (o
  `.exe` su Windows) oppure imposta `STOCKFISH_PATH` con il percorso completo.
- **VS Code non vede l'ambiente Poetry**: esegui `poetry env info --path`,
  copia il percorso mostrato e selezionalo manualmente come interprete
  Python in VS Code (Ctrl+Shift+P → "Python: Select Interpreter").
