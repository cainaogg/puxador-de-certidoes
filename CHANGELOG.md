# Histórico de mudanças

Este arquivo resume o que mudou em cada versão do **Puxador de Certidões**
(apenas a versão original em Python).

## [1.1.0] — 2026-07-09

### Novidades
- **Certidão de Falência (TJRS) automática.** Antes o programa abria o site para
  você preencher à mão. Agora ele consulta a razão social e o endereço do CNPJ
  numa base pública gratuita (BrasilAPI) e **preenche e emite sozinho** — o site
  do TJRS não tem captcha. Se a consulta pública falhar, cai no modo manual.
- **Não rebaixar o que ainda é válido.** Antes de baixar, o programa verifica se
  já existe aquela mesma certidão **ainda não vencida** e, se houver, pula (badge
  "Já válida"). Economiza tempo e captcha — inclusive nas manuais.
- **Autoria e contato** na tela de Ajuda.
- **Ícone próprio** do executável.

### Correções
- **CND Municipal e Comprovante ISS (Porto Alegre).** Em navegador corporativo
  que força o PDF a **baixar** por uma aba que abre e fecha na hora (ex.: Edge
  gerenciado de intranet), o programa não capturava o arquivo e dava erro
  (`TargetClosedError`). Agora captura o download em **qualquer aba** e também
  suporta a certidão que abre como PDF numa aba nova.

## [1.0.0] — 2026-07

### Base
- Baixa em lote as certidões de um ou mais CNPJ/CPF, renomeando cada arquivo com
  a data de validade e organizando por documento.
- Interface em **modo escuro** com badges de status, ícones, fonte Inter e
  abertura centralizada.
- Utilitários: escanear PDFs baixados, verificador de vencimentos e juntar PDFs.
- Resolve captchas com a extensão NopeCHA (modo assistido quando necessário).
