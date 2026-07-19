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
    # Cor de destaque da interface nova (webview). Um dos 6 hex do seletor.
    "accent": "#3B82F6",
    # Tema da interface nova: "dark" (padrão) ou "light".
    "tema": "dark",
    # Perfis de download: definem quais certidões os chips CNPJ/CPF marcam.
    # "Padrão" é fixo (computado na interface) e NÃO fica aqui — só os perfis
    # criados pelo usuário: {nome: {"cnpj": [ids], "cpf": [ids]}}.
    "perfis": {},
    "perfil_ativo": "Padrão",
    # Notificações de vencimento (sino no Painel): chaves (caminho+data) já vistas
    # (some o badge, mas continua na lista) e já excluídas (some da lista).
    "notif_vistas": [],
    "notif_excluidas": [],
    # Nomenclatura dos documentos: {id do módulo: nome personalizado}. Vazio ou
    # ausente = usa o nome padrão do programa (nome_documento(modulo.nome)).
    "nomes_personalizados": {},
    # Atualização já baixada, aguardando ser aplicada ao fechar o programa (ou
    # imediatamente, se o usuário pediu "Reiniciar"): {"caminho", "versao",
    # "relancar"}. None = nenhuma atualização pendente.
    "atualizacao_pendente": None,
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
