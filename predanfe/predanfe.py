import argparse
import os
import sys

from database import read_only_connection
from generator import (build, file_name, find_by_number, list_pending, official_pdf, output_dir, predanfe_pdf,
                       save)

DESCRIPTION = "Pré-DANFE do SysPDV (linha de comando): lista as NF-e não transmitidas e gera o PDF."


def currency(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def choose_pending(cur):
    invoices = list_pending(cur)
    if not invoices:
        print("Nenhuma NF-e pendente (todas já foram transmitidas ou canceladas).")
        return None
    print("\nNF-e pendentes de transmissão:\n")
    for i, inv in enumerate(invoices, start=1):
        date = inv["NFSDATEMI"].strftime("%d/%m/%Y") if inv["NFSDATEMI"] else "--"
        print(f"  {i:>2}) Nº {int(inv['NFSNUM']):>6}  série {inv['NFSSER']:<3} {date}  "
              f"R$ {currency(inv['NFSVLR']):>11}  {inv['NFSCLIDES'] or ''}")
    while True:
        try:
            answer = input("\nNúmero da linha (Enter para sair): ").strip().lstrip("\ufeff")
        except EOFError:
            return None
        if not answer:
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(invoices):
            return invoices[int(answer) - 1]
        print("Opção inválida.")


def main():
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument("--number", help="número da NF-e (NFSNUM)")
    ap.add_argument("--compare", action="store_true", help="também gera o DANFE do XML oficial (nota já transmitida)")
    ap.add_argument("--xml", action="store_true", help="salva também o XML montado (para conferência)")
    ap.add_argument("--no-open", action="store_true", help="não abre o PDF ao final")
    args = ap.parse_args()

    folder = output_dir()
    with read_only_connection() as cur:
        if args.number:
            found = find_by_number(cur, args.number)
            if not found:
                sys.exit(f"Nota {args.number} não encontrada.")
            if len(found) > 1:
                print(f"Atenção: {len(found)} notas com número {args.number}; usando a primeira.")
            invoice = found[0]
            if invoice["HAS_XML"] == "S" and not args.compare:
                print("Esta nota já foi transmitida. O pré-DANFE será gerado mesmo assim, a partir das tabelas.")
        else:
            invoice = choose_pending(cur)
            if invoice is None:
                return

        number = int(invoice["NFSNUM"])
        xml, key, warnings = build(cur, invoice["NFSCTR"])
        target = save(folder, file_name(number), predanfe_pdf(xml))
        if args.xml:
            save(folder, file_name(number, extension=".xml"), xml.encode("utf-8"))
        print(f"\nPré-DANFE gerado: {target}")
        print(f"Chave prevista:   {key}")
        for w in warnings:
            print(f"  AVISO: {w}")

        to_open = [target]
        if args.compare:
            official = save(folder, file_name(number, "DANFE_oficial"), official_pdf(cur, invoice["NFSCTR"]))
            print(f"DANFE oficial:    {official}")
            to_open.append(official)

    if not args.no_open:
        for path in to_open:
            os.startfile(path)


if __name__ == "__main__":
    main()
