import argparse

from database import read_only_connection, rows_as_dicts

DESCRIPTION = "Diagnóstico (somente leitura) das notas fiscais no banco do SysPDV."

ISSUER_COLUMNS = (
    "PRPCOD, PRPDES, PRPFAN, PRPCGC, PRPIERG, PRPINCMUN, PRPEND, PRPNUM, PRPCMP, "
    "PRPBAI, PRPMUN, PRPCODIBGE, PRPUF, PRPCEP, PRPTEL, PRPCRT, PRPREGESPTRB, PRPPAIS"
)


def non_blob_columns(cur, table):
    cur.execute(
        """
        SELECT TRIM(RF.RDB$FIELD_NAME)
          FROM RDB$RELATION_FIELDS RF
          JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME = RF.RDB$FIELD_SOURCE
         WHERE RF.RDB$RELATION_NAME = ?
           AND F.RDB$FIELD_TYPE <> 261
         ORDER BY RF.RDB$FIELD_POSITION
        """,
        (table,),
    )
    return ", ".join(f'"{c[0]}"' for c in cur.fetchall())


def print_table(rows, columns):
    if not rows:
        print("  (nenhum registro)")
        return
    widths = {c: max(len(c), *(len(str(r[c] if r[c] is not None else "")) for r in rows)) for c in columns}
    print("  " + " | ".join(c.ljust(widths[c]) for c in columns))
    print("  " + "-+-".join("-" * widths[c] for c in columns))
    for r in rows:
        print("  " + " | ".join(str(r[c] if r[c] is not None else "").ljust(widths[c]) for c in columns))


def print_record(record):
    for k, v in record.items():
        if v not in (None, "", 0):
            print(f"  {k:<16} = {v!r}")


def summary(cur):
    print("\n== Combinações de tipo/status em NOTAFISCAL ==")
    cur.execute(
        """
        SELECT NFSTIP, NFSTNF, NFSSTATNFE, NFSACAONFE,
               IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS HAS_XML,
               IIF(COALESCE(NFSPROTNFE, '') = '', 'N', 'S') AS HAS_PROT,
               COUNT(*) AS QTY, MAX(NFSDATEMI) AS LATEST
          FROM NOTAFISCAL
         GROUP BY 1, 2, 3, 4, 5, 6
         ORDER BY 7 DESC
        """
    )
    rows = rows_as_dicts(cur)
    print_table(rows, ["NFSTIP", "NFSTNF", "NFSSTATNFE", "NFSACAONFE", "HAS_XML", "HAS_PROT", "QTY", "LATEST"])

    print("\n== Últimas 20 notas ==")
    cur.execute(
        """
        SELECT FIRST 20 NFSCTR, NFSNUM, NFSSER, NFSTIP, NFSTNF, NFSDATEMI, NFSCLIDES,
               NFSVLR, NFSSTATNFE, NFSACAONFE,
               IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS HAS_XML,
               SUBSTRING(COALESCE(NFSMENSNFE, '') FROM 1 FOR 40) AS MESSAGE
          FROM NOTAFISCAL
         ORDER BY NFSDATEMI DESC, NFSCTR DESC
        """
    )
    rows = rows_as_dicts(cur)
    print_table(rows, ["NFSCTR", "NFSNUM", "NFSSER", "NFSTIP", "NFSTNF", "NFSDATEMI", "NFSCLIDES",
                       "NFSVLR", "NFSSTATNFE", "NFSACAONFE", "HAS_XML", "MESSAGE"])


def detail(cur, number):
    cols = non_blob_columns(cur, "NOTAFISCAL")
    cur.execute(
        f"""
        SELECT {cols}, IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS HAS_XML
          FROM NOTAFISCAL
         WHERE TRIM(LEADING '0' FROM TRIM(NFSNUM)) = ?
         ORDER BY NFSDATEMI DESC
        """,
        (str(int(number)),),
    )
    invoices = rows_as_dicts(cur)
    if not invoices:
        print(f"Nenhuma nota com número {number}.")
        return
    print(f"{len(invoices)} nota(s) com número {number} (podem ser séries/tipos diferentes).")

    item_cols = non_blob_columns(cur, "ITEM_NOTA_FISCAL")
    for inv in invoices:
        print(f"\n== NOTAFISCAL  NFSCTR={inv['NFSCTR']} (campos vazios/zero omitidos) ==")
        print_record(inv)

        cur.execute(
            f"SELECT {item_cols} FROM ITEM_NOTA_FISCAL WHERE NFSCTR = ? ORDER BY INFSEQ",
            (inv["NFSCTR"],),
        )
        for item in rows_as_dicts(cur):
            print(f"\n  -- item {item['INFSEQ']} --")
            print_record(item)

        for table in ("NOTAFISCAL_REFERENCIA", "IMPOSTO_SAIDA", "NOTA_FISCAL_TRANSACAO"):
            cur.execute(f"SELECT {non_blob_columns(cur, table)} FROM {table} WHERE NFSCTR = ?", (inv["NFSCTR"],))
            rows = rows_as_dicts(cur)
            if rows:
                print(f"\n  -- {table} --")
                for r in rows:
                    print_record(r)

    print("\n== Emitente (PROPRIO) ==")
    cur.execute(f"SELECT {ISSUER_COLUMNS} FROM PROPRIO")
    for r in rows_as_dicts(cur):
        print_record(r)
        print()


def main():
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument("--number", help="número da nota (NFSNUM)")
    args = ap.parse_args()
    with read_only_connection() as cur:
        if args.number:
            detail(cur, args.number)
        else:
            summary(cur)


if __name__ == "__main__":
    main()
