"""ImportYeti integration package."""

from importlib import import_module
from typing import Any

__all__ = [
    "bol_search_service",
    "chinese_name_resolver",
    "internal_bol_client",
    "subscription",
]

_MODULE_ALIASES = {
    "bol_search_service": "importyeti.buyers.service",
    "chinese_name_resolver": "importyeti.clients.chinese_name_resolver",
    "internal_bol_client": "importyeti.clients.internal_bol_client",
    "subscription": "importyeti.contracts.subscription",
}


def __getattr__(name: str) -> Any:
    module_path = _MODULE_ALIASES.get(name)
    if module_path is None:
        raise AttributeError(f"module 'importyeti' has no attribute {name!r}")
    module = import_module(module_path)
    globals()[name] = module
    return module
