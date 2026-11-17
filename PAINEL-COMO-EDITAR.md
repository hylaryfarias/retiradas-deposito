# Painel de retiradas para depósito — como assumir

Este documento é para quem vai **mexer no painel**: corrigir, melhorar, dar
manutenção. Ele descreve o que existe hoje, como publicar, como testar sem
estragar o dado de verdade, e o que foi decidido de propósito e não deve ser
desfeito.

Site no ar: **https://retiradas-deposito.vercel.app**

---

## 1. O que é

Uma página que casa o **dinheiro que as lojas sangraram do caixa para depósito**
(export do PDV, Cloudfy) com o **que apareceu no extrato bancário**, semana a
semana, e fecha um quadro por loja que vai para a diretoria.

Quem usa: a Hylary edita e publica. O time abre o link e só lê.

---

## 2. Onde mora o código

| | |
|---|---|
| Repositório | `github.com/hylaryfarias/retiradas-deposito` |
| Arquivo | **`index.html`** — um arquivo só, ~1.830 linhas |
| Branch | `claude/payment-methods-grouping-8u535o` (**é a única que existe; é a principal**) |
| Deploy | Vercel, automático a cada push |

> O repositório já se chamou `relatorio-diario` e o nome antigo ainda
> redireciona. É o mesmo lugar, e ele guarda **duas coisas**: o painel
> (`index.html`) e os scripts do relatório diário de vendas (`gerar_*.py`).
> Mexer num não tem relação nenhuma com o outro.

**Não tem build, não tem npm, não tem framework.** É HTML + CSS + JavaScript
puro, no mesmo arquivo. As duas únicas coisas de fora são carregadas por CDN:

- `xlsx.full.min.js` 0.18.5 (SheetJS) — lê os `.xlsx` que o usuário sobe;
- a fonte Instrument Sans, do Google Fonts.

Para editar, basta um editor de texto. Para ver o resultado, basta abrir o
arquivo no navegador.

---

## 3. Como publicar uma mudança

```bash
git clone https://github.com/hylaryfarias/retiradas-deposito.git
cd retiradas-deposito
# editar index.html
git add index.html
git commit -m "o que mudou"
git push
```

O Vercel reconstrói sozinho em menos de um minuto.

> **ATENÇÃO: não existe ambiente de homologação.** O push vai direto para o
> site que a diretoria abre. Testar **antes** (ver a seção 5).

Quem for fazer isso precisa de **acesso de escrita no repositório** — a Hylary
concede em `Settings → Collaborators`.

---

## 4. Onde mora o DADO (e por que isso é a parte delicada)

**O dado não está no repositório.** O que o painel guarda — as semanas
fechadas, os arquivos processados, os vínculos, as observações — vive num
**gist secreto do GitHub**, na conta da Hylary:

| | |
|---|---|
| gist | `d84f5b4a270c092d2e8cfda4da4a9baa` |
| arquivo | `painel-depositos.json` |

A página lê esse gist ao abrir e escreve nele ao publicar. É a fonte única da
verdade: o repositório guarda **só o programa**, nunca os números.

### Quem pode escrever

Para publicar, o painel pede um **token pessoal do GitHub com permissão de
Gists (Read and write)**. O token é colado na própria página e fica guardado
**só no `localStorage` daquele navegador** — nunca vai para o repositório nem
para o gist.

- **Com token** → a pessoa edita e publica para o time.
- **Sem token** → a pessoa só enxerga o que foi publicado. O bloco "Em aberto"
  (trabalho pela metade) fica escondido.

Ou seja: **mandar o link para alguém não dá poder de edição nenhum.** É seguro
compartilhar.

### Se o dado se perder

O GitHub guarda todas as revisões do gist:
`https://gist.github.com/d84f5b4a270c092d2e8cfda4da4a9baa/revisions`

Abrir a revisão certa em Raw, copiar e colar de volta no gist (Edit → Update).

> **Fechar TODAS as abas do painel antes de restaurar.** Uma aba aberta
> republica o estado dela por cima em 2,5 segundos (função `agendar()`) e
> desfaz a restauração sem avisar.

---

## 5. Como testar sem encostar no dado de verdade

Três caminhos, do mais leve ao mais completo:

1. **Abrir o `index.html` direto do disco.** Sem token, o painel roda em modo
   local: o que a pessoa fizer fica só naquele navegador. Serve para mexer em
   layout, texto, cor, ordenação.

2. **Apontar para um gist de rascunho.** A página aceita `?g=<id do gist>` na
   URL e passa a usar aquele gist em vez do oficial. Então: criar um gist
   secreto próprio, abrir `index.html?g=<id novo>` com um token próprio, e
   trabalhar à vontade. **É assim que se testa publicação sem risco.**

3. **Subir para o Vercel** só quando estiver pronto.

Para exercitar de verdade, é preciso um export do PDV
(`Relatriodesangriassuprimentos_*.xlsx`) e um extrato. Pedir à Hylary um par
antigo — serve qualquer semana já fechada.

---

## 6. Decisões que NÃO devem ser desfeitas

Estas não são preferências de estilo: cada uma saiu de um problema real.
Mexer nelas é refazer um erro que já aconteceu.

**Classificação dos lançamentos**

- Conta como depósito quando a descrição tem `depósito`/`deposito` **e não**
  tem suprimento (as grafias erradas são muitas: `SUPRIMENTO`, `SUPLIMENTO`,
  `SUPPRIMENTO`, `SUUPRIMENTO` — o casamento por `supr|supl|suppr|suup` pega
  todas). Conta também a descrição que é exatamente `RETIRADA`, sem destino.
- **Filtrar por "retirada" sozinha está errado**: a maioria é
  `RETIRADA PARA SUPRIMENTO DO CAIXA`, dinheiro indo de um caixa para outro,
  que nunca sai da loja. Numa semana isso contaria R$ 15.240,00 a mais.
- A descrição às vezes erra, e isso é esperado. O conserto é marcar a linha na
  **Fonte 3 · Suprimentos**, que entra na mesma lista com um selo. Não criar
  lista de "suspeitos" nem adivinhar por valor alto — a Hylary acha esses
  casos quando o valor cai no extrato.

**Interface**

- **Não recriar o botão "Fechar semana".** Quem guarda a semana é o cadeado do
  cartão "Em aberto", na lateral, com uma confirmação que diz o período.
- **Não devolver o seletor de data do "Texto do fechamento".** Ele segue a
  semana aberta, e só. O seletor deixava copiar o texto da semana errada.
- **Não devolver para dentro da tabela** o nome editável, o botão de trancar
  nem o título "De:para por loja". Saíam no print que vai para a diretoria.
  Controle de edição mora na lateral, que some para quem só lê.
- **A faixa vermelha acima da tabela é só informativa** (`SEMANA APURADA` + o
  período). Não pendurar botão nela.
- **Semana fechada nasce trancada**, e trancada não aceita upload, renomear,
  marcar lançamento nem editar observação.
- **O bloco "Em aberto" não aparece para quem não tem token**, e a página abre
  na última semana apurada. Trabalho pela metade não vai para a diretoria.

**A armadilha que motivou metade disso**

O upload sempre vai para **a aba que está aberta** — e a aba aberta pode ser
uma semana já fechada. Isso já apagou uma semana inteira sem aviso. Por isso
existem a trava e a confirmação que diz o que vai ser substituído. Qualquer
mexida no fluxo de upload tem de manter os dois.

---

## 7. O que a pessoa precisa para começar

| Para | Precisa de |
|---|---|
| Ler o código | nada, é público no repositório |
| Mexer e publicar o **programa** | acesso de escrita no repositório |
| Mexer no **dado** (fechar semana, subir arquivo) | um token do GitHub com permissão de Gists, e acesso ao gist |
| Testar sem risco | um gist secreto próprio + `?g=<id>` na URL |

**Para só melhorar o painel, o primeiro acesso basta.** O segundo e o terceiro
só são necessários se a pessoa também for operar a rotina semanal — o que hoje
é da Hylary.

---

## 8. Por onde um recém-chegado começa

1. Abrir o `index.html` no navegador e brincar no modo local.
2. Ler o arquivo de cima para baixo uma vez. É longo mas é linear: estilo,
   HTML, leitura dos `.xlsx`, classificação, render, e por último o bloco de
   sincronismo com o gist (a partir da linha ~1.477, que tem o comentário
   explicando o modelo "um escreve, o time lê").
3. Fazer uma mudança pequena e visível, publicar num gist de rascunho, e
   conferir no navegador.
4. Só então encostar no repositório.
