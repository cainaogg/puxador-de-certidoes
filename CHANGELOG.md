# Histórico de mudanças

Este arquivo resume o que mudou em cada versão do **Puxador de Certidões**
(apenas a versão original em Python).

## [2.0.0] — 2026-07-13

### Nova interface
- **Interface visual reformulada.** A tela foi redesenhada do zero (HTML/CSS
  modernos), fiel ao design: tipografia, ícones, espaçamentos e a lista de
  certidões com visual mais limpo. O motor que baixa as certidões é o mesmo —
  só a aparência e a usabilidade mudaram.
- **Tema claro/escuro.** Botão sol/lua no menu lateral alterna entre os dois
  temas; a escolha fica salva.
- **Cor de destaque personalizável.** Em Configurações há um seletor com 6
  cores para a cor de destaque da interface.
- **Botão do site em cada certidão.** Cada linha da lista tem um botão que abre
  o site oficial daquela certidão no navegador — útil para as que exigem
  emissão manual.
- **Cores no verificador de validade.** Ao escanear os vencimentos, cada
  documento aparece colorido: verde (ok), amarelo (vence em até 7 dias) e
  vermelho (vencido).

### Correções
- **Botão "Abrir pasta" volta a funcionar no executável.** No .exe ele não abria
  a pasta de downloads; agora abre pelo Explorer do Windows.
- **Importa o Cartão CNPJ sozinho.** O novo Cartão CNPJ da Receita imprime o
  número com espaços, o que impedia o reconhecimento na pasta Downloads. Agora
  ele é reconhecido pelos dígitos, movido e renomeado como as demais.

### Observações
- A interface abre em uma **janela de aplicativo do Edge do Windows**,
  independente do seu navegador padrão (mesmo que use Chrome ou Firefox).
- Na **primeira abertura** o programa leva alguns segundos para carregar (o
  executável se descompacta a cada início) — isso é normal.

## [1.1.0] — 2026-07-09

### Novidades
- **Sócio majoritário na pasta do CNPJ.** Um CPF colocado logo abaixo de um CNPJ
  na lista é tratado como sócio daquela empresa: todas as certidões dele (as
  automáticas e as importadas) vão para a MESMA pasta do CNPJ.
- **Importa sozinho os documentos da Receita.** Cartão CNPJ e CND Federal abrem no
  seu navegador (a Receita bloqueia automação). Agora, quando você os baixa, o
  programa os encontra na pasta Downloads pelo conteúdo (reconhece a certidão e o
  CNPJ/CPF dentro dela), move para a pasta certa e renomeia com a validade — sem
  clicar em nada. Só toca em PDFs recentes, reconhecidos e que casam com a sessão.
- **Certidão de Improbidade (CNJ) automática.** Antes abria o site para
  preenchimento manual. Agora preenche e emite sozinho; o reCAPTCHA é resolvido
  pela NopeCHA (ou por você, no modo assistido). O nome do CNPJ vem da base
  pública; para **CPF** (sócio majoritário), informe o nome na mesma linha do CPF
  (ex.: `123.456.789-00 FULANO DE TAL`).
- **CND Trabalhista (CNDT/TST) com captcha automático.** O captcha de texto em
  imagem do TST passa a ser resolvido **sozinho** (OCR offline e gratuito, com
  novas tentativas se errar). Antes era assistido (você digitava). Se o OCR não
  estiver disponível, cai no modo assistido.
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
- **TCU (Inidôneos, Contas Julgadas, Consulta Consolidada): novas tentativas.**
  Em rede lenta/proxy (ex.: trabalho), a plataforma do TCU às vezes falha de forma
  intermitente ("captcha expirou", "erro no serviço", "não localizado", ou fica
  processando). Agora o programa **tenta de novo automaticamente** (recarrega e
  recalcula o ALTCHA), o que costuma resolver esses erros passageiros.
- **Abas extras fechadas.** Depois de baixar/emitir uma certidão que abre em nova
  aba (ex.: TJRS), o programa fecha as abas/popups que sobraram.
- **CND Municipal e Comprovante ISS (Porto Alegre).** Em navegador corporativo
  que força o PDF a **baixar** por uma aba que abre e fecha na hora (ex.: Edge
  gerenciado de intranet), o programa não capturava o arquivo e dava erro
  (`TargetClosedError`). Agora captura o download em **qualquer aba** e também
  suporta a certidão que abre como PDF numa aba nova.

### Desempenho
- **Início mais rápido.** Antes, ao começar um CNPJ, o programa ficava parado
  (às vezes >1 min, em rede lenta/proxy) consultando a razão social só para
  nomear a pasta. Agora a pasta é criada na hora (com o número) e o download
  começa imediatamente; o nome ("NOME - número") é aplicado no fim. O tempo
  limite da consulta também caiu de 30s para 12s por fonte.

## [1.0.0] — 2026-07

### Base
- Baixa em lote as certidões de um ou mais CNPJ/CPF, renomeando cada arquivo com
  a data de validade e organizando por documento.
- Interface em **modo escuro** com badges de status, ícones, fonte Inter e
  abertura centralizada.
- Utilitários: escanear PDFs baixados, verificador de vencimentos e juntar PDFs.
- Resolve captchas com a extensão NopeCHA (modo assistido quando necessário).
