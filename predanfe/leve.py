"""Evita carregar módulos pesados que as bibliotecas importam mas o programa não usa.

Importar este módulo antes do firebird-driver e do fpdf economiza ~8 MB de memória,
sem mudar nada no funcionamento:

- `unittest.mock`: o fpdf o importa só para assinar PDFs digitalmente (não usamos).
  Ele carrega o asyncio inteiro.
- `firebird.base.config_pb2`: o firebird-driver o importa só para gravar/ler a
  configuração em formato protobuf (não usamos). Ele carrega o protobuf do Google.

No lugar de cada um entra um módulo "de mentira". Se alguém usar de fato alguma coisa
dele, o módulo verdadeiro é carregado na hora e a chamada segue normalmente.
"""
import importlib
import sys
import types

ADIADOS = {
    "unittest.mock": ("patch",),
    "firebird.base.config_pb2": ("ConfigProto",),
}


def _adiar(nome, atributos):
    if nome in sys.modules:
        return
    falso = types.ModuleType(nome)

    def verdadeiro():
        if sys.modules.get(nome) is falso:
            del sys.modules[nome]
        return importlib.import_module(nome)

    def atributo(attr):
        if attr.startswith("__"):  # perguntas do próprio import (__path__ etc.) não carregam nada
            raise AttributeError(attr)
        return getattr(verdadeiro(), attr)

    for attr in atributos:  # os nomes que as bibliotecas importam com "from ... import"
        setattr(falso, attr, lambda *a, _attr=attr, **k: getattr(verdadeiro(), _attr)(*a, **k))
    falso.__getattr__ = atributo
    sys.modules[nome] = falso


for _nome, _atributos in ADIADOS.items():
    _adiar(_nome, _atributos)
