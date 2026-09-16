"""Walk the package with griffe into an ordered, curated Reference."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import final

import griffe

import effecton as E
from api_reference.topics import Topic

NAMESPACE = "E"


@final
@dataclass(frozen=True)
class UnmappedModule(E.EffectonError):
    name: str
    module: str

    def __str__(self) -> str:
        return (
            f"{self.name} lives in {self.module}, which no topic lists; "
            "add the module to api_reference.topics.TOPICS"
        )


@final
@dataclass(frozen=True)
class UnresolvedExport(E.EffectonError):
    name: str
    reason: str

    def __str__(self) -> str:
        return f"Cannot resolve the export {self.name}: {self.reason}"


@final
@dataclass(frozen=True)
class MissingExtra(E.EffectonError):
    path: str

    def __str__(self) -> str:
        return f"The extra {self.path} listed in TOPICS does not exist"


type CollectError = UnmappedModule | UnresolvedExport | MissingExtra


@dataclass(frozen=True)
class Member:
    """A method or property rendered under its class as a ``####`` block."""

    display: str
    obj: griffe.Object


@dataclass(frozen=True)
class Symbol:
    """A ``###`` entry: the displayed name, the griffe object, its members."""

    display: str
    obj: griffe.Object
    members: tuple[Member, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class Section:
    title: str
    symbols: tuple[Symbol, ...]


@dataclass(frozen=True)
class Reference:
    sections: tuple[Section, ...]


def load(package: str = "effecton") -> griffe.Module:
    """Read the package statically from the environment's search path."""
    loaded = griffe.load(package, allow_inspection=False)
    if not isinstance(loaded, griffe.Module):
        raise TypeError(f"{package} did not load as a module: {loaded!r}")
    return loaded


def collect(
    root: griffe.Module, topics: Sequence[Topic]
) -> E.Effect[Reference, CollectError]:
    """Bucket every ``__all__`` name and service member into the topics.

    Fails when an export lives in a module no topic lists, so a new module
    must be placed in TOPICS before the docs build passes.
    """

    def build() -> E.Effect[Reference, CollectError]:
        buckets: dict[str, list[Symbol]] = {
            module: [] for topic in topics for module in topic.modules
        }
        seen: set[str] = set()

        def add(module: str, symbol: Symbol) -> None:
            if symbol.obj.path in seen:
                return
            seen.add(symbol.obj.path)
            buckets[module].append(symbol)

        for name in exported_names(root):
            resolved = resolve_export(root, name)
            if isinstance(resolved, UnresolvedExport):
                return E.fail(resolved)
            module = module_key(root, resolved)
            if module not in buckets:
                return E.fail(UnmappedModule(name=f"{NAMESPACE}.{name}", module=module))
            display = f"{NAMESPACE}.{name}"
            if isinstance(resolved, griffe.Module):
                add(module, Symbol(display, resolved))
                for member in service_members(resolved):
                    symbol = Symbol(
                        f"{display}.{member.name}",
                        member,
                        class_members(member, f"{display}.{member.name}"),
                    )
                    add(module, symbol)
            else:
                add(module, Symbol(display, resolved, class_members(resolved, display)))

        sections: list[Section] = []
        for topic in topics:
            symbols: list[Symbol] = []
            for module in topic.modules:
                symbols.extend(sorted(buckets[module], key=source_order))
            for path in topic.extras:
                extra = lookup(root, path)
                if extra is None:
                    return E.fail(MissingExtra(path=path))
                name = path.rsplit(".", 1)[-1]
                note = (
                    f"Not exported as `{NAMESPACE}.{name}`; reached through "
                    "the return types above."
                )
                symbols.append(Symbol(name, extra, class_members(extra, name), note))
            sections.append(Section(topic.title, tuple(symbols)))
        return E.success(Reference(tuple(sections)))

    return E.suspend(build)


def exported_names(root: griffe.Module) -> list[str]:
    """The package's ``__all__`` entries, in declaration order."""
    declared = root.members.get("__all__")
    if not isinstance(declared, griffe.Attribute) or not isinstance(
        declared.value, griffe.ExprList
    ):
        raise TypeError(f"{root.path} has no __all__ list literal: {declared!r}")
    return [str(element).strip("'\"") for element in declared.value.elements]


def resolve_export(root: griffe.Module, name: str) -> griffe.Object | UnresolvedExport:
    """Follow an ``__all__`` name to the object it re-exports.

    A submodule of the same name shadows a re-exported function (``suspend``,
    ``gen``, ``attempt``, ``run_sync`` ...), so descend into it first.
    """
    member = root.members[name]
    if isinstance(member, griffe.Module) and name in member.members:
        member = member.members[name]
    if not isinstance(member, griffe.Alias):
        return member
    try:
        return member.final_target
    except (griffe.AliasResolutionError, griffe.CyclicAliasError) as error:
        return UnresolvedExport(name=name, reason=str(error))


def module_key(root: griffe.Module, obj: griffe.Object) -> str:
    """The object's module path relative to the root package (``std.clock``)."""
    path = obj.path if isinstance(obj, griffe.Module) else obj.module.path
    return path.removeprefix(f"{root.path}.")


def service_members(module: griffe.Module) -> list[griffe.Object]:
    """A service module's own public definitions, in source order."""
    return [
        member
        for member in module.members.values()
        if not member.name.startswith("_")
        and not isinstance(member, griffe.Alias)
        and isinstance(
            member, griffe.Class | griffe.Function | griffe.TypeAlias | griffe.Attribute
        )
    ]


def class_members(obj: griffe.Object, display: str) -> tuple[Member, ...]:
    """Public methods and properties of a class; nothing for other kinds.

    A service implementation (a class deriving from its module's Protocol)
    lists only what the Protocol does not declare, so protocol methods are
    documented once.
    """
    if not isinstance(obj, griffe.Class):
        return ()
    declared = protocol_members(obj)
    members: list[Member] = []
    for name, member in obj.members.items():
        if name.startswith("_") and name != "__call__":
            continue
        if name in declared or isinstance(member, griffe.Alias):
            continue
        is_property = (
            isinstance(member, griffe.Attribute) and "property" in member.labels
        )
        if isinstance(member, griffe.Function) or is_property:
            members.append(Member(f"{display}.{name}", member))
    return tuple(members)


def protocol_members(cls: griffe.Class) -> frozenset[str]:
    """Names declared on the module's Protocol when ``cls`` implements it."""
    if cls.name == "Protocol" or not any(str(base) == "Protocol" for base in cls.bases):
        return frozenset()
    protocol = cls.module.members.get("Protocol")
    if not isinstance(protocol, griffe.Class):
        return frozenset()
    return frozenset(protocol.members)


def lookup(root: griffe.Module, path: str) -> griffe.Object | None:
    try:
        found = root[path]
    except KeyError:
        return None
    return found.final_target if isinstance(found, griffe.Alias) else found


def source_order(symbol: Symbol) -> tuple[int, int]:
    """Modules first, then definitions by line."""
    is_module = 0 if isinstance(symbol.obj, griffe.Module) else 1
    return (is_module, symbol.obj.lineno or 0)
