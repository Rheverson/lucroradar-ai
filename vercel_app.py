"""Ponto de entrada da função Python na Vercel (projeto "api").

A Vercel procura o módulo a partir da raiz do projeto; o código da API vive em
services/api, então o caminho é adicionado aqui antes de importar a aplicação.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "services" / "api"))

from lucroradar_api.main import app  # noqa: E402

__all__ = ["app"]
