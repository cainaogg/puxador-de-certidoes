# Puxador de Certidões

Aplicativo desktop (Windows) que baixa, de uma vez, as certidões de um ou mais
CNPJ/CPF — renomeando cada arquivo com a data de validade e organizando por
documento. Interface em modo escuro (CustomTkinter).

> Este repositório contém **apenas a versão original em Python** (gratuita sempre
> que possível). A versão paga (API Infosimples), os executáveis e dados baixados
> **não** fazem parte do repositório.

O código do aplicativo está em [`Projeto Original/`](Projeto%20Original/).

## Como rodar (a partir do código)

Requer **Python 3.14+** no Windows.

```powershell
cd "Projeto Original"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

## Estrutura

- `Projeto Original/certidoes/` — código (interface, motor, e um módulo por órgão).
- `Projeto Original/assets/` — ícones (PNG) e a fonte Inter usados na interface.
- `Projeto Original/main.py` — ponto de entrada.
- `assets/icone.ico` — ícone do executável (usado pelo `Gerar executavel.bat`).

## Observações importantes

- **Token da API não está aqui.** O programa lê um `config.json` local (ignorado
  pelo Git). A versão original funciona sem token; ele só é usado no modo API.
- **Extensão NopeCHA não está incluída** (`vendor/`, ignorada). Ela resolve alguns
  captchas automaticamente; sem ela, o captcha é resolvido de forma assistida
  (você clica na janela do navegador). Para adicioná-la, baixe a extensão do
  Chromium da NopeCHA e extraia em `Projeto Original/vendor/nopecha_ext`.
- Vários órgãos bloqueiam automação (Receita, CNJ, TJRS): nesses casos o programa
  abre o site no navegador para emissão manual.

## Autoria

Desenvolvido por **Cainã Gomes Süffert** — contato: caina@outlook.com
