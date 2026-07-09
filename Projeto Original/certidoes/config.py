"""Configurações do programa, salvas em config.json (na pasta do projeto)."""

from __future__ import annotations

import json

from . import paths

ARQUIVO = paths.base_dados() / "config.json"

PADRAO = {
    # Como emitir a Receita Federal: "navegador" (abre o seu navegador para emitir
    # manualmente) ou "api" (baixa automaticamente pela API da Infosimples).
    "receita_modo": "navegador",
    "infosimples_token": "",
}


def carregar() -> dict:
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        return {**PADRAO, **dados}
    except Exception:
        return dict(PADRAO)


def salvar(**alteracoes) -> None:
    atual = carregar()
    atual.update(alteracoes)
    ARQUIVO.write_text(
        json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8"
    )
