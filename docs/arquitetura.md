# Arquitetura do Pré-DANFE

Como cada parte do código funciona e por que foi feita assim. Uso e instalação estão no
[README](../README.md). O código não tem comentários: as explicações ficam aqui.

## Visão geral

```
app_v1.py (janela)  ─┐
app_v2.py (bandeja) ─┼─> generator.py ─> nfe_xml.py ─> approx_taxes.py
predanfe.py (CLI)   ─┘         │              │
                               └──────> database.py (Firebird, somente leitura)
```

`generator.py` é o núcleo comum: busca as notas, monta o XML e desenha o PDF. Os três programas só
mudam a forma de pedir e mostrar o resultado.

## database.py — acesso ao banco

- Toda consulta roda numa transação **READ ONLY** do Firebird (`read_only_connection`): o próprio
  servidor recusa INSERT/UPDATE/DELETE. No fim, a transação é desfeita (rollback), nunca confirmada.
- `APP_DIR` é a pasta do programa (do `.exe` quando compilado, do código-fonte fora dele). Lá ficam o
  `config.ini` e a pasta de PDFs. `RESOURCES` é a pasta `_internal` do programa compilado, onde
  ficam os arquivos embutidos (`fbclient/`, `resources/`).
- Logs e estado do modo automático ficam em `%LOCALAPPDATA%\PreDANFE` (`LOG_DIR`).
- `syspdv_defaults` lê do registro (`HKLM\SOFTWARE\WOW6432Node\Syspdv_server\UniConnection`) o
  servidor, a porta e o banco que o SysPDV da máquina usa, para preencher a configuração.
- `fbclient.dll` (64 bits) é procurado nesta ordem: o do `config.ini`, o embutido no programa, o da pasta
  `fbclient/` e o do Firebird 5.0 instalado. Ele é carregado uma vez só, protegido por uma trava,
  porque `tpb()` já carrega a DLL e o modo automático usa várias threads.
- `save_config` só grava a chave `fbclient` quando alguém apontou uma DLL.
- `ConfigError` herda de `SystemExit`: na linha de comando, o programa sai mostrando a mensagem.

## lazy_imports.py — economia de memória

Importado antes do `firebird-driver` e do `brazilfiscalreport`. Ele troca dois módulos pesados, que as
bibliotecas importam mas o programa não usa, por módulos substitutos. Isso economiza ~8 MB:

- `unittest.mock`: o fpdf o importa só para assinar PDFs digitalmente, e ele carrega o asyncio inteiro.
- `firebird.base.config_pb2`: o firebird-driver o importa só para configuração em protobuf, e ele
  carrega o protobuf do Google.

Se algo for usado de fato, o módulo verdadeiro é carregado na hora e a chamada segue normalmente. Os
atributos `__xxx__` que o próprio `import` consulta não disparam esse carregamento.

## generator.py — núcleo

- **Nota pendente**: `NFSTIP <> 'CAN'`, `NFSSTATNFE` vazio e sem XML gravado (`NFSXMLEMINFE`).
- `predanfe_class` escolhe o layout oficial (MOC 7.0 ou NT 2026.010) pela data de emissão e
  sobrescreve dois métodos do `brazilfiscalreport`: o protocolo vira "NAO TRANSMITIDA" e a marca d'água
  vira "SEM VALOR FISCAL / PRÉ-VISUALIZAÇÃO" (54 pt, girada 55°, vermelho claro).
- `PREVIEW_NOTICE` entra no início das informações complementares.
- `official_pdf` desenha o DANFE do XML que o SysPDV gravou depois da transmissão (para comparar).
- `save`: se o PDF de destino estiver aberto (bloqueado pelo leitor de PDF), grava com o horário no nome.

## nfe_xml.py — XML da NF-e a partir das tabelas

Monta um XML NF-e 4.00, sem assinatura, que serve só para desenhar o pré-DANFE. O mapeamento dos
campos foi tirado de notas reais já autorizadas (o XML gravado em `NOTAFISCAL.NFSXMLEMINFE`).

- **Chave de acesso**: o SysPDV usa o `NFSCTR` como código numérico (`cNF`). O dígito verificador é
  módulo 11 com pesos de 2 a 9. Se a chave gravada no banco for diferente da calculada, sai um aviso.
- **Município (IBGE)**: procurado pelo nome da cidade + UF em `FISCO_CODIGOIBGE` (como o SysPDV faz),
  comparando sem acentos. Se não achar, usa o código do cadastro do cliente.
- **NCM do item**: o do item; se vazio, o da nota de entrada referenciada (devoluções); por último, o do
  cadastro do produto.
- **Emitente**: da tabela `PROPRIO` só são lidos dados cadastrais. Ela também guarda senhas e o
  certificado, que nunca são lidos.
- **vProd e desconto**: no banco, o total do item já vem sem o desconto. No XML, `vProd` é
  quantidade × unitário e o desconto vai separado em `vDesc`.
- **PIS/COFINS CST 01**: o SysPDV grava a base ao salvar, mas a alíquota e o valor só na transmissão,
  pelo regime federal da empresa (`PROPRIO.PRPREGFED`): R (lucro real) = 1,65%/7,60%;
  P (lucro presumido) = 0,65%/3,00%. Meio centavo exato arredonda para baixo (`ROUND_HALF_DOWN`):
  1,995 → 1,99.
- **ICMS**: CST 41 e 50 usam o grupo `ICMS40`. Simples Nacional (CRT 1 ou 2) usa `ICMSSN<CSOSN>`.
- **Cobrança**: nota a prazo (P) ou à vista (V) tem fatura, mas sem linhas de duplicata (o SysPDV não
  lista duplicatas em 177 de 178 notas conferidas). Sem pagamento (N) e devolução (finalidade 4) não
  têm fatura.
- **Informações complementares**, como o SysPDV monta na transmissão:
  - o modelo "Val Aprox Tributos ... R$ 0,00" que o SysPDV grava na observação recebe os valores
    calculados;
  - antes da observação entram "Valor do IPI" e "Nota Ref." (devolução) e "Valor Total FCP" (se houver FCP);
  - o texto sai sem acentos, com hífen virando espaço e espaços repetidos juntados;
  - se algum NCM usou % estimado, o aviso do pré-DANFE ganha "(TRIBUTOS APROXIMADOS ESTIMADOS PARA
    NCM ...)", porque o modo automático não mostra avisos na tela.
- **Devolução** (finalidade 4) não leva tributos aproximados.
- **Avisos** devolvidos junto com o XML: chave diferente da gravada, total do item diferente de
  quantidade × unitário − desconto, total da nota diferente da soma das parcelas e NCM sem % do IBPT.

## approx_taxes.py — tributos aproximados (Lei 12.741, "IBPT")

O SysPDV usa, por NCM, um % federal e um % estadual. O valor do item é
`arred(base × federal / 100) + arred(base × estadual / 100)`, e as informações complementares
recebem os totais federal e estadual.

Os % não ficam gravados no banco: a tabela NCM está zerada e o arquivo `C:\Syspdv\<versão>.ibpt` é de 2024.
Por isso eles são **aprendidos** das notas já transmitidas:

1. Lê as 600 notas transmitidas mais recentes (`HISTORY_INVOICES`), sem devoluções, e usa até 40 itens
   por NCM (`ITEMS_PER_NCM`).
2. Para cada estadual candidato (os vistos nas notas e as alíquotas usuais de ICMS), calcula o intervalo
   de % federal que reproduz todos os itens centavo a centavo. Se nenhum par serve para todos, reduz
   pela metade o período, ficando com os itens mais recentes, até achar.
3. Quando vários pares explicam os itens (NCM com pouco histórico), fica o par que serve para mais NCMs
   da empresa (ex.: 13,45+18 nos alimentos).
4. **Par do texto** (`text_rates`): em alguns NCMs o SysPDV usa % diferentes no valor do item e no texto
   "Federais/Estaduais" (ex.: água 22011000, itens 13,45+20 e texto 14,21+20). Para cada NCM, entre
   os pares candidatos, escolhe o que faz mais notas baterem exatamente no texto. Notas com um só
   NCM dão o par direto. O processo repete até estabilizar (até 6 voltas), porque uma nota tem vários
   NCMs. Sem nenhuma nota exata, o texto usa o par dos itens.
5. **NCM sem histórico**: % federal do arquivo `.ibpt` do SysPDV mais o estadual mais comum nas notas
   (o estadual do arquivo está desatualizado). O PDF marca esses NCMs como estimados.

O arquivo `.ibpt` é zlib + CSV. Os mesmos % se repetem em milhares de NCMs, então cada combinação vira
um único trio de `Decimal` compartilhado (a tabela cai de ~4,4 MB para ~1 MB). A tabela aprendida fica
em cache por 10 minutos.

## app_v1.py — janela (PreDANFE.exe)

- O acesso ao banco roda em segundo plano (`app_utils.run_in_background`): se o servidor demorar, a
  janela continua respondendo.
- A lista de pendentes é um `Canvas` com cartões. A altura acompanha a quantidade de notas (1 a 4
  cartões; acima disso, a lista rola). A rolagem é animada: a roda do mouse só muda o destino, e cada
  quadro percorre 22% do que falta, corrigido pelo intervalo real entre quadros. Assim touchpads
  (deltas pequenos) e mouses ficam proporcionais.
- O painel "Sobre" troca com o conteúdo deslizando na horizontal (240 ms, desacelerando no fim). O
  tamanho da área é travado durante a troca para a janela não "pular".
- Uma instância só (mutex `Local\PreDANFE`). Ao abrir de novo, a janela existente vem para a frente.

## app_v2.py — modo automático (PreDANFE-Automatico.exe)

- Roda em segundo plano, com ícone na bandeja. A cada `[automatico] intervalo_segundos` (mínimo 3,
  padrão 10) lê as notas pendentes.
- Para não pegar uma nota no meio da gravação, só gera o PDF quando o XML montado fica igual (mesmo
  SHA-1) em **duas verificações seguidas**.
- O estado (`automatico_estado.json`, em `%LOCALAPPDATA%\PreDANFE`) guarda o hash e o arquivo de cada
  nota já gerada. Uma nota só é refeita se mudou ou se o PDF sumiu. Notas que deixaram de estar
  pendentes (transmitidas ou excluídas) saem do estado.
- Cada tipo de erro de conexão é notificado uma vez só, até a conexão voltar.
- "Iniciar com o Windows" grava o valor `PreDANFE-Automatico` em
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- `refresh_autostart`: ao abrir o `.exe`, se o início com o Windows está ligado mas aponta para outro
  caminho (ex.: a antiga pasta `C:\PreDanfe`, antes do instalador), o valor é regravado com o caminho
  atual. Só regrava quando o caminho muda e só no `.exe`, para rodar do código-fonte não desviar o
  início com o Windows de uma instalação. O instalador não cria atalho de inicialização, porque o
  próprio programa já pergunta e o menu do ícone liga e desliga essa opção.
- O ícone da bandeja (`TrayIcon`, sobre o `pystray`): dois cliques abrem a pasta, e o botão direito
  abre o menu próprio. Antes de abrir o menu, o programa vem para o primeiro plano, porque sem isso o
  Windows não deixa o menu pegar o foco.
- O `pystray` roda em outra thread. Os pedidos dele (menu, pasta, configuração, sair) vão por uma fila
  que a thread do Tk lê a cada 50 ms.

## tray_menu.py — menu da bandeja

O menu padrão do Windows só mostra texto. Este é uma janela sem moldura no visual do programa:
ícone, título e uma linha de explicação por opção, mais uma chave liga/desliga em "Iniciar com o
Windows" (o clique na chave não fecha o menu).

- Abre com o canto de baixo à direita no mouse, sem passar da área livre do monitor (sem a barra de
  tarefas). Se a barra estiver em cima, abre para baixo.
- Fecha quando outra janela ganha o foco, quando há clique fora dele ou com Esc. Ele confere isso a
  cada 60 ms.
- Cantos arredondados no Windows 11 via DWM. No Windows 10, o pedido é ignorado.

## theme.py — visual

- Paleta Primer do GitHub (claro/escuro, conforme o tema do Windows), barra em degradê
  ciano → violeta, ícones de traço violeta, cartões com cantos de 12 px e botões em pílula, no estilo
  dos SVGs de `docs/referencia-visual`.
- O Canvas do Tk não suaviza bordas. Por isso as formas arredondadas e os ícones são desenhados com
  Pillow em resolução maior (4× ou 8×) e reduzidos.
- Os ícones seguem a grade 24×24 dos SVGs, com traço 2 e pontas redondas.
- **Ponto de status** do cabeçalho: um anel que cresce de 4 a 10 px e some em 2 s. A fase vem do
  relógio, então um atraso do Tk não deixa o pulso mais lento. Os quadros são pedidos a cada 8 ms
  porque o relógio do Windows anda de ~15,6 em ~15,6 ms: pedir 8 ms dá ~60 quadros/s, e pedir 16 daria
  ~30. A frase do status aparece numa dica ao passar o mouse.
- **Logo da PBtec**: no tema claro, `pbtec_logo_light.png` (já transparente). No escuro,
  `pbtec_logo.png` sem o fundo preto: a transparência vem do brilho de cada ponto, o vermelho do "PB"
  é mantido e o branco vira a cor do tema.
- **Barra de título escura** (Windows 10/11) via `DwmSetWindowAttribute`.
- **Ícone na barra de tarefas**: `set_taskbar_icon` manda o `.ico` direto para a janela
  (`WM_SETICON`, tamanhos grande e pequeno do DPI atual). Sem isso, a barra de tarefas fica com a
  pena do Tk, porque guarda o ícone que a janela tinha ao nascer.
- Imagens do Tk ficam em cache (`Theme.photo`), porque o Tk apaga imagens sem referência.

## app_utils.py — apoio às janelas

- `set_app_id`: identidade própria na barra de tarefas (`PBtec.<nome>`). Sem ela, o Windows agrupa a
  janela pelo programa que a abriu (python.exe ou o Tk dentro do .exe) e mostra o ícone dele.
- `apply_icon`: usa o `.ico` do executável em todas as janelas. O `.ico` tem todos os tamanhos prontos,
  e o Windows escolhe o certo em cada lugar. Rodando do código-fonte sem build, o `.ico` é gerado em
  `%LOCALAPPDATA%\PreDANFE`.
- `log_tk_errors`: erros dentro das janelas vão para o log, porque no `.exe` não há console.
- `single_instance`: mutex `Local\<nome>`, que fica aberto até o programa fechar.

## config_window.py e about_window.py

- A configuração é uma janela independente (com botão próprio na barra de tarefas), sem
  `transient`/`grab`. Se a janela principal for minimizada, a configuração não some junto, e a
  principal nunca fica presa esperando por ela. Só uma tela de configuração por vez.
- Os campos vêm do `config.ini`, completados com o que o SysPDV da máquina usa.
- "Sobre": dentro da janela principal no V1 (`Panel`) e em janela própria no V2 (`show`), porque o V2
  não tem janela principal.

## build.py, predanfe.spec e installer.iss — distribuição

O formato da distribuição foi escolhido para reduzir os falsos positivos de antivírus, já que os `.exe`
não têm assinatura digital:

- **Pasta (`onedir`) em vez de arquivo único (`onefile`).** O `onefile` extrai DLLs para a pasta
  temporária a cada abertura e roda de lá, o mesmo comportamento de muitos vírus. Com a pasta, nada é
  extraído e o programa abre mais rápido.
- **Inicializador do PyInstaller compilado na máquina do build** (veja o README). O inicializador
  pronto que vem do PyPI é o mesmo usado por vírus feitos em Python, e os antivírus já têm assinatura
  para ele.
- **Dados de versão no `.exe`** (empresa, produto, versão), vindos de `version.py`. Executável sem
  esses dados parece mais suspeito.
- **Sem UPX** (`upx=False`): executável compactado é outro motivo comum de alerta.

`predanfe.spec` descreve os dois programas e junta os dois numa única pasta `dist/PreDANFE/`, com uma
`_internal/` compartilhada (Python, bibliotecas, `fbclient/`, `resources/`). O `.spec` é necessário
porque a linha de comando do PyInstaller não sabe juntar dois `.exe` na mesma pasta. O mesmo `.ico`
vira o ícone dos `.exe` e vai em `resources/` para as janelas usarem.

`build.py` roda o `.spec`, copia para a pasta o `LEIA-ME.txt`, o manual (o de `dist/`, ou o da raiz do
repositório) e o `LICENSE` e o `NOTICE`, que a licença Apache 2.0 pede que acompanhem os executáveis.
Depois gera:

- `dist/PreDANFE-Portatil-<versão>.zip`: a pasta inteira, para usar sem instalar;
- `dist/PreDANFE-Instalador-<versão>.exe`: compilando `installer.iss` com o Inno Setup, se ele
  estiver instalado.

`installer.iss` (Inno Setup):

- Instala em `C:\Program Files\PreDANFE`, com atalhos no menu Iniciar e, se o usuário pedir, na Área
  de Trabalho.
- Como `APP_DIR` é a pasta do programa, o `config.ini` e a pasta `pdf` ficam dentro de
  `Program Files`, onde usuários comuns não gravam. O instalador libera a gravação **só** na pasta
  `pdf` e no `config.ini` (grupo Usuários, `S-1-5-32-545`). A pasta inteira não é liberada, porque aí
  qualquer usuário poderia trocar os `.exe` que outros usuários abrem.
- Para o `config.ini` poder ter essa permissão, ele precisa existir: se não existir, o instalador cria
  um só com `[saida] pasta_pdf = pdf`. Sem a seção `[banco]`, o programa age como se não houvesse
  configuração e abre a tela de configuração.
- Se existir `C:\PreDanfe\config.ini` (a pasta que as versões portáteis usavam), ele é copiado para a
  instalação, desde que ela ainda não tenha um `config.ini`.
- Desinstalar não apaga o `config.ini` nem os PDFs.
- `AppId` identifica o programa no Windows para atualizações e desinstalação. Não pode mudar.
- O arquivo é UTF-8 com BOM, para o Inno Setup ler os acentos.

## manual/

- `screenshots.py`: abre as janelas por alguns segundos com **dados fictícios** (nada é lido do banco),
  no tema claro e em escala 1,3× (com escala maior, a janela encosta na barra de tarefas em telas de
  1080 px; a configuração usa 1,2× para caber). Grava as capturas, o exemplo de pré-DANFE e
  `markers.json`, com as posições das marcações numeradas.
- `build_manual.py`: monta `dist/Manual-PreDANFE.pdf` com fpdf2. As marcações numeradas são
  desenhadas numa faixa livre dos dois lados da captura, para não cobrirem o texto (`l` = à esquerda
  do item, `r` = à direita, `c` = no ponto).
- `readme_cover.py`: gera `docs/capa-clara.png` e `docs/capa-escura.png`.
