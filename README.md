# Puxador de Certidões

Aplicativo desktop (Windows) que baixa, de uma vez, as certidões de um ou mais
CNPJ/CPF — renomeando cada arquivo com a data de validade e organizando por
documento. Interface em modo escuro (CustomTkinter).

> Este repositório contém **apenas a versão original em Python** (gratuita sempre
> que possível). A versão paga (API Infosimples), os executáveis e dados baixados
> **não** fazem parte do repositório.

O código do aplicativo está em [`Projeto Original/`](Projeto%20Original/).

## Preparação (uma vez)

Requer **Python 3.14+** no Windows. Depois de clonar, entre na pasta
`Projeto Original` e rode:

```
Preparar ambiente.bat
```

Esse script faz tudo: cria a venv, instala as dependências, **baixa a extensão
NopeCHA** (que resolve captchas) e o navegador do Playwright.

<details>
<summary>Ou manualmente (PowerShell)</summary>

```powershell
cd "Projeto Original"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python baixar_nopecha.py
python -m playwright install chromium
```
</details>

## Rodar

```
Iniciar.bat
```

(ou `.venv\Scripts\python.exe main.py`)

## Gerar o executável (opcional)

```
Gerar executavel.bat
```

Gera um `.exe` portátil único em `dist\`. Ele instala o PyInstaller se faltar e
embute a NopeCHA automaticamente (se você já a baixou).

## Estrutura

- `Projeto Original/certidoes/` — código (interface, motor, e um módulo por órgão).
- `Projeto Original/assets/` — ícones (PNG) e a fonte Inter usados na interface.
- `Projeto Original/baixar_nopecha.py` — baixa a extensão de captcha.
- `Projeto Original/main.py` — ponto de entrada.
- `assets/icone.ico` — ícone do executável (usado pelo `Gerar executavel.bat`).

## Observações importantes

- **Token da API não está aqui.** O programa lê um `config.json` local (ignorado
  pelo Git). A versão original funciona sem token; ele só é usado no modo API.
- **Extensão NopeCHA** não é versionada (`vendor/`, ignorada), mas o
  `baixar_nopecha.py` (rodado pelo `Preparar ambiente.bat`) baixa a versão pública
  oficial dela. Sem a extensão o programa continua funcionando: o captcha vira
  assistido (você o resolve na janela do navegador). A versão gratuita da NopeCHA
  funciona sem nenhuma chave.
- Vários órgãos bloqueiam automação (Receita, CNJ, TJRS): nesses casos o programa
  abre o site no navegador para emissão manual.
- Usa o **Edge/Chrome do sistema** para navegar; o Chromium do Playwright é só
  reserva.

## Autoria

Desenvolvido por **Cainã Gomes Süffert** — contato: caina@outlook.com
