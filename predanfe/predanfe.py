"""Pré-DANFE do SysPDV (linha de comando).

  python predanfe.py                -> lista as NF-e pendentes e pergunta qual gerar
  python predanfe.py --numero 4194  -> gera direto a nota 4194
  python predanfe.py --numero 4149 --comparar
        -> nota já transmitida: gera o pré-DANFE (das tabelas) e o DANFE do XML
           oficial, para conferir diferenças
"""
import argparse
import os
import sys

from banco import conexao_leitura
from gerador import (buscar_por_numero, listar_pendentes, montar, nome_arquivo, pasta_saida,
                     pdf_oficial, pdf_predanfe, salvar)


def moeda(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def escolher_pendente(cur):
    notas = listar_pendentes(cur)
    if not notas:
        print("Nenhuma NF-e pendente (todas já foram transmitidas ou canceladas).")
        return None
    print("\nNF-e pendentes de transmissão:\n")
    for i, n in enumerate(notas, start=1):
        data = n["NFSDATEMI"].strftime("%d/%m/%Y") if n["NFSDATEMI"] else "--"
        print(f"  {i:>2}) Nº {int(n['NFSNUM']):>6}  série {n['NFSSER']:<3} {data}  "
              f"R$ {moeda(n['NFSVLR']):>11}  {n['NFSCLIDES'] or ''}")
    while True:
        try:
            resp = input("\nNúmero da linha (Enter para sair): ").strip().lstrip("\ufeff")
        except EOFError:
            return None
        if not resp:
            return None
        if resp.isdigit() and 1 <= int(resp) <= len(notas):
            return notas[int(resp) - 1]
        print("Opção inválida.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--numero", help="número da NF-e (NFSNUM)")
    ap.add_argument("--comparar", action="store_true", help="também gera o DANFE do XML oficial (nota já transmitida)")
    ap.add_argument("--xml", action="store_true", help="salva também o XML montado (para conferência)")
    ap.add_argument("--nao-abrir", action="store_true", help="não abre o PDF ao final")
    args = ap.parse_args()

    pasta = pasta_saida()
    with conexao_leitura() as cur:
        if args.numero:
            achadas = buscar_por_numero(cur, args.numero)
            if not achadas:
                sys.exit(f"Nota {args.numero} não encontrada.")
            if len(achadas) > 1:
                print(f"Atenção: {len(achadas)} notas com número {args.numero}; usando a primeira.")
            nota = achadas[0]
            if nota["TEM_XML"] == "S" and not args.comparar:
                print("Esta nota já foi transmitida. O pré-DANFE será gerado mesmo assim, a partir das tabelas.")
        else:
            nota = escolher_pendente(cur)
            if nota is None:
                return

        num = int(nota["NFSNUM"])
        xml, chave, avisos = montar(cur, nota["NFSCTR"])
        destino = salvar(pasta, nome_arquivo(num), pdf_predanfe(xml))
        if args.xml:
            salvar(pasta, nome_arquivo(num, extensao=".xml"), xml.encode("utf-8"))
        print(f"\nPré-DANFE gerado: {destino}")
        print(f"Chave prevista:   {chave}")
        for a in avisos:
            print(f"  AVISO: {a}")

        abrir = [destino]
        if args.comparar:
            oficial = salvar(pasta, nome_arquivo(num, "DANFE_oficial"), pdf_oficial(cur, nota["NFSCTR"]))
            print(f"DANFE oficial:    {oficial}")
            abrir.append(oficial)

    if not args.nao_abrir:
        for arq in abrir:
            os.startfile(arq)


if __name__ == "__main__":
    main()
