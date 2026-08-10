# Script di installazione per Chess Tutor su Windows.
# Installa le dipendenze Python via Poetry.
# Il download di Stockfish per Windows va completato a mano
# (il nome dell'archivio cambia ad ogni release, non e' automatizzabile in modo affidabile).

Write-Host "== Chess Tutor - installazione locale (Windows) =="

# 1. Verifica Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "Python non trovato. Installalo da https://www.python.org/downloads/ (spunta 'Add to PATH') e riprova."
    exit 1
}
Write-Host "Python trovato: $(python --version)"

# 2. Verifica/installa Poetry
$poetryCmd = Get-Command poetry -ErrorAction SilentlyContinue
if (-not $poetryCmd) {
    Write-Host "Poetry non trovato, lo installo..."
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
    Write-Host "Riapri il terminale se 'poetry' non viene riconosciuto subito dopo."
}

# 3. Installa le dipendenze del progetto
poetry install

# 4. Stockfish
New-Item -ItemType Directory -Force -Path "engines" | Out-Null
if (Test-Path "engines\stockfish.exe") {
    Write-Host "Stockfish gia' presente in engines\stockfish.exe"
} else {
    Write-Host ""
    Write-Host "Passo manuale richiesto:"
    Write-Host "1. Apri https://stockfishchess.org/download/"
    Write-Host "2. Scarica la build Windows (es. 'AVX2' se la CPU e' recente)"
    Write-Host "3. Estrai l'archivio ed estrai il file stockfish-windows-*.exe"
    Write-Host "4. Rinominalo stockfish.exe e spostalo nella cartella .\engines\"
}

Write-Host ""
Write-Host "Installazione completata! Avvia con:  poetry run chess-tutor"
