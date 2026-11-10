<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/capa-escura.png">
    <img src="docs/capa-clara.png" alt="Pré-DANFE — Veja o DANFE da sua NF-e antes de transmitir no SysPDV" width="820">
  </picture>
</p>

# Pré-DANFE SysPDV

Gera um PDF no layout oficial do DANFE, com a marca **"SEM VALOR FISCAL – PRÉ-VISUALIZAÇÃO"**,
de NF-e (modelo 55) digitadas no **SysPDV** e ainda **não transmitidas**.
Serve para conferir a nota (itens, impostos, cliente) antes de transmitir.

O programa só **lê** o banco Firebird do SysPDV — nunca grava nada nele.

## Download

Baixe a versão mais recente em **[Releases](https://github.com/Jhowseh/pre-danfe/releases/latest)**:

- `PreDANFE.exe` e/ou `PreDANFE-Automatico.exe` — os programas prontos (não precisa instalar Python);
- `Manual-PreDANFE.pdf` — manual completo, com imagens;
- `LEIA-ME.txt` — instruções rápidas.

Coloque os arquivos numa mesma pasta (ex.: `C:\PreDanfe`) e abra um dos programas.
Na primeira vez ele pede os dados do banco do SysPDV e cria o `config.ini` sozinho.

## Programas

| Programa | O que faz |
|---|---|
| `PreDANFE.exe` (V1) | Digite o número da NF-e e clique em **Gerar Pré-DANFE**. A janela também lista as notas pendentes (clique em uma para gerar). |
| `PreDANFE-Automatico.exe` (V2) | Fica perto do relógio e gera sozinho o PDF de toda NF-e nova ou alterada ainda não transmitida (`PreDANFE_<número>.pdf`). |
| `PreDANFE.bat` | Versão de linha de comando: lista as pendentes, você digita a linha e o PDF abre. |

Instruções para o usuário final: [`docs/LEIA-ME.txt`](docs/LEIA-ME.txt) e o manual em PDF
gerado por `predanfe/manual/build_manual.py` (os dois vão junto em cada release).

## Estrutura

```
PreDanfe/
├── PreDANFE.bat            atalho da linha de comando
├── CLAUDE.md               regras do projeto (sem comentários no código, código em inglês)
├── LICENSE, NOTICE         licença Apache 2.0 e créditos
├── requirements.txt        dependências Python
├── docs/
│   ├── arquitetura.md      como cada módulo funciona e por quê
│   ├── LEIA-ME.txt         instruções para o usuário final
│   ├── capa-*.png          faixa do topo deste README (manual/readme_cover.py)
│   └── referencia-visual/  ícones SVG que o theme.py redesenha
└── predanfe/               código-fonte
    ├── app_v1.py           janela V1 (sob demanda)
    ├── app_v2.py           V2 automático (ícone na bandeja)
    ├── predanfe.py         linha de comando
    ├── generator.py        núcleo comum: busca a nota, monta e gera o PDF
    ├── database.py         conexão somente leitura com o Firebird
    ├── nfe_xml.py          monta o XML da NF-e a partir das tabelas
    ├── approx_taxes.py     tributos aproximados (IBPT) aprendidos das notas
    ├── lazy_imports.py     evita carregar módulos pesados que não são usados
    ├── theme.py            visual (cores, ícones, botões, claro/escuro)
    ├── config_window.py, about_window.py, tray_menu.py, app_utils.py
    ├── validate.py         conferência contra as notas autorizadas
    ├── diagnostics.py      mostra os campos crus de uma nota
    ├── build.py            compila os .exe e monta a pasta dist/
    ├── version.py          versão e créditos
    ├── config.example.ini  modelo do config.ini
    ├── fbclient/           cliente Firebird 5.0 64 bits (vai embutido nos .exe)
    ├── resources/          ícone e logos
    └── manual/             gerador do manual em PDF (com dados fictícios)
```

O funcionamento interno de cada módulo está em [`docs/arquitetura.md`](docs/arquitetura.md).
O código não tem comentários: toda explicação fica na documentação (veja [`CLAUDE.md`](CLAUDE.md)).

## Instalação para desenvolvimento

1. Python 3.12 **64 bits** (python.org), marcando "Add python.exe to PATH".
2. Instale as dependências:
   ```bash
   python -m pip install -r requirements.txt
   ```
   `pyinstaller` só é usado para compilar os .exe (`build.py`), e `pypdfium2` só para refazer o manual
   (`manual/screenshots.py`).
3. Copie `predanfe/config.example.ini` para `predanfe/config.ini` e preencha a senha do banco.
   O `config.ini` fica só no computador local e não vai para o Git, porque tem a senha do banco.

### `config.ini`

| Chave | O que é |
|---|---|
| `[banco] host`, `porta` | Servidor Firebird do SysPDV (2.5, porta 3050). |
| `[banco] arquivo` | Banco da retaguarda (o SysPDV registra em `HKLM\SOFTWARE\WOW6432Node\Syspdv_server\UniConnection`). |
| `[banco] usuario`, `senha` | Acesso ao banco. |
| `[banco] fbclient` | `fbclient.dll` **64 bits**. Em branco, usa o que vem no programa (pasta `predanfe/fbclient`); se preencher, precisa ser um de 64 bits (ex.: o do Firebird 5.0 instalado). |
| `[automatico] intervalo_segundos` | De quantos em quantos segundos o PreDANFE-Automatico verifica o banco (mínimo 3). |
| `[saida] pasta_pdf` | Pasta onde os PDFs são gravados (relativa à pasta do programa ou absoluta). Nada é gravado na pasta do SysPDV. |

As chaves continuam em português para não quebrar o `config.ini` de quem já usa o programa.

## Uso pela linha de comando

Dentro de `predanfe/`:

- `python predanfe.py` – lista as pendentes e pergunta qual gerar.
- `python predanfe.py --number 4194` – gera direto a nota 4194.
- `python predanfe.py --number 4194 --xml` – salva também o XML montado.
- `python predanfe.py --number 4149 --compare` – nota já transmitida: gera o
  pré-DANFE e o DANFE do XML oficial para comparar.
- `--no-open` – não abre o PDF ao final.

Os PDFs ficam em `predanfe/pdf` (configurável em `[saida] pasta_pdf`).

## Compilar os .exe

```bash
python predanfe/build.py
```

Gera `dist/PreDANFE.exe`, `dist/PreDANFE-Automatico.exe` e copia o `LEIA-ME.txt`,
o `LICENSE.txt` e o `NOTICE.txt`.
Para refazer o manual: `python predanfe/manual/screenshots.py` (só quando as telas mudarem) e depois
`python predanfe/manual/build_manual.py` (grava `dist/Manual-PreDANFE.pdf`).

A pasta `dist/` não vai para o Git (pode ter `config.ini` com senha e PDFs de clientes).
Para publicar uma versão, crie uma release em GitHub → Releases com a tag `v<versão>`
(a de `predanfe/version.py`) e anexe só `PreDANFE.exe`, `PreDANFE-Automatico.exe`,
`Manual-PreDANFE.pdf`, `LEIA-ME.txt`, `LICENSE.txt` e `NOTICE.txt` — **nunca o `config.ini` nem a pasta `pdf`**.

## Conferência

- `python validate.py` – monta o XML de todas as notas já autorizadas a partir
  das tabelas e compara com o XML oficial, campo a campo.
- `python validate.py --latest 20` – só as 20 notas mais recentes; `--detail` mostra cada divergência.
- `python validate.py --before pdf\PreDANFE_4194.xml --number 4194` – depois
  de transmitir uma nota, compara o pré-DANFE salvo antes (com `predanfe.py --xml`) com o XML final.
- `python diagnostics.py` – combinações de status e últimas notas; `--number 123` mostra todos os
  campos da nota 123, itens e emitente.

Resultado: com o histórico só até cada nota, 146 de 178 idênticas; com todo o
histórico (uso real), 161 de 178. Na conferência, os % do IBPT de cada nota são aprendidos só com as
notas transmitidas antes dela, para o resultado ser honesto.

## Valores que o SysPDV só calcula na transmissão

O pré-DANFE calcula como ele (conferido com as notas autorizadas):

- **PIS/COFINS** (CST 01): base gravada × alíquota do regime (`PROPRIO.PRPREGFED`:
  R = 1,65%/7,60%; P = 0,65%/3,00%), meio centavo exato arredonda para baixo.
- **Tributos aproximados (IBPT)** — `approx_taxes.py`: o SysPDV não grava os %
  (tabela NCM zerada; o arquivo `C:\Syspdv\<versão>.ibpt` é de 2024). Os % de cada
  NCM são aprendidos das notas transmitidas: item = arred(base×federal) +
  arred(base×estadual); o texto "Val Aprox Tributos..." usa um par próprio por NCM.
  NCM sem histórico: federal do arquivo .ibpt + estadual mais comum (marcado como estimado).
- **Texto das informações complementares**: sem acentos, hífen vira espaço;
  "Valor Total FCP: R$ x" quando há FCP; devolução recebe "Valor do IPI" e "Nota Ref.".
- **Fatura** sem linhas de duplicata (o SysPDV só lista a fatura).
- Devolução (finalidade 4) não leva tributos aproximados.

## Como a nota pendente é reconhecida

`NOTAFISCAL` com `NFSTIP <> 'CAN'`, `NFSSTATNFE` vazio e sem XML (`NFSXMLEMINFE`).
Notas transmitidas ficam com `NFSSTATNFE = 'AU'`; canceladas, `NFSACAONFE = 'CA'`.

## Segurança

- Toda consulta usa transação **somente leitura** do Firebird e termina em rollback.
- Nenhum arquivo da pasta `C:\Syspdv` é alterado.
- Da tabela `PROPRIO` só são lidos dados cadastrais (nunca senhas nem certificado).
- A senha do banco fica apenas no `config.ini` local, que não vai para o Git.

## Créditos

PBtec – Soluções em Automação · (83) 3224-3080
Desenvolvimento: Erick Henrique e José Henrique.

## Licença

Distribuído sob a [Apache License 2.0](LICENSE). Você pode usar, modificar e
redistribuir o Pré-DANFE, inclusive em projetos comerciais, desde que:

- mantenha o arquivo [`NOTICE`](NOTICE) com os créditos ao distribuir o programa
  ou uma versão modificada dele;
- indique nos arquivos alterados que eles foram modificados.

O nome e o logo da PBtec não estão incluídos na licença.
