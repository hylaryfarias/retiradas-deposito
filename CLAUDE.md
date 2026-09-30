# Relatório diário de vendas — Grupo Ragga

São **dois envios** por dia, e cada um tem seu script:

| Envio | Quando | Script | Saída |
|---|---|---|---|
| **1. Venda bruta + entrada prevista** | de manhã, quando ela manda os PDFs | `gerar_relatorio.py` | quadrinho PNG + `texto_whatsapp.txt` |
| **2. Entradas do dia (recebimento real)** | depois, quando ela passa o que entrou | `gerar_entradas.py` | `texto_entradas.txt` |

O envio 2 é o **complemento** do 1: ele confronta o que entrou de verdade
contra a previsão que foi mandada no envio 1.

# Envio 1 — venda bruta e entrada prevista

## O que fazer quando o PDF chegar

```bash
python3 gerar_relatorio.py <pdf-do-periodo> --mes-anterior <pdf-de-um-mes-atras> --saida saida
```

Ela manda **dois** PDFs: o do período atual e o do **mesmo intervalo do mês
anterior** (ex.: 04-07/09 + 04-07/08). O segundo serve só para o voucher D+30.

Isso entrega os três arquivos em `saida/`:

| Arquivo | O que é |
|---|---|
| `vendas_card.png` | o quadrinho roxo pronto para o print do WhatsApp |
| `texto_whatsapp.txt` | o texto de venda bruta + entrada prevista |
| `formas_agrupadas.csv` | a tabela em CSV (`;` e decimal BR, abre no Excel) |

Depois: mandar o PNG e o texto no chat, com a tabela também em markdown na
resposta, e o fechamento (soma dos dias) conferido.

Flags úteis:

- `--dia 04/09/2026` — usa só aquele dia. **Sem a flag, todos os dias do PDF
  são somados num bloco único** (foi o que ela pediu: "em um dia só").
- `--mes-anterior <pdf>` — PDF do mesmo intervalo do mês anterior, de onde sai
  o voucher D+30. Sem ele, a parcela de voucher não entra.
- `--dia-previsto dd/mm/aaaa` — força a data da entrada prevista (o padrão é o
  dia seguinte ao último dia do relatório, já tratando virada de mês).
- `--b2b 1177.80` — valor do B2B da iKI, quando a base existir.
- `--a-prazo outro.csv` — outra tabela de recebíveis (padrão: `vendas_a_prazo.csv`).
- `--entrada forcar.json` — sobrescreve na mão qualquer parcela:
  `{"vendas": 0, "voucher": 0, "a_prazo": 0, "b2b": 0}`

## Regras que ela já definiu (não perguntar de novo)

1. **Descartar** as colunas `QTDE. CLIENTES` e `TICKET MÉDIO`. A tabela final
   tem só **FORMA DE PAGAMENTO · TOTAL · % DO TOTAL**.
2. **Agrupar mantendo o nome do primeiro da dupla:**
   - `TEF - DEBITO` + `CARTAO DEBITO` → **TEF - DEBITO**
   - `TEF - CREDITO` + `CARTAO CREDITO` → **TEF - CREDITO**
   - `VOUCHER IFOOD (DESCONTO)` + `IFOOD` → **VOUCHER IFOOD (DESCONTO)**
3. **Deixar separados:** `VOUCHER`, `TEF - VOUCHER` e `TEF - TICKET`. Ela
   desfez esse agrupamento de propósito — não juntar de novo.
4. Ordenar o quadrinho **do maior para o menor percentual**, com linha `Total`
   no pé.
5. Valores em **padrão brasileiro** (`R$ 1.089.716,13`).
6. **Não usar o nome da loja do cabeçalho do PDF.** O PDF vem com "ROBS", mas
   isso é erro do relatório — o valor é de **todas as filiais**. O subtítulo do
   quadrinho é sempre `Vendas de <período> · Todas as filiais`.

As regras 2 e 3 vivem no dicionário `GRUPOS` no topo de `gerar_relatorio.py`.
Mudança de agrupamento se faz lá, não na mão na resposta.

## Entrada prevista — como cada parcela é calculada

| Parcela | De onde sai |
|---|---|
| **Cartão (D+1)** | `TEF - CREDITO` + `TEF - DEBITO` do período atual, **já agrupados** (ou seja, com CARTAO CREDITO e CARTAO DEBITO dentro), **líquidos de taxa**. |
| **Pix** | **a venda do dia**, junto com crédito e débito (decisão dela em 30/09). O modelo D+0 — parcela própria, estimada pelo histórico, fim de semana caindo na segunda — só entra com `--pix-d0`. |
| **Voucher D+30** | soma de `VOUCHER` + `TEF - VOUCHER` + `TEF - TICKET` do PDF de `--mes-anterior`. Voucher liquida em 30 dias, então o previsto de hoje é a venda de voucher de um mês atrás. |
| **Repasse do iFood** | **valor informado na mão** em `--ifood-valor`, já líquido, por entidade (Grupo Ragga, Dell Iris). Cai na quarta, referente à semana segunda a domingo anterior. |
| **Vendas a prazo** | `vendas_a_prazo.csv`, os títulos cujo `VENCIMENTO` é o **dia anterior** à data prevista: é boleto, compensa em **D+1** (vence 20/09 → entra na previsão de 21/09). Fora disso a parcela não entra. |
| **B2B iKI** | ainda **sem base**. Entra só quando vier `--b2b`. |
| **Depois da meia-noite** | o que foi vendido depois do corte **sai** da previsão de amanhã e fica gravado em `pos_meia_noite.csv` para entrar sozinho na do dia seguinte. Valor informado em `--pos-meia-noite`. |

### O Pix: hoje entra como a venda do dia

> **DECISÃO DELA, 30/09: o Pix volta a ser a VENDA DE ONTEM**, na mesma linha
> de crédito e débito, sem estimativa. É o modelo antigo. Toda a máquina de
> D+0 descrita abaixo continua no código e volta com **`--pix-d0`**, mas o
> padrão (`PIX_D0_PADRAO = False`) é o Pix como venda do dia.
>
> Na prática: a linha do Pix no texto é o Pix do relatório menos a madrugada
> dele, mais a madrugada da véspera — igual ao cartão. O arrasto volta a levar
> o Pix junto.

O que está escrito abaixo é **por que o D+0 existe**, e vale se ela mandar
ligar de novo.

**O Pix não é D+1.** Ela confirmou em 23/09: o Pix da maquininha liquida no
mesmo dia da venda, e por isso a previsão estava saindo alta. Em 22/09 o texto
previu R$ 18.029,16 de Pix (o Pix vendido em 21/09) e caíram R$ 10.300,08 —
porque o Pix de 21/09 já tinha caído em 21/09.

Consequência: a previsão de hoje precisa do Pix de **hoje**, que de manhã ainda
não foi vendido. Ela sai de duas partes:

| Parte | De onde |
|---|---|
| **madrugada** | o que foi vendido depois da meia-noite no relatório de ontem — já é hoje no calendário, é número **real** |
| **resto do dia** | **estimativa**: mediana do mesmo dia da semana nas últimas `PIX_AMOSTRAS` (4) semanas, em `historico_pix.csv` |

#### Mas não cai em fim de semana

Ela confirmou em 23/09: **o Pix não liquida sábado nem domingo**. Os dois se
acumulam e caem **na segunda**, junto com a própria segunda. Então:

| Dia previsto | Parcela de Pix |
|---|---|
| terça a sexta | só o próprio dia |
| **sábado e domingo** | **nenhuma** — o script avisa e diz em que segunda aquilo entra |
| **segunda** | **três dias**: sábado + domingo + segunda |

Na segunda, só a parte da própria segunda é estimada: sábado e domingo **já
foram vendidos** e saem do histórico, com número real. Por isso o texto da
segunda sai com `de Pix de sábado, domingo e segunda` — quem lê na ponta
precisa saber que ali estão três dias, senão o número assusta (na segunda
21/09 teria dado R$ 66.279,83 contra ~R$ 17 mil de um dia comum).

Isso depende de o relatório ter rodado no domingo: é ele que grava o sábado no
histórico. Se faltar, o script **avisa** e estima aquele pedaço também.

`liquida_pix_em()` e `dias_do_pix()` cuidam disso, no topo de
`gerar_relatorio.py`. Feriado ainda **não** é tratado — só fim de semana.

O script **grava o histórico sozinho** a cada rodada (`DATA;DIURNO;MADRUGADA;TOTAL`,
com `DIURNO` = o Pix do dia fora a madrugada). Sem mesmo-dia-da-semana
suficiente ele cai para a mediana dos últimos 7 dias e **avisa no console**.

O mesmo dia da semana repete muito bem — medido entre agosto e setembro:
quarta 15.099,81 × 15.275,55 (1,2%), quinta 19.932,16 × 19.996,37 (0,3%),
segunda 16.137,65 × 16.898,14 (4,7%), sexta 24.210,28 × 22.923,79 (5,3%). O
sábado foi o pior (29.845,30 × 23.485,08, 21%).

Flags: `--pix-hoje VALOR` força a estimativa, `--sem-pix` tira a parcela,
`--historico outro.csv` aponta para outro arquivo.

#### Quanto a estimativa erra — medido

Comparando o mesmo dia da semana de agosto contra setembro (um mês de
distância), o erro do estimador em dia normal:

| Dia | Agosto | Setembro | Erro |
|---|---:|---:|---:|
| segunda | 17.368,32 | 17.747,02 | 2,1% |
| quarta | 15.879,42 | 16.239,68 | 2,2% |
| quinta | 21.475,26 | 21.785,56 | 1,4% |
| sexta | 26.683,15 | 26.180,01 | 1,9% |
| sábado | 34.289,17 | 27.711,73 | **23,7%** |

Ou seja: **2% em dia normal**, e o risco mora nos dias atípicos. Não adianta
refinar a fórmula — o que estraga a previsão é evento, não método.

#### O alerta de fatia (o que realmente quebra a estimativa)

**O Pix é uma fatia muito estável da venda**: 8,68% a 10,51% em 12 dos 13 dias
medidos, mediana **9,56%**. Quando foge disso não foi o cliente que mudou de
hábito — foi a operação.

Em **22/09 o Pix foi 4,97% da venda** e o débito bateu recorde (23,58%, contra
~20% de sempre), com a venda total quase igual à véspera. O dinheiro não sumiu:
**mudou de forma**, o que tem cara de maquininha sem Pix em alguma loja.

Por isso o script confere a fatia do dia anterior contra o histórico e, quando
o desvio passa de `PIX_DESVIO_ALERTA` (25%), **acende um ALERTA no console**
com os dois cenários: a estimativa normal (se foi pontual) e a estimativa
corrigida pela fatia de ontem (se o problema continuar), já com o comando
`--pix-hoje` pronto para colar.

**Isso não muda número nenhum sozinho** — quem decide é ela, que sabe se
resolveram ou não.

**Mas o dia anômalo sai da base de estimativa.** `dia_anomalo()` marca os dias
cuja fatia foge da faixa, e `estimar_pix()` os ignora: eles medem um problema
de operação, não o hábito do cliente. Sem isso, a terça 22/09 (Pix a 4,97%)
puxava a estimativa de todas as terças seguintes — em 29/09 daria R$ 12.819,23
em vez de R$ 17.437,63. Hoje estão marcados **22/09 (4,97%) e 23/09 (1,75%)**.

Junto com isso, **uma amostra do mesmo dia da semana já vale mais que a
mediana de sete dias misturados** — antes eram necessárias duas, e o fallback
de 7 dias mistura sábado com segunda.

> **O Pix não usa mais o `pos_meia_noite.csv`.** Quem guarda a madrugada dele
> é o próprio `historico_pix.csv`, que tem a coluna `MADRUGADA` de cada dia —
> o arrasto ficou só para crédito e débito, que são D+1.

> **Fica em aberto: o dia do Pix parece fechar por volta das 23h.** Em 22/09
> caíram R$ 10.300,08 contra R$ 8.655,58 de Pix vendidos no dia de calendário.
> A diferença bate com o Pix de 21/09 vendido depois das 23h (o melhor ajuste
> deu 22h58, erro de R$ 138). **É uma amostra só** — conferir conforme ela for
> passando o recebido de cada dia, e só então mexer.

`PAGAMENTO ONLINE` **é o iFood** e fica fora da parcela diária de cartão + Pix
porque tem repasse próprio, semanal. Isso confere com o modelo dela: no print
de 27/08 o previsto (R$ 101.481,14) bate com crédito + débito + Pix
(R$ 102.999,18) e não com nada que inclua o pagamento online.

### O corte da meia-noite

**O Cloudfy não vira o dia.** Ela confirmou em 17/09: a venda feita depois da
meia-noite continua gravada na data do dia anterior, o relatório não corta às
02h nem em hora nenhuma. Para a **venda** isso está certo — é a mesma noite de
operação, e o quadrinho tem que sair assim. Para o **recebimento** não: a
adquirente carimba a transação pela data do calendário, então o cartão passado
00h30 liquida junto com o dia seguinte.

Então esse pedaço **sai da previsão de amanhã e entra na de depois de amanhã**.
O jeito certo de fazer isso é com o relatório de cupons, que traz a hora:

```bash
python3 gerar_relatorio.py 16-09.pdf --mes-anterior 16-08.pdf \
    --cupons Relatriodecuponsdevendas_*.xlsx --saida saida
```

`--cupons` lê o `Relatriodecuponsdevendas_*.xlsx` do Cloudfy (aba `Planilha`,
cabeçalho na linha 1: `Filial · Caixa · Data · Cupom · Hora · Itens · Chave ·
CPF/CNPJ · Nome do cliente · Desc. pagam. · Nr. parc · Vl. pagamento`), agrupa
as formas pelas mesmas regras de `GRUPOS` e separa sozinho o que foi vendido
**da meia-noite até `HORA_ABERTURA` (05h)**. Ele também **confere o total
contra o PDF** e avisa se divergir.

> **O relatório de cupons bate exatamente com o PDF.** Medido em 16/09/2026:
> R$ 175.023,83 nos dois, e forma a forma idêntico (17 filiais, 4.454 cupons).
> É a mesma base, só que aberta — então dá para pedir esse arquivo junto com o
> PDF e o corte sai sem ninguém digitar nada.

Medido em 16/09: R$ 3.866,81 de cartão + Pix depois da meia-noite (crédito
R$ 1.652,52, débito R$ 1.250,16, Pix R$ 964,13), de um total de R$ 11.385,50
vendidos na madrugada — o resto é pagamento online, dinheiro, a prazo e
voucher, que não entram nessa parcela.

Sem o xlsx, dá para informar na mão:

```bash
python3 gerar_relatorio.py 15-09.pdf --mes-anterior 15-08.pdf \
    --pos-meia-noite "credito=1200" --pos-meia-noite "debito=900" \
    --pos-meia-noite "pix=400" --saida saida
```

- `--pos-meia-noite` aceita `[FORMA=]VALOR` e pode repetir. As formas são
  `credito`, `debito` e `pix` (também aceita o nome completo). **Sem forma, o
  valor é rateado** entre as três na proporção do próprio dia.
- O valor é subtraído da parcela de cartão + Pix **e gravado** em
  `pos_meia_noite.csv` (`DATA DE ENTRADA;FORMA;VALOR;ORIGEM;CORTE`), com data
  de entrada = dia previsto + 1.
- No dia seguinte o script **lê esse arquivo sozinho** e a parcela entra como
  linha própria, já líquida de taxa, no console e no texto.
- Rodar o mesmo dia duas vezes **não dobra**: as linhas daquela origem são
  regravadas.
- `--corte HH:MM` só muda o rótulo (padrão `00:00`); `--sem-arrasto` ignora o
  que está guardado; `--arrasto outro.csv` aponta para outro arquivo.

> **O PDF de vendas por forma de pagamento não tem hora** — por isso o
> `--cupons`. Sem `--cupons` e sem `--pos-meia-noite` nada é separado, e o
> script **avisa** que a previsão saiu com tudo e que nada foi guardado para o
> dia seguinte.

### A regra do iFood

O fechamento do iFood é de **segunda a domingo**, e isso abre **duas** datas em
que a parcela entra:

| Dia previsto | O que é | Entra no total? | De onde |
|---|---|---|---|
| **Segunda** | **prévia**: a semana fechou domingo, então o valor já dá para calcular | **NÃO** — sai num bloco à parte do texto | faturado do Cloudfy (`--ifood`) com as taxas |
| **Quarta** | o repasse **entra de verdade** | **SIM**, é parcela do total | valor na mão (`--ifood-valor`), já líquido |

**A regra que resolve tudo: a semana fecha no domingo e o dinheiro entra na
quarta.** Segunda é só quando já dá para saber o número — não é entrada de
segunda. Por isso a prévia fica **fora do total do dia** e vai no texto como
bloco separado (`🛵 REPASSE DO IFOOD — ENTRA QUARTA dd/mm`). Somar a prévia no
total de segunda contaria o mesmo dinheiro duas vezes, já que segunda 14/09 e
quarta 16/09 apontam ambas para a semana 07/09 a 13/09.

Nos outros dias da semana não há janela, e os PDFs de `--ifood` são ignorados
com aviso.

### O relatório de pedidos do iFood (fonte certa da prévia)

A Hylary exporta toda segunda o `relatorio-pedidos_*.xlsx` do iFood, cobrindo
a semana seg–dom. **Ele traz o `VALOR LIQUIDO (R$)` pronto, por pedido** — é a
fonte da prévia de segunda, muito melhor que estimar taxa sobre o Cloudfy.

Regra de limpeza: **descartar só os `CANCELADO`**. Manter `CONCLUIDO`,
`CANCELAMENTO PARCIAL` e `CONFIRMED`.

Identidade validada em 96,3% das linhas:

```
VALOR LIQUIDO = VALOR DOS ITENS − INCENTIVO PROMOCIONAL DA LOJA + TAXAS E COMISSOES
```

#### A estrutura de taxa — o que o arquivo permite afirmar

> **NÃO tentar decompor `TAXAS E COMISSOES` em comissão / transação /
> antecipação.** O arquivo traz **um número agregado por pedido** e não abre a
> composição. Uma tentativa anterior chegou a "10,600% × itens + taxa fixa"
> com erro de R$ 0,004, mas isso era **circular**: o ajuste foi feito num
> grupo selecionado por esse mesmo resíduo. Ajustando por loja, o percentual
> varia de **9,46% a 13,61%** com erro de ~R$ 1 por pedido — ou seja, a
> fórmula não se sustenta.

O que **é** medível, e basta para o relatório:

| Recorte | Taxa efetiva sobre os itens | Taxa média por pedido |
|---|---:|---:|
| ENTREGA (14.035 pedidos) | **20,41%** | R$ 9,41 |
| PARA RETIRAR (239 pedidos) | **12,10%** | R$ 6,27 |

**A taxa é fortemente regressiva** — quanto menor o pedido, maior a mordida:

| Itens do pedido | Taxa efetiva | Taxa por pedido |
|---|---:|---:|
| até R$ 25 | 30,27% | R$ 6,54 |
| R$ 25 a 40 | 24,31% | R$ 7,87 |
| R$ 40 a 60 | 19,85% | R$ 9,72 |
| R$ 60 a 100 | 16,97% | R$ 12,79 |
| acima de R$ 100 | 14,54% | R$ 19,60 |

A taxa por pedido sobe bem mais devagar que o valor do pedido, o que confirma
que existe **um componente fixo por pedido** — mas o tamanho exato dele não sai
deste arquivo.

#### O desconto real é ~40%, não 12%

Semana 07–13/09, pedidos liquidados:

| | | % dos itens |
|---|---:|---:|
| Valor dos itens | R$ 659.012,79 | 100% |
| − Incentivo promocional da **loja** | −R$ 110.321,83 | 16,74% |
| − Comissão + transação | −R$ 69.855,36 | 10,60% |
| − Taxa fixa por pedido | −R$ 63.648,41 | 9,66% |
| **= Valor líquido** | **R$ 397.039,13** | **60,25%** |

O incentivo promocional da loja é desconto que o Grupo banca, não taxa, mas
sai do líquido igual — e é a maior das deduções.

> **A antecipação de 1,59% não está no relatório.** O `VALOR LIQUIDO` é
> anterior a ela. Aplicar sempre no fim, sobre o total da semana.

> **Cuidado: o último dia da semana costuma vir incompleto.** Em 07–13/09,
> **803 dos 1.603 pedidos de domingo** estavam com taxa e líquido zerados (não
> liquidados). Os outros seis dias vieram completos. **Sempre conferir quantas
> linhas têm `VALOR LIQUIDO = 0` e em que dia caem**; se houver, estimar o que
> falta pela razão líquido/itens dos liquidados e avisar no chat.

#### Como montar a prévia a partir do relatório

1. Descartar só os `CANCELADO`.
2. Somar `VALOR LIQUIDO (R$)` dos pedidos liquidados.
3. Estimar as linhas com líquido zerado (o último dia costuma vir assim),
   aplicando aos itens delas a razão líquido ÷ itens dos já liquidados.
4. **Aplicar 1,59% de antecipação sobre o total.** O relatório de pedidos
   **não traz a antecipação** — ela incide depois, sobre o líquido, na média.

> **REGRA DURA: o número do iFood SEMPRE sai com a antecipação aplicada.**
> Nunca mandar o líquido cru do relatório de pedidos, nem na prévia de segunda
> nem no repasse de quarta, e nunca perguntar se aplica — ela já parametrizou
> isso. Em 14/09 a prévia foi mandada com R$ 422.999,70 (sem a antecipação) e a
> diretoria ficou esperando R$ 422 mil de um repasse de R$ 416.274,00.
>
> Para não depender de ninguém lembrar, passar o número do relatório em
> **`--ifood-liquido`**, que aplica os 1,59% sozinho e mostra a memória de
> cálculo. O `--ifood-valor` continua existindo para o **valor final**, já com
> tudo aplicado — e agora avisa no console quando é usado sozinho.
>
> ```bash
> python3 gerar_relatorio.py 15-09.pdf --mes-anterior 15-08.pdf \
>     --ifood-liquido "Semana 07 a 13/09=422999.70" --saida saida
> #   422.999,70 - 1,59% = 416.274,00
> ```

Feito em 07–13/09:

| | |
|---|---:|
| Liquidados | R$ 397.039,13 |
| + domingo estimado | R$ 25.960,57 |
| = líquido do relatório | R$ 422.999,70 |
| − antecipação 1,59% | −R$ 6.725,70 |
| **= previsão de recebimento** | **R$ 416.274,00** |

Faturamento da semana (`VALOR DOS ITENS`, sem cancelados): R$ 700.841,32.

No texto isso vai como bloco próprio, via `--ifood-valor` (a previsão já
líquida) e `--ifood-faturado` (o bruto, só para exibir):

```bash
python3 gerar_relatorio.py 11-13-09.pdf --mes-anterior 11-13-08.pdf \
    --ifood-valor "Previsao=422239.80" --ifood-faturado 700841.32 --saida saida
```

#### O que o iFood retém do repasse

Quando o iFood desconta algo do próprio repasse antes de creditar — hoje a
**parcela do empréstimo** (22 parcelas; a 18ª, de R$ 40.758,73, caiu na semana
21–27/09) — isso entra em `--ifood-desconto "[ROTULO=]VALOR"`, que pode
repetir. O valor é abatido da parcela e sai como **linha própria** no bloco do
iFood, para a Amanda ver o repasse cheio, o que foi retido e o que sobra:

```
· Faturamento: R$ 651.314,45
· Repasse previsto: R$ 401.767,14
· Parcela 18/22 do empréstimo: −R$ 40.758,73
· Retido (dívidas Santander/Safra): −R$ 16.900,01
· Previsão de recebimento: *R$ 361.008,41*
```

**O bloco sai nos dois dias, não só na segunda.** Na quarta o repasse já é
parcela do total, e o bloco vira a **abertura daquela linha** — fecha com
`Entra hoje, dd/mm, e já está no total acima.` para ninguém somar duas vezes.
Ele aparece sempre que houver `--ifood-faturado` ou `--ifood-desconto`; sem
nada disso o texto sai só com a linha no total, como antes.

Na quarta, passar em `--ifood-valor` o **repasse líquido de antecipação**, e os
descontos em `--ifood-desconto` — assim o bloco mostra a conta inteira e a
linha do total já sai abatida:

```bash
python3 gerar_relatorio.py cupons.xlsx --mes-anterior cupons_mes_anterior.xlsx \
    --ifood-valor "Semana 21 a 27/09=411789.77" \
    --ifood-desconto "Parcela 18/22 do empréstimo=40758.73" \
    --ifood-desconto "Retido (dívidas Santander/Safra)=16900.01" \
    --ifood-faturado 651314.45 --saida saida
```

#### A cadeia inteira do repasse (o portal mostra, o relatório não)

Ela mandou em 28/09 o print do portal da semana 07–13/09, e ele fecha a conta
que o relatório de pedidos sozinho não fecha:

| | | |
|---|---:|---|
| Repasse | R$ 432.242,52 | as duas operações somadas |
| − Retido | −R$ 8.114,00 | **dívidas de bancos**: R$ 4.904,60 Santander + R$ 3.209,40 Safra |
| = Base bruta a receber | R$ 424.128,52 | |
| Caiu na conta | R$ 424.146,20 | R$ 17,68 a mais que a base |
| − Taxa de antecipação | −R$ 3.661,54 | debitada **à parte**, no mesmo extrato (R$ 1.058,48 devolvidos por exclusividade → custo líquido R$ 2.603,06) |
| **= Valor líquido recebido** | **R$ 420.484,66** | |

Três coisas que isso derruba:

1. **O relatório de pedidos SUBESTIMA o repasse.** O líquido dele foi
   R$ 422.999,70 e o repasse real R$ 432.242,52 — **2,19% acima**.
2. **A taxa de antecipação NÃO está errada — a base é que é menor.** Ela
   incide sobre pouco mais da **metade** do repasse (base implícita a 1,59%:
   R$ 230.285 de R$ 432.242, 53%; e R$ 240.578 de R$ 445.150, 54%), porque só
   parte do recebível é antecipada. **Não mexer na `IFOOD_ANTECIPACAO`** — ela
   foi confirmada por ela em 28/09. No efeito sobre a previsão, a antecipação
   pesa **~0,853% do repasse**.
3. **O retido só existe no portal.** São parcelas de dívida com Santander e
   Safra que o iFood segura antes de creditar — não saem em relatório nenhum,
   então **têm de ser perguntados a ela toda semana**.

A semana 14–20/09 (print de 28/09) confirma a estrutura e fecha a calibração:

| Semana | Líquido do relatório | Repasse | Relatório → repasse | Retido | % do repasse | Antecipação | % do repasse | Líquido recebido |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 07–13/09 | 422.999,70 | 432.242,52 | +2,19% | 8.114,00 | 1,88% | 3.661,54 | 0,847% | 420.484,66 |
| 14–20/09 | 437.288,24 | 445.150,58 | +1,80% | 19.839,19 | 4,46% | 3.825,19 | 0,859% | 421.490,89 |

**Dois dos três fatores são estáveis e viraram régua:**

| Fator | Valor | Uso |
|---|---:|---|
| **Não liquidados** | **66,4% dos itens** | medido direto em 30/09 (ver abaixo) — **não** 81,3% |
| Relatório fechado → repasse | **×1,0147** | sobra ~1,5% que o relatório não mostra, mesmo depois de tudo liquidado |
| Antecipação | **0,853% do repasse** | efeito prático dos 1,59% sobre ~54% de base |
| **Retido** | **imprevisível** | 1,88% numa semana, 4,46% na outra — **só sai do portal, perguntar sempre** |

A semana **21–27/09** trouxe o retido em **R$ 16.900,01** (4,07% do repasse
estimado), passado por ela em 30/09 como **"semi atualizado"** — ou seja, ainda
pode mexer até o crédito cair. Com três semanas medidas o retido segue sem
padrão (1,88% · 4,46% · 4,07%): **continua sendo pergunta de toda semana**, e
quando vier como parcial, dizer isso no chat junto com a previsão.

**MEDIDO DIRETO EM 30/09: os não liquidados valem 66,4% dos itens.** Ela mandou
o relatório da MESMA semana (21–27/09) puxado na quarta, com tudo liquidado, e
isso matou o chute:

| | |
|---|---:|
| Domingo 27/09 na segunda | R$ 40.667,70 (1.119 pedidos) |
| Domingo 27/09 na quarta | R$ 59.898,35 (1.672 pedidos) |
| **Os 553 pedidos valiam** | **R$ 19.230,65** |
| sobre itens de R$ 28.977,17 | **66,36%** |

Eu tinha estimado 81,3% (R$ 23.558,44) e **errei 22,5% para cima**. A razão
certa é ~66%, um pouco acima da razão dos liquidados (~63%), não 80%.

**E sobra um resíduo que o relatório não explica.** Refazendo as duas semanas
com 66,36%, o repasse ainda fica **1,5% acima** do relatório fechado
(R$ 7.443,96 e R$ 5.237,29). Não é o domingo — é outra coisa, ainda sem nome.

> **Pedir o relatório de pedidos de novo na quarta.** É de graça, fecha a
> semana com número real e é o que permite medir o resíduo em vez de estimar.

| Semana | Liquidados | Repasse | Falta | Itens não liquidados | Razão |
|---|---:|---:|---:|---:|---:|
| 07–13/09 | 397.039,13 | 432.242,52 | 35.203,39 | 41.828,53 | 84,2% |
| 14–20/09 | 411.017,76 | 445.150,58 | 34.132,82 | 43.540,43 | 78,4% |

Então a conta da prévia passa a ser:

```
repasse estimado = (liquidados + itens não liquidados × 66,4%) × 1,0147
repasse líquido  = repasse × (1 − 0,853%)
previsão         = repasse líquido − retido − parcela do empréstimo
```

**Estimar os não liquidados é obrigatório**, e ela confirmou em 28/09: o
relatório só fecha na quarta e a prévia tem de sair na segunda.

> **Nas próximas semanas, pedir o print dessa tela.** É o único lugar onde
> aparecem o retido e a antecipação real. Sem o retido a previsão sai
> **incompleta e para cima** — avisar no chat quando ele faltar.

> **O `EMPRÉSTIMO IFOOD` do portal estava R$ 0,00 nas duas semanas medidas**,
> mesmo com a parcela 18/22 existindo. Conferir em 30/09 se os R$ 40.758,73
> aparecem nesse quadro ou em outro lugar.

#### O empréstimo do iFood

Separado do retido: é empréstimo do **próprio iFood**, abatido do crédito. Na
semana 07–13/09 estava zerado; na semana 21–27/09 entrou a **parcela 18/22, de
R$ 40.758,73**. Vai em `--ifood-desconto`, com rótulo próprio.

#### A previsão vem saindo ~2% acima do que entra

Medido na semana 14–20/09, o único par previsão × recebido fechado até agora:

| | |
|---|---:|
| Líquido do relatório de pedidos | R$ 437.288,24 |
| Previsão enviada (−1,59%) | R$ 430.335,36 |
| **Recebido de verdade** | **R$ 421.490,89** |
| **Desconto real sobre o líquido** | **3,613%** |

**Não foi a estimativa do domingo.** O domingo 20/09 teve razão líquido/itens
de 62,36% nos pedidos já liquidados, *acima* dos 60,34% aplicados — se houve
erro, foi para menos. Ou seja: entre o `VALOR LIQUIDO` e o dinheiro na conta
some mais ~2% que o relatório não mostra (plano/assinatura, chargeback, pedido
cancelado depois do snapshot).

O teste que sustenta isso: aplicando 3,613% na semana 21–27/09 a previsão dá
R$ 393.509,82, o que implica 25,40% de desconto sobre o `PAGAMENTO ONLINE` do
Cloudfy — dentro da faixa das duas semanas medidas (25,06% e 25,46%). Com
1,59% daria 23,84%, **fora da faixa**.

> **Falta o segundo par** (recebido da semana 07–13/09) antes de trocar a
> constante. Até lá, aplicar os 1,59% e **avisar no chat** que deve entrar ~2%
> abaixo.

#### Cloudfy × relatório de pedidos

`PAGAMENTO ONLINE` do Cloudfy espelha **`VALOR DOS ITENS − INCENTIVO DA LOJA`**
do iFood — não o valor líquido, e não o valor dos itens puro.

A virada de dia é às **02h**, não à meia-noite: agrupar os pedidos por
`DATA E HORA DO PEDIDO − 2h` reduz o erro diário de R$ 3.877 para R$ 2.861.

Semana 07–13/09: Cloudfy R$ 555.505,94 × iFood R$ 579.344,26 → Cloudfy fica
**4,1% abaixo** (R$ 23.838,32), dos quais R$ 2.855,21 são pedidos com
`CANCELAMENTO PARCIAL`. Sobram ~3,6% sem explicação, que encolhem ao longo da
semana (−5,9% na segunda, −0,9% no domingo) — tem cara de atraso de
lançamento, não de perda.

**A Dell'iris está nas duas fontes e não tem relatório próprio.** É uma *dark
kitchen* dentro das lojas físicas: no iFood ela aparece como 4 lojas próprias
(988 pedidos, R$ 32.559,78 na semana), e no Cloudfy o faturamento dela sai
embutido no da loja que a hospeda. Não existe e não adianta pedir um relatório
de vendas separado dela.

> **Por que a estimativa por taxa dava errado:** aplicar 12,02% sobre o
> faturado do Cloudfy deu R$ 488.726,02 para 07–13/09, contra um líquido real
> de ~R$ 422 mil. **Erro de R$ 66 mil.** Por isso a prévia de segunda passa a
> sair do `VALOR LIQUIDO` do relatório de pedidos, não de taxa sobre o Cloudfy.

**O valor NÃO sai do Cloudfy.** O `PAGAMENTO ONLINE` do relatório é a *venda*,
não o *repasse* — medido em 09/09, a diferença foi de **24,72%**, muito acima
da taxa. Ela passa o valor na mão:

```bash
python3 gerar_relatorio.py 08-09.pdf --mes-anterior 08-08.pdf \
    --ifood-valor "Grupo Ragga=401827.58" --ifood-valor "Dell Iris=22224.02" \
    --saida saida
```

- `--ifood-valor` aceita `[ROTULO=]VALOR`, pode repetir e soma tudo. O rótulo
  aparece na abertura do console. Aceita `401827.58` e `401.827,58`.
- **O valor informado assim JÁ É LÍQUIDO — nunca aplicar taxa em cima.**
  Aplicar os 12,02% de novo tiraria uns R$ 51 mil de um repasse de R$ 424 mil.
- Chega **por entidade**: Grupo Ragga e Dell Iris são CNPJs diferentes e vêm
  em valores separados. Passar cada um com seu rótulo.
- **A Dell Iris é só iFood.** Ela não tem cartão, voucher nem venda a prazo
  para entrar no previsto — o relatório do Cloudfy (CNPJ 52.934.334/0001-36)
  cobre tudo o que não é iFood. Não procurar venda da Dell Iris.
- Se a data prevista é quarta e o valor não veio, o script avisa e diz a janela
  — aí é pedir o valor antes de mandar o texto.

`--ifood <pdf>` continua existindo como **estimativa** a partir do Cloudfy (aí
sim com a taxa de 12,02%), mas `--ifood-valor` tem precedência e o script avisa
quando os dois vêm juntos. Para o número que vai para a diretoria, usar sempre
o valor informado.

### As taxas (entrada prevista LÍQUIDA)

A entrada prevista sai **líquida de taxa**, como estimativa. As taxas vivem em
`TAXAS` e `TAXA_IFOOD` no topo de `gerar_relatorio.py` — mudança de taxa se faz
lá:

| Forma | Taxa |
|---|---:|
| Crédito (`TEF - CREDITO`) | 2,63% |
| Débito (`TEF - DEBITO`) | 0,99% |
| Pix maquininha | 0% |
| Voucher | **6,90%** — a maior das operadoras |
| iFood (`PAGAMENTO ONLINE`) | **25,064% efetivos** (medido) — só na estimativa por `--ifood`; o valor de `--ifood-valor` já vem líquido |

Regras de uso:

- **Não descrever as taxas no texto do WhatsApp.** Ela pediu explicitamente:
  o texto mostra só o valor líquido. A abertura bruto → taxa → líquido sai no
  console, e vale reportar no chat.
- São **estimativas**, não a taxa real de cada transação. A taxa real sai do
  EDI — isso é a skill `ragga-conciliacao`.
- **A taxa do iFood é 25,064%, MEDIDA — não é a soma das taxas de tabela.**
  Está em `IFOOD_DESCONTO_EFETIVO`. Veio de cruzar o relatório de pedidos com
  o Cloudfy na semana 07–13/09:

  | | |
  |---|---:|
  | base Cloudfy (`PAGAMENTO ONLINE`) | R$ 555.505,94 |
  | recebido do iFood (já líquido) | R$ 416.274,00 |
  | **desconto efetivo** | **25,064%** |

  Os 12,02% de tabela (8% + 2,60% + 1,59%) erravam em **R$ 72.451,79** nessa
  semana, porque ignoravam a taxa fixa por pedido, o incentivo promocional
  bancado pela loja e os pedidos pagos em vale.

  > **Amostra de uma semana só.** Recalibrar conforme os pares faturado ×
  > recebido forem acumulando. A `IFOOD_ANTECIPACAO` (1,59%) continua separada
  > porque é aplicada à parte sobre o líquido do relatório de pedidos — ela já
  > está dentro dos 25,064%.
- **Voucher: 6,90%**, em `TAXA_VOUCHER`. É a **maior taxa** que o Grupo tem
  hoje entre as operadoras de vale (Alelo, Pluxee, Ticket, Fepas) — escolha
  conservadora dela, para o previsto não sair otimista. A taxa cobre as três
  formas de `FORMAS_VOUCHER`: `VOUCHER`, `TEF - VOUCHER` e `TEF - TICKET`.
  Substituiu os 5% fictícios que valiam antes. Se um dia a média real por
  operadora for levantada, é trocar uma linha — **não perguntar a cada envio**.
- **Venda a prazo e B2B saem brutos** — são boleto, sem adquirente no meio.
- `--bruto` desliga tudo e devolve a entrada prevista no bruto, para comparar.

#### Validação contra o Sicredi (semana 08–14/09/2026)

Ela exporta o `vendas_<loja>_<data>.zip` do portal — **17 lojas**, um `.xlsx` por
loja, layout consolidado (crédito, débito, PIX e voucher no mesmo arquivo).
Cabeçalho na **linha 13**, achar pela célula `Data da venda`. **`openpyxl` não
abre** esses arquivos: usar `python-calamine`. Manter só `Aprovada` e
`Autorizada`.

Colunas que importam: `Produto`, `Bandeira`, `Status`, `Valor Bruto`,
`Valor da taxa (MDR)`, `Valor líquido`.

**As duas fontes batem — o Cloudfy é confiável:**

| Forma | Cloudfy | Sicredi bruto | Cloudfy/Sicredi |
|---|---:|---:|---:|
| Crédito | R$ 306.163,49 | R$ 307.014,01 | 99,72% |
| Débito | R$ 280.437,22 | R$ 279.031,72 | 100,50% |
| PIX | R$ 140.256,22 | R$ 140.648,89 | 99,72% |
| Voucher | R$ 47.064,03 | R$ 49.593,68 | 94,90% |
| **TOTAL** | **R$ 773.920,96** | **R$ 776.288,30** | **99,70%** |

**As taxas medidas confirmam a parametrização:**

| Forma | MDR medido | Parametrizado | Leitura |
|---|---:|---:|---|
| Débito | **1,00%** | 0,99% | confirmado |
| PIX | **0,00%** | 0% | confirmado |
| Crédito | **1,11%** | 2,63% | 2,63% = MDR + antecipação |
| Voucher | 0,05% | 6,90% | a taxa do vale **não está** neste arquivo |

O crédito **não está errado**: o MDR puro é 1,11%, e os 2,63% embutem a
antecipação automática (sem ela o crédito seria D+30). A antecipação implícita
é **1,52%**, coerente com os **1,6424%** medidos na conciliação em 14/08.

> **Falta o relatório de antecipação** para cravar a taxa da semana em vez de
> inferir. É um dos 4 relatórios do portal e não veio neste zip.

A taxa de voucher de 6,90% é cobrada **pela operadora do vale** (Alelo, Pluxee,
Ticket), fora do Sicredi — por isso aparece como 0,05% aqui.

Confere com o modelo dela: aquele print de 27/08 saiu 1,47% abaixo da soma
bruta, que era justamente o desconto de taxa.

O texto do WhatsApp só mostra as parcelas que têm número; o que está faltando
sai como aviso no console, para não mandar `[PREENCHER]` para a diretoria.
**Sempre avisar no chat o que ficou de fora.**

## vendas_a_prazo.csv

Tabela de recebíveis B2B a prazo (BGs, Casaria etc.) que ela manda de vez em
quando. Formato: `RAZAO SOCIAL;CNPJ;VALOR;VENCIMENTO;ORIGEM DO CONSUMO`, com
valor em padrão BR e vencimento `dd/mm/aaaa`.

Estado atual: **26 títulos, R$ 53.102,69**, assim distribuídos:

| Vencimento | Títulos | Valor |
|---|---:|---:|
| 14/09/2026 | 22 | R$ 38.482,02 |
| 20/09/2026 | 3 | R$ 12.748,67 |
| 28/09/2026 | 1 | R$ 1.872,00 |

Quando ela mandar títulos novos, acrescentar linhas no arquivo e commitar.

**O que entra e o que não entra** quando ela manda a planilha do B2B:

- entra o que está **A RECEBER com data futura** — é caixa que ainda vai cair;
- **não entra permuta** (HELP DESK, ALISON CECOTTI): é troca, não é dinheiro;
- **não entra linha zerada** (consumo de colaboradores antes do fechamento,
  cliente sem consumo no mês);
- **não entra o que já está RECEBIDO**, e o que está **VENCIDO ou A RECEBER com
  data passada fica de fora** até ela dar uma data nova — a parcela só entra no
  dia exato do vencimento, então uma data velha nunca mais apareceria.

**É boleto, então compensa em D+1 do pagamento** — e **vencimento em fim de
semana só é pago no próximo dia útil**. Ela confirmou isso em 21/09, com os
títulos que venceram no domingo 20/09: os clientes pagam na segunda e o
dinheiro cai na terça, então a parcela foi para 22/09 e não para 21/09.

A conta é `próximo dia útil do vencimento + A_PRAZO_COMPENSACAO`, pulando o
fim de semana de novo no fim — está em `entrada_do_boleto()`, e o intervalo
vive em `A_PRAZO_COMPENSACAO`, no topo de `gerar_relatorio.py`.

Cuidado para **não contar em dobro**: a venda a prazo já entrou na venda bruta
no dia da venda; o que entra aqui é o **caixa** na compensação. São coisas
diferentes, e é por isso que `VENDA A PRAZO` não está em `CARTAO_E_PIX`.

## Conferências que o script já faz

- A soma antes e depois do agrupamento tem de ser idêntica (erro se divergir).
- Avisa se alguma forma de `GRUPOS` não apareceu no PDF do dia.
- Imprime o total de cada dia para bater com o rodapé do PDF.
- Avisa quando o período do mês anterior tem número de dias diferente do atual
  (aí o voucher D+30 sai desproporcional).
- Mostra os vencimentos da tabela, com a data em que cada um entra (D+1),
  quando nenhum boleto compensa na data prevista.

Se o PDF vier sem nenhum dia reconhecido, o layout do Cloud Commerce mudou —
conferir `ROW_RE` e `DAY_RE`.

## Ambiente

- `pdfplumber` para ler o PDF. Se der `ModuleNotFoundError: _cffi_backend`,
  rodar `pip install --force-reinstall cffi`.
- Chromium para o PNG (usa `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`
  ou o que estiver no PATH; dá para apontar com `CHROME_PATH`). Sem Chromium o
  script salva `vendas_card.html` em vez do PNG.
- `pillow` (opcional) para recortar a sobra branca do print.

# Envio 2 — entradas do dia (recebimento real)

Quando ela passar os valores que entraram:

```bash
python3 gerar_entradas.py --data 04/09/2026 --previsao 110000 \
    --pix 24739.28 --debito 44730.61 --credito 46217.25 \
    --voucher 6730.53 --b2b 1045.86 --saida saida
```

Ou com `--dados recebimentos.json`:

```json
{
  "data": "04/09/2026",
  "previsao": 110000.00,
  "recebido": {"PIX": 24739.28, "Débito": 44730.61, "Crédito": 46217.25,
               "Voucher": 6730.53, "B2B": 1045.86},
  "total_informado": 128115.36
}
```

Formas disponíveis, na ordem em que saem no texto: `--pix`, `--debito`,
`--credito`, `--voucher`, `--b2b`, `--dinheiro`, `--online`. Só as que forem
passadas aparecem na mensagem.

## Regras do envio 2

1. **`--previsao` é a previsão que foi mandada para aquele dia** no envio 1 —
   não recalcular por outro caminho. Sem ela o script para: comparar
   recebimento com uma previsão inventada é pior do que não mandar nada.
2. **O `VALOR RECEBIDO` é sempre a soma das formas.** Nunca digitar um total à
   parte. Se ela informar um total, passar em `--total-informado`: o script
   confere e avisa se não fechar, mas o texto sai com a soma.
3. O tom muda sozinho conforme o resultado: acima da previsão sai `✅` +
   `🟢 ... ACIMA` + 🚀 no resumo; abaixo sai `⚠️` + `🔴 ... ABAIXO` e um resumo
   sem comemoração; empate sai `⚪ EM LINHA COM A PREVISÃO`.
4. **Sempre reportar no chat** a diferença entre previsto e recebido, e por
   forma quando der, para ela ver de onde veio o desvio.

## Sobre o exemplo de 04/09

Os valores daquele modelo **não são reais** — ela confirmou que era só para
mostrar o formato. Por isso a soma das formas (R$ 123.463,53) não fechava com
o total do texto (R$ 128.115,36). Não é para caçar essa diferença.

A trava do `--total-informado` continua valendo para os envios de verdade: se
a soma não fechar com o total que ela passar, avisar antes de mandar.

# Retiradas para depósito (sangria)

Ela exporta o `Relatriodesangriassuprimentos_*.xlsx` do PDV quando precisa
casar o dinheiro depositado com o que a loja sangrou. Abre com `openpyxl`,
aba `Planilha`, cabeçalho na linha 1:
`Filial · Caixa · Data · Valor · Motivo/Descrição · Usuário · Usuário autorizador`.

**Ela quer SÓ o consolidado por loja.** Não mandar o detalhe lançamento a
lançamento nem a quebra por dia, a não ser que peça. Formato:

| Loja | Retiradas | Valor | % |

## Como classificar

O campo é texto livre e vem escrito de vários jeitos, com erro de digitação.
A regra que funciona:

1. **Entra**: a descrição contém `depósito`/`deposito` **e não** contém
   suprimento. Aparece como `RETIRADA DEPOSITO`, `RETIRADA DEPOSITO R$450,00.`,
   `Retirada deposito no valor de R$900,00. Autorizado pelo gerente Gabriel.`
2. **Entra também**: a descrição é exatamente `RETIRADA`, sem destino — ela
   decidiu em 15/09 que esses contam como depósito.
3. **Fica de fora** todo o resto.

> **A armadilha: "retirada" sozinha quase nunca é depósito.** A maioria são
> `RETIRADA PARA SUPRIMENTO DO CAIXA`, dinheiro passando de um caixa para
> outro, que nunca sai da loja. Filtrar por "retirada" na semana 07–14/09
> contaria R$ 15.240,00 de transferência interna como depósito.

Grafias de suprimento já vistas, todas no mesmo relatório: `SUPRIMENTO`,
`SUPLIMENTO`, `SUPPRIMENTO`, `SUUPRIMENTO`, `suplimento`. O casamento por
`supr|supl|suppr|suup` pega todas.

Outras categorias que aparecem e ficam de fora: pagamento a freelancer,
compra/despesa (gelo, arroz, café, pit stop), reembolso e estorno a cliente,
pagamento de entregador por fora quando a TAON está sem limite.

## A descrição manda — e vai furar às vezes

**Classificar sempre pela descrição, e só por ela.** A descrição erra em alguns
casos: em 13/09 a BIGGS 13 registrou `RETIRADA SUPRIMENTO CAIXA E DELIVERY
DIURNO` (R$ 2.350,00) e era depósito — o operador ia suprir o caixa, não
precisou, e depositou.

Isso é **normal e esperado**, e a Hylary já decidiu como lidar: **ela acha
esses casos quando o valor cai no extrato.** Consequências para mim:

- **não propor lista de "suspeitos"** nem pedir confirmação de lançamentos que
  a descrição classifica como suprimento — ela não quer esse ruído;
- **não tentar adivinhar** por valor alto ou por padrão de caixa;
- quando ela apontar um furo, **incluir aquele lançamento** e seguir.

## O painel

O de:para virou painel, em **https://retiradas-deposito.vercel.app** (código em
`hylaryfarias/retiradas-deposito`, arquivo `index.html`).

- **Cada semana é uma aba**, com os próprios arquivos, observações e situação.
  Nada é compartilhado entre abas; o upload vai para a aba que estiver aberta.
- **O nome da aba define o período**: `07/09 a 13/09` corta da sangria o que
  for de fora. O extrato **não** é filtrado por data, porque o depósito cai
  depois — às vezes na semana seguinte.
- **Fonte 3 · Suprimentos** é o export do PDV filtrado em suprimento. Ele
  entra **na mesma lista da sangria**, com um selo `suprimento` na linha, para
  a pesquisa varrer os dois de uma vez. Vem **tudo desmarcado**: nada dali
  conta no quadro. Marcar uma linha é o jeito de corrigir o furo da descrição
  — aquele lançamento passa a contar como depósito da loja. É o caso da
  BIGGS 13 de 13/09.
- Um escreve, o time lê: quem tem o token publica; quem abre o link só olha.
- **O bloco "Em aberto" não é uma semana.** O arquivo que sobe cai nele, e ele
  só vira semana quando ela clica em **Fechar semana** — é aí que nasce a aba
  com cadeado. Antes disso não há o que trancar, e foi essa confusão que fez
  ela achar que tinha criado uma semana nova em 30/09.
- **As abas saem em ordem de período**, pela menor data dos lançamentos (não
  pela ordem em que foram fechadas): refazer uma semana antiga não joga ela
  para o fim da fila. A aba do bloco em aberto diz `Em aberto · <período>` —
  antes ela mostrava só o período, igualzinha a uma semana fechada.
- **Semana fechada nasce TRANCADA** (cadeado na aba e no cabeçalho). Trancada,
  ela não aceita upload, não deixa renomear, não deixa marcar/desmarcar
  lançamento, não deixa editar situação nem observação, e o botão Remover some.
  Destrancar é um clique no cadeado com confirmação.
- **Antes de um arquivo entrar por cima de outro**, o painel diz o que vai ser
  substituído (aba, nome do arquivo e quantos lançamentos) e pede confirmação.

> **Por que isso existe.** O upload sempre foi para a **aba que está aberta**, e
> a aba aberta pode ser uma semana já fechada (`alvo()` devolve a semana da aba,
> não o bloco em aberto). Em 30/09 ela subiu o arquivo da semana nova com a aba
> da semana anterior selecionada e o arquivo entrou por cima — a semana passada
> foi embora sem aviso nenhum. A trava e o aviso de substituição fecham os dois
> buracos.
>
> **E o nome do botão ajudou o acidente.** Ele se chamava `+ Nova semana`, o que
> lê como "cria uma aba vazia" — mas o que ele faz é **fechar** o que está em
> aberto. Hoje se chama **Fechar semana**. Não voltar ao nome antigo.

### Quando o painel perder dado

O estado vive num **gist secreto**, id `d84f5b4a270c092d2e8cfda4da4a9baa`, arquivo
`painel-depositos.json`. O GitHub guarda **todas as revisões** desse gist, então
nada se perde de verdade: é só restaurar em
`https://gist.github.com/d84f5b4a270c092d2e8cfda4da4a9baa/revisions`, abrir a
revisão certa em Raw, copiar e colar de volta no gist (Edit → Update).

Duas coisas que mordem nessa hora:

1. **Fechar todas as abas do painel antes.** Uma aba aberta republica o estado
   dela por cima em 2,5 s (`agendar()`), desfazendo a restauração.
2. Para quem edita, o painel só aplica o gist se ele for **mais novo** que o que
   está na tela — mas `sync.carimbo` mora só na memória e volta a 0 a cada
   carregamento, então **abrir a página do zero sempre aplica** o que está no
   gist. Restaurar e recarregar funciona; restaurar com a aba aberta, não.

> **Gist está fora do alcance do Claude Code aqui**: a sessão só fala com
> endpoints do próprio repositório (`repos/{owner}/{repo}/...`), e
> `api.github.com/gists/...` volta 403. Restauração é na mão, pelo navegador.

## Conciliação

Pergunta sobre **por que** o dinheiro entra assim (taxas, prazos, EDI, vales,
Sicredi/Fiserv) não é este relatório — usar a skill `ragga-conciliacao`.
