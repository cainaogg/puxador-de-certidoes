# Puxador de Certidões

Aplicativo desktop (Windows) que baixa, de uma vez, as certidões de um ou mais
CNPJ/CPF — renomeando cada arquivo com a data de validade e organizando por
documento. A interface abre em uma janela de aplicativo do **Edge do Windows**,
com tema claro/escuro e cor de destaque configurável.

> Este repositório contém **apenas a versão original em Python** (gratuita sempre
> que possível). A versão paga (API Infosimples), os executáveis e dados baixados
> **não** fazem parte do repositório.

O código do aplicativo está em [`Projeto Original/`](Projeto%20Original/).

## Baixar (pronto para usar)

Não precisa instalar nada nem programar: baixe o `.exe` mais recente na página de
**[Releases](../../releases/latest)** e é só abrir. Portátil, roda direto.

> Na primeira abertura ele leva alguns segundos para carregar (o executável se
> descompacta a cada início) — isso é normal.

## Manual / Tutorial

Um guia ilustrado passo a passo (pensado para quem não é técnico) está em
[`docs/index.html`](docs/index.html). Ele mostra a tela do programa, como digitar
os documentos, o que são as certidões manuais (captcha) e onde ficam os arquivos.

Para publicá-lo como página (GitHub Pages): Settings → Pages → Source **main** /
pasta **/docs**. A página fica em `https://<usuario>.github.io/<repo>/`.

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

## Rodar (a partir do código)

Interface atual (janela de app do Edge):

```
interface_web\Ver interface nova (teste).bat
```

<details>
<summary>Interface clássica (CustomTkinter)</summary>

```
Iniciar.bat
```
(ou `.venv\Scripts\python.exe main.py`)
</details>

## Gerar o executável (opcional)

```
interface_web\Gerar executavel (nova interface).bat
```

Gera um `.exe` portátil único em `dist\` (a interface nova, em modo-app do Edge).
Instala o PyInstaller se faltar e embute a NopeCHA automaticamente (se você já a
baixou). O `Gerar executavel.bat` da raiz ainda gera a interface clássica.

## Estrutura

- `Projeto Original/certidoes/` — código (motor e um módulo por órgão; o motor é
  compartilhado pelas duas interfaces).
- `Projeto Original/interface_web/` — interface atual (HTML/CSS/JS + `main_web.py`,
  ponte via eel).
- `Projeto Original/assets/` — ícones (PNG) e a fonte Inter usados na interface.
- `Projeto Original/baixar_nopecha.py` — baixa a extensão de captcha.
- `Projeto Original/main.py` — ponto de entrada da interface clássica.
- `assets/icone.ico` — ícone do executável.

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
