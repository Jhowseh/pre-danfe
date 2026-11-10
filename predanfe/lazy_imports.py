import importlib
import sys
import types

DEFERRED = {
    "unittest.mock": ("patch",),
    "firebird.base.config_pb2": ("ConfigProto",),
}


def _defer(name, attributes):
    if name in sys.modules:
        return
    stub = types.ModuleType(name)

    def real_module():
        if sys.modules.get(name) is stub:
            del sys.modules[name]
        return importlib.import_module(name)

    def get_attribute(attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return getattr(real_module(), attr)

    for attr in attributes:
        setattr(stub, attr, lambda *a, _attr=attr, **k: getattr(real_module(), _attr)(*a, **k))
    stub.__getattr__ = get_attribute
    sys.modules[name] = stub


for _name, _attributes in DEFERRED.items():
    _defer(_name, _attributes)
