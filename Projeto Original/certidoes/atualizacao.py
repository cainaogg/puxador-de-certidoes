"""Verifica e aplica atualizações do programa via GitHub Releases.

Usa o endpoint público da API (sem token) — funciona mesmo rodando do código,
só que aí não há `.exe` para substituir (ver `_congelado`).

Um `.exe` em execução não consegue se sobrescrever no Windows (o arquivo fica
travado), então a troca é feita por um `.bat` descartável: espera o processo
atual fechar, substitui o arquivo e, se pedido, reabre o programa.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from . import __version__, paths

REPO = "cainaogg/puxador-de-certidoes"
_API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
_HEADERS = {"User-Agent": "puxador-de-certidoes", "Accept": "application/vnd.github+json"}


def _congelado() -> bool:
    return bool(getattr(sys, "frozen", False))


def _versao_tupla(v: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", v)) or (0,)


def verificar(timeout: int = 8) -> Optional[dict]:
    """None se não há versão nova ou a checagem falhou (nunca levanta exceção
    — é best-effort, não pode travar a abertura do programa)."""
    try:
        req = urllib.request.Request(_API_LATEST, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None

    tag = (dados.get("tag_name") or "").strip()
    if not tag or _versao_tupla(tag) <= _versao_tupla(__version__):
        return None

    asset = next(
        (a for a in dados.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None
    )
    if not asset:
        return None

    return {
        "versao": tag.lstrip("vV"),
        "notas": (dados.get("body") or "").strip(),
        "url_release": dados.get("html_url", ""),
        "asset_url": asset["browser_download_url"],
        "asset_nome": asset["name"],
        "asset_tamanho": asset.get("size", 0),
    }


def baixar(asset_url: str, tamanho_esperado: int = 0,
           on_progresso: Optional[Callable[[int], None]] = None) -> Path:
    """Baixa o novo .exe para uma pasta temporária ao lado dos dados do programa.
    Levanta exceção se falhar ou o tamanho baixado não bater com o esperado."""
    destino = paths.base_dados() / "_atualizacao" / "Puxador de Certidoes (novo).exe"
    destino.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(asset_url, headers=_HEADERS)
    baixado = 0
    with urllib.request.urlopen(req, timeout=30) as resp, open(destino, "wb") as f:
        while True:
            bloco = resp.read(256 * 1024)
            if not bloco:
                break
            f.write(bloco)
            baixado += len(bloco)
            if on_progresso and tamanho_esperado:
                on_progresso(min(99, int(baixado * 100 / tamanho_esperado)))

    if tamanho_esperado and destino.stat().st_size != tamanho_esperado:
        destino.unlink(missing_ok=True)
        raise RuntimeError("Download incompleto (tamanho do arquivo não confere).")
    if on_progresso:
        on_progresso(100)
    return destino


def agendar_substituicao(novo_exe: Path, relancar: bool) -> None:
    """Gera e dispara um .bat desacoplado que espera este processo terminar,
    substitui o .exe atual pelo baixado e, se `relancar`, reabre o programa.
    Sem efeito fora do .exe (rodando do código não há o que substituir)."""
    if not _congelado():
        return
    atual = Path(sys.executable).resolve()
    pid = os.getpid()
    bat = novo_exe.parent / "aplicar_atualizacao.bat"
    # ponytail: o retry do "move" não tem limite de tentativas (fica tentando a
    # cada 1s pra sempre se o arquivo ficar travado). Nas travas que já vimos
    # neste projeto (antivírus escaneando o .exe recém-baixado) isso se resolve
    # em segundos; se algum dia virar problema de verdade, adicionar um teto
    # (ex.: desistir após 5 min e avisar o usuário via um arquivo de log).
    bat.write_text(
        "@echo off\n"
        ":espera\n"
        f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul\n'
        "if not errorlevel 1 (\n"
        "  timeout /t 1 /nobreak >nul\n"
        "  goto espera\n"
        ")\n"
        ":troca\n"
        f'move /y "{novo_exe}" "{atual}" >nul 2>nul\n'
        f'if exist "{novo_exe}" (\n'
        "  timeout /t 1 /nobreak >nul\n"
        "  goto troca\n"
        ")\n"
        + (f'start "" "{atual}"\n' if relancar else "")
        + 'rmdir /s /q "%~dp0" 2>nul\n',
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        # Só CREATE_NO_WINDOW (console real, oculto): combinado com DETACHED_PROCESS
        # (sem console nenhum) comandos do .bat que dependem de console, como
        # `timeout`, falham silenciosamente e o script morre sem terminar o serviço.
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
        cwd=str(atual.parent),
    )
