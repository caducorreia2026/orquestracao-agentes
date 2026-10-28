"""Ficheiro de configuração do pytest para os próprios testes do projeto."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
