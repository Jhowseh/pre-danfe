"""Diagnóstico (somente leitura) das notas fiscais no banco do SysPDV.

  python diagnostico.py              -> combinações de status e últimas notas
  python diagnostico.py --numero 123 -> todos os campos da nota 123, itens e emitente
"""
import argparse

from banco import conexao_leitura, linhas_dict

# Só as colunas da empresa que o DANFE usa. PROPRIO também guarda senhas
# (certificado, e-mail) e o certificado em si: essas nunca são lidas.
COLUNAS_EMITENTE = (
    "PRPCOD, PRPDES, PRPFAN, PRPCGC, PRPIERG, PRPINCMUN, PRPEND, PRPNUM, PRPCMP, "
    "PRPBAI, PRPMUN, PRPCODIBGE, PRPUF, PRPCEP, PRPTEL, PRPCRT, PRPREGESPTRB, PRPPAIS"
)


def colunas_sem_blob(cur, tabela):
    """Lista as colunas da tabela, tirando os BLOBs (XML, certificado...)."""
    cur.execute(
        """
        SELECT TRIM(RF.RDB$FIELD_NAME)
          FROM RDB$RELATION_FIELDS RF
          JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME = RF.RDB$FIELD_SOURCE
         WHERE RF.RDB$RELATION_NAME = ?
           AND F.RDB$FIELD_TYPE <> 261
         ORDER BY RF.RDB$FIELD_POSITION
        """,
        (tabela,),
    )
    return ", ".join(f'"{c[0]}"' for c in cur.fetchall())


def imprimir_tabela(regs, colunas):
    if not regs:
        print("  (nenhum registro)")
        return
    larg = {c: max(len(c), *(len(str(r[c] if r[c] is not None else "")) for r in regs)) for c in colunas}
    print("  " + " | ".join(c.ljust(larg[c]) for c in colunas))
    print("  " + "-+-".join("-" * larg[c] for c in colunas))
    for r in regs:
        print("  " + " | ".join(str(r[c] if r[c] is not None else "").ljust(larg[c]) for c in colunas))


def imprimir_registro(reg):
    for k, v in reg.items():
        if v not in (None, "", 0):
            print(f"  {k:<16} = {v!r}")


def resumo(cur):
    print("\n== Combinações de tipo/status em NOTAFISCAL ==")
    cur.execute(
        """
        SELECT NFSTIP, NFSTNF, NFSSTATNFE, NFSACAONFE,
               IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS TEM_XML,
               IIF(COALESCE(NFSPROTNFE, '') = '', 'N', 'S') AS TEM_PROT,
               COUNT(*) AS QTD, MAX(NFSDATEMI) AS ULTIMA
          FROM NOTAFISCAL
         GROUP BY 1, 2, 3, 4, 5, 6
         ORDER BY 7 DESC
        """
    )
    regs = linhas_dict(cur)
    imprimir_tabela(regs, ["NFSTIP", "NFSTNF", "NFSSTATNFE", "NFSACAONFE", "TEM_XML", "TEM_PROT", "QTD", "ULTIMA"])

    print("\n== Últimas 20 notas ==")
    cur.execute(
        """
        SELECT FIRST 20 NFSCTR, NFSNUM, NFSSER, NFSTIP, NFSTNF, NFSDATEMI, NFSCLIDES,
               NFSVLR, NFSSTATNFE, NFSACAONFE,
               IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS TEM_XML,
               SUBSTRING(COALESCE(NFSMENSNFE, '') FROM 1 FOR 40) AS MENSAGEM
          FROM NOTAFISCAL
         ORDER BY NFSDATEMI DESC, NFSCTR DESC
        """
    )
    regs = linhas_dict(cur)
    imprimir_tabela(regs, ["NFSCTR", "NFSNUM", "NFSSER", "NFSTIP", "NFSTNF", "NFSDATEMI", "NFSCLIDES",
                           "NFSVLR", "NFSSTATNFE", "NFSACAONFE", "TEM_XML", "MENSAGEM"])


def detalhe(cur, numero):
    cols = colunas_sem_blob(cur, "NOTAFISCAL")
    cur.execute(
        f"""
        SELECT {cols}, IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS TEM_XML
          FROM NOTAFISCAL
         WHERE TRIM(LEADING '0' FROM TRIM(NFSNUM)) = ?
         ORDER BY NFSDATEMI DESC
        """,
        (str(int(numero)),),
    )
    notas = linhas_dict(cur)
    if not notas:
        print(f"Nenhuma nota com número {numero}.")
        return
    print(f"{len(notas)} nota(s) com número {numero} (podem ser séries/tipos diferentes).")

    cols_item = colunas_sem_blob(cur, "ITEM_NOTA_FISCAL")
    for nota in notas:
        print(f"\n== NOTAFISCAL  NFSCTR={nota['NFSCTR']} (campos vazios/zero omitidos) ==")
        imprimir_registro(nota)

        cur.execute(
            f"SELECT {cols_item} FROM ITEM_NOTA_FISCAL WHERE NFSCTR = ? ORDER BY INFSEQ",
            (nota["NFSCTR"],),
        )
        for item in linhas_dict(cur):
            print(f"\n  -- item {item['INFSEQ']} --")
            imprimir_registro(item)

        for tabela in ("NOTAFISCAL_REFERENCIA", "IMPOSTO_SAIDA", "NOTA_FISCAL_TRANSACAO"):
            cur.execute(f"SELECT {colunas_sem_blob(cur, tabela)} FROM {tabela} WHERE NFSCTR = ?", (nota["NFSCTR"],))
            regs = linhas_dict(cur)
            if regs:
                print(f"\n  -- {tabela} --")
                for r in regs:
                    imprimir_registro(r)

    print("\n== Emitente (PROPRIO) ==")
    cur.execute(f"SELECT {COLUNAS_EMITENTE} FROM PROPRIO")
    for r in linhas_dict(cur):
        imprimir_registro(r)
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--numero", help="número da nota (NFSNUM)")
    args = ap.parse_args()
    with conexao_leitura() as cur:
        if args.numero:
            detalhe(cur, args.numero)
        else:
            resumo(cur)


if __name__ == "__main__":
    main()
