#!/usr/bin/env bash
# Script di installazione per Chess Tutor su macOS/Linux.
# Installa le dipendenze Python via Poetry e procura un eseguibile
# Stockfish locale nella cartella ./engines
set -euo pipefail

echo "== Chess Tutor - installazione locale =="

# 1. Verifica Python
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    echo "Python non trovato. Installa Python (vedi README.md) e riprova."
    exit 1
fi
echo "Python trovato: $($PYTHON_BIN --version)"

# 2. Verifica/installa Poetry
if ! command -v poetry &>/dev/null; then
    echo "Poetry non trovato, lo installo..."
    curl -sSL https://install.python-poetry.org | "$PYTHON_BIN" -
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "Poetry: $(poetry --version)"

# 3. Installa le dipendenze del progetto
poetry install

# 4. Installa Stockfish in locale (cartella ./engines)
mkdir -p engines
OS_NAME="$(uname -s)"

if [ -f engines/stockfish ]; then
    echo "Stockfish gia' presente in engines/stockfish"
else
    if [ "$OS_NAME" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            echo "Installo Stockfish con Homebrew..."
            brew install stockfish
            cp "$(command -v stockfish)" engines/stockfish
        else
            echo "Homebrew non trovato."
            echo "Installa Homebrew (https://brew.sh) e rilancia questo script,"
            echo "oppure scarica Stockfish da https://stockfishchess.org/download/"
            echo "e copia l'eseguibile in engines/stockfish"
            exit 1
        fi
    elif [ "$OS_NAME" = "Linux" ]; then
        if command -v apt-get &>/dev/null; then
            echo "Installo Stockfish con apt..."
            sudo apt-get update && sudo apt-get install -y stockfish
            cp "$(command -v stockfish)" engines/stockfish
        elif command -v dnf &>/dev/null; then
            echo "Installo Stockfish con dnf..."
            sudo dnf install -y stockfish
            cp "$(command -v stockfish)" engines/stockfish
        elif command -v pacman &>/dev/null; then
            echo "Installo Stockfish con pacman..."
            sudo pacman -Sy --noconfirm stockfish
            cp "$(command -v stockfish)" engines/stockfish
        else
            echo "Gestore pacchetti non riconosciuto."
            echo "Scarica Stockfish da https://stockfishchess.org/download/"
            echo "e copia l'eseguibile in engines/stockfish"
            exit 1
        fi
    else
        echo "Sistema operativo non gestito automaticamente: $OS_NAME"
        exit 1
    fi
    chmod +x engines/stockfish
fi

echo ""
echo "Installazione completata!"
echo "Avvia il tutor con:  poetry run chess-tutor"
