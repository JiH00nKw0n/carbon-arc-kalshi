"""One generic component registry: named sub-tables + typed register_* decorators.

Every swappable axis (channel / y_target / prompt / arm / baseline / llm) self-registers
into `Registry._subs[kind]`. Lookups fail fast with the valid set; never return None.
"""
from __future__ import annotations

from typing import Callable

from prediction.errors import ModelConfigError


class Registry:
    """A class-level dict of named sub-registries: kind -> {name: object}."""

    _subs: dict[str, dict[str, object]] = {}

    @classmethod
    def sub(cls, kind: str) -> Callable:
        """Return a decorator that registers name -> object into sub-table `kind`.

        Two equivalent call forms, both returning the registered object:
          register(name)(obj)  registers `obj` under the explicit `name` (functions).
          register(obj)        registers `obj` under `obj.name` (named specs).
        """
        table = cls._subs.setdefault(kind, {})

        def register(target):
            if isinstance(target, str):
                return lambda obj: cls._put(table, target, obj, kind)
            return cls._put(table, target.name, target, kind)

        return register

    @classmethod
    def _put(cls, table: dict, name: str, obj: object, kind: str) -> object:
        if name in table:
            raise ModelConfigError(f"duplicate {kind} '{name}' already registered")
        table[name] = obj
        return obj

    @classmethod
    def get(cls, kind: str, name: str) -> object:
        table = cls._subs.get(kind, {})
        if name not in table:
            valid = ", ".join(sorted(table)) or "<none registered>"
            raise ModelConfigError(f"unknown {kind} '{name}'; valid: {valid}")
        return table[name]

    @classmethod
    def names(cls, kind: str) -> list[str]:
        return sorted(cls._subs.get(kind, {}))


register_channel = Registry.sub("channel")
register_y_target = Registry.sub("y_target")
register_prompt = Registry.sub("prompt")
register_variant = Registry.sub("variant")
register_arm = Registry.sub("arm")
register_baseline = Registry.sub("baseline")
register_llm = Registry.sub("llm")


def get(kind: str, name: str) -> object:
    """Module-level convenience for `Registry.get`."""
    return Registry.get(kind, name)
