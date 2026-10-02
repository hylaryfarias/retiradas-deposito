#!/usr/bin/env python3
"""Gera o texto de ENTRADAS DO DIA — o recebimento real contra a previsão.

É o complemento do gerar_relatorio.py: aquele manda a venda bruta e a entrada
prevista; este manda, depois, o que de fato entrou.

Uso:
    python3 gerar_entradas.py --data 04/09/2026 --previsao 110000 \
        --pix 24739.28 --debito 44730.61 --credito 46217.25 \
        --voucher 6730.53 --a-prazo 1045.86

    python3 gerar_entradas.py --dados recebimentos.json
"""

import argparse
import json
import os
import sys

from gerar_relatorio import brl

LINHA = '━' * 18

# Ordem em que as formas saem no texto. A chave e o nome da flag na linha de
# comando (--pix, --debito, ...); o valor e o rotulo que aparece na mensagem.
FORMAS = [
    ('pix', 'PIX'),
    ('debito', 'Débito'),
    ('credito', 'Crédito'),
    ('voucher', 'Voucher'),
    ('a_prazo', 'A prazo'),
    ('dinheiro', 'Dinheiro'),
    ('online', 'Pagamento online'),
]


def montar_texto(data, previsao, recebido_por_forma):
    """recebido_por_forma: lista de (rotulo, valor) na ordem de FORMAS."""
    recebido = sum(valor for _, valor in recebido_por_forma)
    diferenca = recebido - previsao

    if diferenca > 0:
        marca, sinal = '✅', f'🟢 R$ {brl(diferenca)} ACIMA DA PREVISÃO'
        resumo = (f'A previsão de R$ {brl(previsao)} foi superada, com entrada '
                  f'total de R$ {brl(recebido)}, representando um resultado de '
                  f'R$ {brl(diferenca)} acima do previsto. 🚀')
    elif diferenca < 0:
        marca, sinal = '⚠️', f'🔴 R$ {brl(abs(diferenca))} ABAIXO DA PREVISÃO'
        resumo = (f'A previsão de R$ {brl(previsao)} não foi atingida: a entrada '
                  f'total foi de R$ {brl(recebido)}, R$ {brl(abs(diferenca))} '
                  f'abaixo do previsto.')
    else:
        marca, sinal = '✅', '⚪ EM LINHA COM A PREVISÃO'
        resumo = (f'A entrada total ficou em R$ {brl(recebido)}, exatamente em '
                  f'linha com a previsão. ')

    partes = [
        f'📊 *ENTRADAS DO DIA | {data[:5]}*', '', LINHA, '',
        '🎯 *PREVISÃO*', f'R$ {brl(previsao)}', '',
        '💰 *VALOR RECEBIDO*', f'R$ {brl(recebido)} {marca}', '',
        '📈 *DIFERENÇA SOBRE A PREVISÃO*', sinal, '',
        LINHA, '',
        '💰 *RECEBIMENTO POR FORMA DE PAGAMENTO*', '',
    ]
    partes += [f'🔹 {rotulo}: R$ {brl(valor)}' for rotulo, valor in recebido_por_forma]
    partes += ['', LINHA, '', '📌 *RESUMO DO DIA*', '', resumo, LINHA]
    return '\n'.join(partes) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data', help='dia do recebimento (dd/mm/aaaa)')
    parser.add_argument('--previsao', type=float,
                        help='previsao daquele dia (a que foi mandada antes)')
    for flag, rotulo in FORMAS:
        parser.add_argument(f'--{flag.replace("_", "-")}', dest=flag, type=float,
                            help=f'recebido em {rotulo}')
    # decisao dela em 02/10: B2B e venda a prazo sao a mesma coisa. O --b2b
    # continua valendo como apelido para nao quebrar o que ela ja digita.
    parser.add_argument('--b2b', dest='a_prazo', type=float, help=argparse.SUPPRESS)
    parser.add_argument('--total-informado', dest='total_informado', type=float,
                        help='total que voce ja tem na mao; so para conferir a soma')
    parser.add_argument('--dados', help='JSON com data, previsao, recebido e total_informado')
    parser.add_argument('--saida', default='.', help='pasta de saida (padrao: atual)')
    args = parser.parse_args()

    dados = json.load(open(args.dados)) if args.dados else {}
    recebido_bruto = dados.get('recebido', {})

    data = args.data or dados.get('data')
    previsao = args.previsao if args.previsao is not None else dados.get('previsao')
    total_informado = (args.total_informado if args.total_informado is not None
                       else dados.get('total_informado'))

    if not data:
        raise SystemExit('ERRO: falta --data (ou "data" no JSON).')
    if previsao is None:
        raise SystemExit('ERRO: falta --previsao (ou "previsao" no JSON). '
                         'E a previsao que foi mandada para esse dia.')

    recebido_por_forma = []
    for flag, rotulo in FORMAS:
        valor = getattr(args, flag, None)
        if valor is None:
            valor = recebido_bruto.get(rotulo, recebido_bruto.get(flag))
        if valor is not None:
            recebido_por_forma.append((rotulo, float(valor)))

    if not recebido_por_forma:
        raise SystemExit('ERRO: nenhuma forma de pagamento informada.')

    recebido = sum(valor for _, valor in recebido_por_forma)

    # O total do texto e SEMPRE a soma das formas. Se voce passou um total na
    # mao e ele nao fecha, o script avisa em vez de mandar numero que nao soma.
    if total_informado is not None and abs(total_informado - recebido) > 0.005:
        diferenca = total_informado - recebido
        print('=' * 62, file=sys.stderr)
        print('ATENCAO: o total informado nao fecha com a soma das formas.',
              file=sys.stderr)
        print(f'  soma das formas : R$ {brl(recebido)}', file=sys.stderr)
        print(f'  total informado : R$ {brl(total_informado)}', file=sys.stderr)
        print(f'  falta explicar  : R$ {brl(diferenca)}', file=sys.stderr)
        print('  Ou falta uma forma no detalhamento, ou um dos valores esta errado.',
              file=sys.stderr)
        print('  O texto saiu com a SOMA DAS FORMAS.', file=sys.stderr)
        print('=' * 62, file=sys.stderr)

    os.makedirs(args.saida, exist_ok=True)
    destino = os.path.join(args.saida, 'texto_entradas.txt')
    with open(destino, 'w') as arquivo:
        arquivo.write(montar_texto(data, previsao, recebido_por_forma))

    print(f'ENTRADAS DE {data}')
    for rotulo, valor in recebido_por_forma:
        print(f'  {rotulo:<18} R$ {brl(valor):>13}')
    print(f'  {"= recebido":<18} R$ {brl(recebido):>13}')
    print(f'  {"previsao":<18} R$ {brl(previsao):>13}')
    print(f'  {"diferenca":<18} R$ {brl(recebido - previsao):>13}')
    print(f'\nGerado:\n  {destino}')


if __name__ == '__main__':
    main()
