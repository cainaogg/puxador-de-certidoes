# Baixador de Certidões — CPF/CNPJ

Programa de desktop (Windows) que recebe **um** CPF ou CNPJ e baixa as certidões
que normalmente você emitiria manualmente em vários sites de órgãos públicos.

## Como funciona

- Você digita o CPF/CNPJ uma única vez.
- O programa detecta automaticamente se é CPF ou CNPJ e habilita só as certidões compatíveis.
- A tela lista as certidões em dois grupos:
  - **Automáticas (sem CAPTCHA)** — baixadas sozinhas.
  - **Exigem CAPTCHA (modo assistido)** — o programa abre o site, preenche tudo e
    **para** para você resolver o CAPTCHA; o download é capturado em seguida.
- Há um "Selecionar todas" no topo e o status de cada certidão por linha.
- Os arquivos vão para `downloads/<documento>/<data>/`.

## Estado atual (MVP)

Implementadas e funcionais:

| Certidão | Órgão | CAPTCHA | Situação |
| --- | --- | --- | --- |
| Certificado de Regularidade do FGTS (CRF) | Caixa | não | ✅ verificado (certificado real, A4, com logo) |
| Certidão Negativa de Débitos Trabalhistas (CNDT) | TST | **sim** (assistido) | ✅ verificado (negativa real) |
| Certidão de Licitantes Inidôneos | TCU | não (ALTCHA auto) | ✅ verificado (negativa real) |
| Consulta Consolidada de Pessoa Jurídica | TCU | não | ✅ verificado (relatório consolidado real) |
| Certidão de Situação Fiscal | SEFAZ-RS | não (ALTCHA auto) | ✅ verificado (negativa real) |
| Certidão de Débitos Tributários (POA) | Procempa/SIAT | reCAPTCHA (NopeCHA auto) | ✅ verificado (negativa real) |
| Comprovante de Inscrição no ISS (POA) | Procempa/SIAT | reCAPTCHA (NopeCHA auto) | ✅ verificado (comprovante real) |
| Certidão Negativa Correcional (CGU) | CGU | hCaptcha imagens (assistido) | ✅ verificado (negativa real) |
| Certidão Negativa da Receita Federal | RFB/PGFN | hCaptcha Enterprise | ⚠ **manual** (bloqueia automação) |

> **Solver de captcha (NopeCHA):** o motor carrega a extensão NopeCHA (em
> `vendor/nopecha_ext`), que resolve **reCAPTCHA/hCaptcha comuns automaticamente**
> (grátis, 100/dia por IP). Funciona na POA (reCAPTCHA). **Não** resolve hCaptcha
> Enterprise (CGU). Se a pasta da extensão não existir, o programa abre sem ela.

As outras 2 certidões da lista (CNJ Improbidade e TJRS Falência) ainda aparecem
como **"(em breve)"** — captcha a confirmar no mapeamento.

> **Modo discreto (anti-bot):** o motor injeta um script que oculta a marca de
> automação (`navigator.webdriver`) e usa `--disable-blink-features=AutomationControlled`.
> Sem isso, a CGU bloqueia com erro 403 (CloudFront).

> **Navegador:** o programa usa o **Microsoft Edge/Chrome já instalado** no
> Windows (não o Chromium embutido do Playwright, que dá erro *side-by-side*
> nesta máquina). A ordem tentada é Edge → Chrome → embutido.

> **Anti-robô:** o site do FGTS bloqueia navegador invisível (headless). Por
> isso o programa sempre roda com o navegador **visível**.

> ⚠️ Quando algo falhar, o programa salva uma **screenshot do erro** em
> `downloads/<doc>/<data>/erro_<id>.png` — útil para recalibrar os seletores.

## Instalação

Já existe um ambiente virtual em `.venv` com tudo instalado. Para recriar do zero:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Executar

```powershell
.\.venv\Scripts\python.exe main.py
```

## Rodar os testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Estrutura

```
main.py                      # ponto de entrada (abre a janela)
certidoes/
  app.py                     # interface gráfica (CustomTkinter)
  engine.py                  # motor Playwright (roda os módulos em thread separada)
  base.py                    # contratos: Status, Resultado, Contexto, ModuloCertidao
  documento.py               # validação/detecção de CPF e CNPJ
  registry.py                # catálogo das 11 certidões
  modulos/
    receita_federal.py
    cndt.py                  # modo assistido (CAPTCHA)
    fgts.py
tests/
  test_documento.py
downloads/                   # saída (criada em tempo de execução)
```

## Como adicionar uma nova certidão

1. Crie `certidoes/modulos/<nome>.py` com uma classe que herda de `ModuloCertidao`
   e implementa `executar(self, page, ctx)`.
2. Defina `id`, `nome`, `url`, `requer_captcha`, `aceita` e `implementado = True`.
3. Registre a instância em `certidoes/registry.py` (substituindo o `_planejado(...)`).
4. Use `ctx.aguardar_captcha(...)` + `page.expect_download(...)` se o site tiver CAPTCHA,
   ou `salvar_pagina_como_pdf(page, ctx.caminho_pdf(self.id))` para imprimir a tela em PDF.
```
