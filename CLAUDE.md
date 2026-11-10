# Regras do projeto

## Sem comentários no código

- Nunca adicione comentários no código: nem `#`, nem docstrings, nem `rem` em `.bat`, nem `;` em `.ini`,
  nem diretivas como `# noqa`.
- Toda informação (por que algo existe, regras fiscais, decisões, limitações) vai para a documentação:
  `README.md` (uso e visão geral) ou `docs/arquitetura.md` (funcionamento interno de cada módulo).
- Ao mudar um comportamento descrito na documentação, atualize a documentação no mesmo commit.
- O código deve se explicar pelos nomes. Se precisar de explicação, ela vai para a documentação.

## Código em inglês

- Nomes de arquivos, pastas, módulos, classes, funções, variáveis, constantes e opções de linha de
  comando ficam em inglês.
- Continuam em português:
  - textos que pessoas leem: janelas, mensagens, saída da linha de comando, ajuda do `argparse`, logs,
    conteúdo do PDF e do manual;
  - formatos já gravados nas máquinas dos clientes: chaves do `config.ini` (`[banco] senha`,
    `[saida] pasta_pdf`, `[automatico] intervalo_segundos`...), o arquivo de estado
    `automatico_estado.json` e os nomes dos logs. Renomear essas chaves quebraria as instalações existentes;
  - nomes de tabelas e colunas do SysPDV (`NOTAFISCAL`, `NFSNUM`...) e tags do XML da NF-e;
  - nomes dos executáveis (`PreDANFE.exe`, `PreDANFE-Automatico.exe`) e do manual (`Manual-PreDANFE.pdf`).

## Estrutura

- Saída do build e do manual: `dist/` (fora do Git).
- Documentação em português, em `README.md` e `docs/`.
