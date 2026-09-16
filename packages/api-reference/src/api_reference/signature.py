"""Render griffe objects as the Python signature text shown in a fence."""

from collections.abc import Iterable

import griffe

MAX_LINE = 88


def render(obj: griffe.Object, name: str) -> str:
    """The signature under the given display name; empty for a module."""
    match obj:
        case griffe.Function():
            return function_signature(obj, name)
        case griffe.Class():
            return class_signature(obj, name)
        case griffe.TypeAlias():
            return f"type {name}{type_params(obj.type_parameters)} = {obj.value}"
        case griffe.Attribute():
            return attribute_signature(obj, name)
        case _:
            return ""


def function_signature(fn: griffe.Function, name: str) -> str:
    """Each overload with its decorator; a plain function as one ``def``."""

    def one(fn: griffe.Function) -> str:
        head = f"def {name}{type_params(fn.type_parameters)}("
        tail = ")" if fn.returns is None else f") -> {fn.returns}"
        params = parameters(fn)
        flat = head + ", ".join(params) + tail
        if len(flat) <= MAX_LINE:
            return flat
        return head + "\n" + "".join(f"    {p},\n" for p in params) + tail

    if fn.overloads:
        return "\n\n".join(f"@overload\n{one(overload)}" for overload in fn.overloads)
    return one(fn)


def parameters(fn: griffe.Function) -> list[str]:
    """Parameter texts plus the ``/`` and ``*`` markers.

    A bare ``self`` or ``cls`` is dropped; an annotated ``self`` stays because
    the annotation is where a binder's fresh type variables are introduced.
    """
    params = list(fn.parameters)
    if params and params[0].name in ("self", "cls") and params[0].annotation is None:
        params = params[1:]
    kinds = [
        p.kind.value if p.kind is not None else "positional or keyword" for p in params
    ]
    has_var_positional = "variadic positional" in kinds
    out: list[str] = []
    for index, (param, kind) in enumerate(zip(params, kinds, strict=True)):
        if kind == "keyword-only" and not has_var_positional and "*" not in out:
            out.append("*")
        star = {"variadic positional": "*", "variadic keyword": "**"}.get(kind, "")
        text = f"{star}{param.name}"
        if param.annotation is not None:
            text += f": {param.annotation}"
        if param.default is not None and not star:
            text += f" = {param.default}" if param.annotation else f"={param.default}"
        out.append(text)
        next_kind = kinds[index + 1] if index + 1 < len(kinds) else None
        if kind == "positional-only" and next_kind != "positional-only":
            out.append("/")
    return out


def class_signature(cls: griffe.Class, name: str) -> str:
    """Decorators, the class line, then its public fields (or ``...``)."""
    lines = [f"@{decorator.value}" for decorator in cls.decorators]
    bases = ", ".join(str(base) for base in cls.bases)
    head = f"class {name}{type_params(cls.type_parameters)}"
    lines.append(f"{head}({bases}):" if bases else f"{head}:")
    fields = [
        member
        for member in cls.members.values()
        if isinstance(member, griffe.Attribute)
        and not member.name.startswith("_")
        and "property" not in member.labels
    ]
    for field in fields:
        lines.append(f"    {attribute_signature(field, field.name)}")
    if not fields:
        lines.append("    ...")
    return "\n".join(lines)


def attribute_signature(attr: griffe.Attribute, name: str) -> str:
    """``name: Type``; an unannotated instance is typed by what it calls."""
    text = name if attr.annotation is None else f"{name}: {attr.annotation}"
    if attr.annotation is None and isinstance(attr.value, griffe.ExprCall):
        return f"{name}: {attr.value.function}"
    if attr.value is not None and "property" not in attr.labels:
        text += f" = {attr.value}"
    return text


def type_params(params: Iterable[griffe.TypeParameter]) -> str:
    """PEP 695 brackets: ``[A, E: Bound = Default, **P]``, or nothing."""
    parts: list[str] = []
    for param in params:
        prefix = {"param-spec": "**", "type-var-tuple": "*"}.get(param.kind.value, "")
        text = f"{prefix}{param.name}"
        if param.bound is not None:
            text += f": {param.bound}"
        if param.default is not None:
            text += f" = {param.default}"
        parts.append(text)
    return f"[{', '.join(parts)}]" if parts else ""
