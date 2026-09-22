"""Schema: describe a shape once, then decode and encode through it.

A Schema[A, I] pairs two pure functions: decode turns untrusted input into
a typed A, encode turns an A back into its wire form I. Combinators build
bigger pairs from smaller ones, so every schema works in both directions.
decode and encode return effects that fail with one ParseError listing
every issue found, each tagged with the path where it occurred.
"""

import dataclasses
import json
import re
import typing
from collections.abc import Callable, Iterable, Mapping
from dataclasses import MISSING, dataclass
from datetime import date, datetime
from types import NoneType, UnionType
from typing import Any, ClassVar, Generic, TypeVar, dataclass_transform, final, overload

from effecton.effect import Effect, EffectonError, fail, success, sync
from effecton.std.path import Path

type IssuePath = tuple[str | int, ...]


@final
@dataclass(frozen=True)
class TypeMismatch:
    path: IssuePath
    expected: str
    actual: object

    def __str__(self) -> str:
        return _at(self.path, f"expected {self.expected}, got {self.actual!r}")


@final
@dataclass(frozen=True)
class MissingKey:
    path: IssuePath

    def __str__(self) -> str:
        return _at(self.path, "is missing")


@final
@dataclass(frozen=True)
class RefinementFailed:
    path: IssuePath
    message: str
    actual: object

    def __str__(self) -> str:
        return _at(self.path, f"{self.message}, got {self.actual!r}")


@final
@dataclass(frozen=True)
class TransformFailed:
    path: IssuePath
    message: str
    actual: object

    def __str__(self) -> str:
        return _at(self.path, f"{self.message}, got {self.actual!r}")


@final
@dataclass(frozen=True)
class NoUnionMember:
    """No member matched; issues holds what every member reported."""

    path: IssuePath
    actual: object
    issues: tuple[Issue, ...]

    def __str__(self) -> str:
        head = _at(self.path, f"no union member matched {self.actual!r}")
        nested = [
            f"  {line}" for issue in self.issues for line in str(issue).split("\n")
        ]
        return "\n".join([head, *nested])


@final
@dataclass(frozen=True)
class InvalidJson:
    path: IssuePath
    reason: str

    def __str__(self) -> str:
        return _at(self.path, f"invalid JSON: {self.reason}")


type Issue = (
    TypeMismatch
    | MissingKey
    | RefinementFailed
    | TransformFailed
    | NoUnionMember
    | InvalidJson
)


@final
@dataclass(frozen=True)
class ParseError(EffectonError):
    issues: tuple[Issue, ...]

    def __str__(self) -> str:
        return "\n".join(str(issue) for issue in self.issues)


@dataclass(frozen=True)
class _Issues:
    issues: tuple[Issue, ...]


@final
class Schema[A, I]:
    """A two-way codec: A is the decoded type, I the encoded one."""

    def __init__(
        self,
        decode: Callable[[object, IssuePath], A | _Issues],
        encode: Callable[[A, IssuePath], I | _Issues],
    ) -> None:
        self._decode = decode
        self._encode = encode

    def check(self, *checks: Check[A]) -> Schema[A, I]:
        """Guard decode and encode alike: every check must hold in both directions.

        Encode runs the inner schema first, so a value of a foreign type is
        a TypeMismatch rather than a crash inside a predicate.
        """

        def apply_checks(value: Any, path: IssuePath) -> Any:
            """Every check against value: None if all pass, else their issues."""
            failures = tuple(
                RefinementFailed(path, c._message, value)
                for c in checks
                if not c._predicate(value)
            )
            return _Issues(failures) if failures else None

        def decode_checked(raw: object, path: IssuePath) -> Any:
            result: Any = self._decode(raw, path)
            if isinstance(result, _Issues):
                return result
            failed = apply_checks(result, path)
            return result if failed is None else failed

        def encode_checked(value: A, path: IssuePath) -> Any:
            result: Any = self._encode(value, path)
            if isinstance(result, _Issues):
                return result
            failed = apply_checks(value, path)
            return result if failed is None else failed

        return Schema(decode_checked, encode_checked)


# _T_contra is an old-style TypeVar, not a PEP 695 `[T]` parameter, because ty
# only infers declared variance from old-style TypeVars: Check must be
# contravariant so that Check[Sized] fits a Schema[str, ...] and Check[float]
# fits a Schema[int, ...] (see the CLAUDE.md notes on Effect's variance).
_T_contra = TypeVar("_T_contra", contravariant=True)


@final
class Check(Generic[_T_contra]):  # noqa: UP046
    """A refinement: a predicate over the decoded value and its failure message."""

    def __init__(self, predicate: Callable[[_T_contra], bool], message: str) -> None:
        self._predicate = predicate
        self._message = message


# How a combinator walks its members: _decode or _encode, chosen once.
type _Direction = Callable[[Schema[Any, Any]], Callable[[Any, IssuePath], Any]]


@overload
def decode[T: Struct](schema: type[T]) -> Callable[[object], Effect[T, ParseError]]: ...


@overload
def decode[A, I](schema: Schema[A, I]) -> Callable[[object], Effect[A, ParseError]]: ...


def decode(schema: Any) -> Any:
    """decode(schema)(raw): turn untrusted input into a typed value."""
    resolved = _resolve(schema)

    def run(raw: object) -> Effect[Any, ParseError]:
        return sync(lambda: resolved._decode(raw, ())).flat_map(_settle)

    return run


@overload
def encode[T: Struct](
    schema: type[T],
) -> Callable[[T], Effect[dict[str, object], ParseError]]: ...


@overload
def encode[A, I](schema: Schema[A, I]) -> Callable[[A], Effect[I, ParseError]]: ...


def encode(schema: Any) -> Any:
    """encode(schema)(value): turn a typed value back into its wire form."""
    resolved = _resolve(schema)

    def run(value: Any) -> Effect[Any, ParseError]:
        return sync(lambda: resolved._encode(value, ())).flat_map(_settle)

    return run


@overload
def decode_json[T: Struct](
    schema: type[T],
) -> Callable[[str], Effect[T, ParseError]]: ...


@overload
def decode_json[A, I](
    schema: Schema[A, I],
) -> Callable[[str], Effect[A, ParseError]]: ...


def decode_json(schema: Any) -> Any:
    """decode_json(schema)(text): parse JSON text, then decode it."""
    resolved = _resolve(schema)

    def run(text: str) -> Effect[Any, ParseError]:
        def parse_then_decode() -> Any:
            if not isinstance(text, str):
                return _Issues((TypeMismatch((), "JSON text", text),))
            try:
                raw = json.loads(text)
            except RecursionError:
                # Its message counts kilobytes of stack, so say it plainly.
                return _Issues((InvalidJson((), "nesting is too deep"),))
            except ValueError as e:  # JSONDecodeError, and int's digit limit.
                return _Issues((InvalidJson((), str(e)),))
            return resolved._decode(raw, ())

        return sync(parse_then_decode).flat_map(_settle)

    return run


@overload
def encode_json[T: Struct](
    schema: type[T],
) -> Callable[[T], Effect[str, ParseError]]: ...


@overload
def encode_json[A, I](
    schema: Schema[A, I],
) -> Callable[[A], Effect[str, ParseError]]: ...


def encode_json(schema: Any) -> Any:
    """encode_json(schema)(value): encode, then serialize as JSON text.

    An encoded form json cannot serialize is a defect: pick schemas whose
    wire side is JSON (every built-in is).
    """
    resolved = _resolve(schema)

    def run(value: Any) -> Effect[Any, ParseError]:
        def encode_then_dump() -> Any:
            encoded = resolved._encode(value, ())
            return encoded if isinstance(encoded, _Issues) else json.dumps(encoded)

        return sync(encode_then_dump).flat_map(_settle)

    return run


@overload
def field[T](schema: Schema[T, Any], *, key: str | None = None) -> T: ...


@overload
def field[T](schema: Schema[T, Any], *, key: str | None = None, default: T) -> T: ...


@overload
def field(*, key: str | None = None) -> Any: ...


@overload
def field[T](*, key: str | None = None, default: T) -> T: ...


def field(
    schema: Any = None,
    *,
    key: str | None = None,
    default: Any = MISSING,
) -> Any:
    """Configure a Struct field: its schema, its wire key, its default.

    A field with a default may be absent from the input; the default is
    checked against the schema once, when the class is defined. Without a
    schema, one is inferred from the annotation.
    """
    return dataclasses.field(
        default=default, metadata={_FIELD: _FieldSpec(schema=schema, key=key)}
    )


@dataclass_transform(
    frozen_default=True, kw_only_default=True, field_specifiers=(field,)
)
class Struct:
    """Subclass to declare a record: annotations are the decoded types.

    Every subclass becomes a frozen, keyword-only dataclass and is itself
    accepted wherever a schema is: decode(User)(raw).
    """

    __schema__: ClassVar[Schema[Any, dict[str, object]]]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        dataclass(frozen=True, kw_only=True)(cls)
        cls.__schema__ = _struct_schema(cls)


def struct_schema[T: Struct](cls: type[T]) -> Schema[T, dict[str, object]]:
    """The schema behind a Struct class, for combinators that need one."""
    return cls.__schema__


def Literal[T: str | int | bool | None](*values: T) -> Schema[T, T]:
    """One of the given values; True is not 1."""
    expected = " | ".join(repr(v) for v in values)

    def check(raw: Any, path: IssuePath) -> Any:
        if any(raw == v and type(raw) is type(v) for v in values):
            return raw
        return _Issues((TypeMismatch(path, expected, raw),))

    return Schema(check, check)


def instance_of[T](cls: type[T]) -> Schema[T, T]:
    """Any instance of cls, unchanged in both directions.

    The guard for a transform's decoded side: pass it as `to=` so encode
    rejects a foreign value instead of handing it to your function.
    """

    def check(raw: Any, path: IssuePath) -> Any:
        if isinstance(raw, cls):
            return raw
        return _Issues((TypeMismatch(path, cls.__name__, raw),))

    return Schema(check, check)


@overload
def Array[T: Struct](
    item: type[T],
) -> Schema[tuple[T, ...], list[dict[str, object]]]: ...


@overload
def Array[A, I](item: Schema[A, I]) -> Schema[tuple[A, ...], list[I]]: ...


def Array(item: Any) -> Any:
    """A list or tuple on the wire, a tuple once decoded."""
    inner = _resolve(item)

    def decode_array(raw: object, path: IssuePath) -> Any:
        if not isinstance(raw, list | tuple):
            return _Issues((TypeMismatch(path, "array", raw),))
        return _collect(
            tuple, (inner._decode(x, (*path, i)) for i, x in enumerate(raw))
        )

    def encode_array(value: Any, path: IssuePath) -> Any:
        if not isinstance(value, tuple):
            return _Issues((TypeMismatch(path, "tuple", value),))
        return _collect(
            list, (inner._encode(x, (*path, i)) for i, x in enumerate(value))
        )

    return Schema(decode_array, encode_array)


def Record[KA, KI, VA, VI](
    key: Schema[KA, KI], value: Schema[VA, VI]
) -> Schema[dict[KA, VA], dict[KI, VI]]:
    """A mapping whose keys and values each go through their schema."""

    def walk(direction: _Direction) -> Callable[[Any, IssuePath], Any]:
        def run(raw: Any, path: IssuePath) -> Any:
            if not isinstance(raw, Mapping):
                return _Issues((TypeMismatch(path, "object", raw),))
            entries = []
            for k, v in raw.items():
                at = (*path, k if isinstance(k, str | int) else repr(k))
                entries.append(direction(key)(k, at))
                entries.append(direction(value)(v, at))
            return _collect(
                lambda flat: dict(zip(flat[::2], flat[1::2], strict=True)), entries
            )

        return run

    return Schema(walk(lambda s: s._decode), walk(lambda s: s._encode))


@overload
def Tuple[A1, I1](m1: Schema[A1, I1], /) -> Schema[tuple[A1], list[I1]]: ...


@overload
def Tuple[A1, I1, A2, I2](
    m1: Schema[A1, I1], m2: Schema[A2, I2], /
) -> Schema[tuple[A1, A2], list[I1 | I2]]: ...


@overload
def Tuple[A1, I1, A2, I2, A3, I3](
    m1: Schema[A1, I1], m2: Schema[A2, I2], m3: Schema[A3, I3], /
) -> Schema[tuple[A1, A2, A3], list[I1 | I2 | I3]]: ...


@overload
def Tuple[A1, I1, A2, I2, A3, I3, A4, I4](
    m1: Schema[A1, I1], m2: Schema[A2, I2], m3: Schema[A3, I3], m4: Schema[A4, I4], /
) -> Schema[tuple[A1, A2, A3, A4], list[I1 | I2 | I3 | I4]]: ...


@overload
def Tuple(*members: Schema[Any, Any]) -> Schema[tuple[Any, ...], list[Any]]: ...


def Tuple(*members: Schema[Any, Any]) -> Any:
    """A fixed-length array with one schema per position."""
    expected = f"array of {len(members)} items"

    def decode_tuple(raw: object, path: IssuePath) -> Any:
        if not isinstance(raw, list | tuple) or len(raw) != len(members):
            return _Issues((TypeMismatch(path, expected, raw),))
        return _collect(
            tuple,
            (
                m._decode(x, (*path, i))
                for i, (m, x) in enumerate(zip(members, raw, strict=True))
            ),
        )

    def encode_tuple(value: Any, path: IssuePath) -> Any:
        if not isinstance(value, tuple) or len(value) != len(members):
            return _Issues(
                (TypeMismatch(path, f"tuple of {len(members)} items", value),)
            )
        return _collect(
            list,
            (
                m._encode(x, (*path, i))
                for i, (m, x) in enumerate(zip(members, value, strict=True))
            ),
        )

    return Schema(decode_tuple, encode_tuple)


@overload
def Union[A1, I1, A2, I2](
    m1: Schema[A1, I1], m2: Schema[A2, I2], /
) -> Schema[A1 | A2, I1 | I2]: ...


@overload
def Union[A1, I1, A2, I2, A3, I3](
    m1: Schema[A1, I1], m2: Schema[A2, I2], m3: Schema[A3, I3], /
) -> Schema[A1 | A2 | A3, I1 | I2 | I3]: ...


@overload
def Union[A1, I1, A2, I2, A3, I3, A4, I4](
    m1: Schema[A1, I1], m2: Schema[A2, I2], m3: Schema[A3, I3], m4: Schema[A4, I4], /
) -> Schema[A1 | A2 | A3 | A4, I1 | I2 | I3 | I4]: ...


@overload
def Union(*members: Schema[Any, Any]) -> Schema[Any, Any]: ...


def Union(*members: Schema[Any, Any]) -> Any:
    """The first member that succeeds wins, decoding and encoding alike."""

    def walk(direction: _Direction) -> Callable[[Any, IssuePath], Any]:
        def run(raw: Any, path: IssuePath) -> Any:
            collected: list[Issue] = []
            for member in members:
                result = direction(member)(raw, path)
                if not isinstance(result, _Issues):
                    return result
                collected.extend(result.issues)
            return _Issues((NoUnionMember(path, raw, tuple(collected)),))

        return run

    return Schema(walk(lambda s: s._decode), walk(lambda s: s._encode))


@overload
def NullOr[T: Struct](
    schema: type[T],
) -> Schema[T | None, dict[str, object] | None]: ...


@overload
def NullOr[A, I](schema: Schema[A, I]) -> Schema[A | None, I | None]: ...


def NullOr(schema: Any) -> Any:
    """The schema or null, in both directions."""
    return Union(_resolve(schema), Null)


@final
@dataclass(frozen=True)
class Invalid:
    """What a transform_or_fail function returns to reject its input."""

    message: str


def transform[A, I, B](
    from_: Schema[A, I],
    *,
    decode: Callable[[A], B],
    encode: Callable[[B], A],
    to: Schema[B, B] | None = None,
) -> Schema[B, I]:
    """Map a schema's decoded side through a total function pair.

    Without `to`, encode hands the value straight to the function, so inside
    a Union or NullOr the function can receive values meant for another
    member; pass `to` to guard it, typically `S.instance_of(cls)`.
    """
    return transform_or_fail(from_, decode=decode, encode=encode, to=to)


def transform_or_fail[A, I, B](
    from_: Schema[A, I],
    *,
    decode: Callable[[A], B | Invalid],
    encode: Callable[[B], A | Invalid],
    to: Schema[B, B] | None = None,
) -> Schema[B, I]:
    """Like transform, but either function may return Invalid(message).

    An exception raised by either function is a defect, not a ParseError.
    `to` guards the decoded side in both directions, as in transform.
    """

    def decode_through(raw: object, path: IssuePath) -> Any:
        inner: Any = from_._decode(raw, path)
        if isinstance(inner, _Issues):
            return inner
        outer = decode(inner)
        if isinstance(outer, Invalid):
            return _Issues((TransformFailed(path, outer.message, inner),))
        return outer if to is None else to._decode(outer, path)

    def encode_through(value: Any, path: IssuePath) -> Any:
        if to is not None:
            guarded: Any = to._encode(value, path)
            if isinstance(guarded, _Issues):
                return guarded
            value = guarded
        inner = encode(value)
        if isinstance(inner, Invalid):
            return _Issues((TransformFailed(path, inner.message, value),))
        return from_._encode(inner, path)

    return Schema(decode_through, encode_through)


def filter[A](predicate: Callable[[A], bool], *, message: str) -> Check[A]:
    """A refinement for Schema.check(): a bare predicate plus its failure message."""
    return Check(predicate, message)


def pattern(regex: str) -> Check[str]:
    """A string the regular expression finds a match in."""
    compiled = re.compile(regex)
    return filter(
        lambda v: compiled.search(v) is not None,
        message=f"expected a string matching {regex}",
    )


def _primitive[T](expected: str, accepts: Callable[[object], bool]) -> Schema[T, T]:
    # Defined before its callers: the primitives below are built at import time.
    def check(raw: Any, path: IssuePath) -> Any:
        if accepts(raw):
            return raw
        return _Issues((TypeMismatch(path, expected, raw),))

    return Schema(check, check)


String: Schema[str, str] = _primitive("string", lambda x: isinstance(x, str))
Int: Schema[int, int] = _primitive(
    "integer", lambda x: isinstance(x, int) and not isinstance(x, bool)
)
Float: Schema[float, float] = _primitive(
    "number", lambda x: isinstance(x, int | float) and not isinstance(x, bool)
)
Bool: Schema[bool, bool] = _primitive("boolean", lambda x: isinstance(x, bool))
Null: Schema[None, None] = _primitive("null", lambda x: x is None)
Unknown: Schema[object, object] = _primitive("anything", lambda _: True)


def _parser[T](parse: Callable[[str], T], message: str) -> Callable[[str], T | Invalid]:
    def run(text: str) -> T | Invalid:
        try:
            return parse(text)
        except ValueError:
            return Invalid(message)

    return run


IntFromString: Schema[int, str] = transform_or_fail(
    String, decode=_parser(int, "expected an integer string"), encode=str, to=Int
)
FloatFromString: Schema[float, str] = transform_or_fail(
    String, decode=_parser(float, "expected a number string"), encode=str, to=Float
)
DateTimeFromString: Schema[datetime, str] = transform_or_fail(
    String,
    decode=_parser(datetime.fromisoformat, "expected an ISO 8601 datetime"),
    encode=datetime.isoformat,
    to=instance_of(datetime),
)
# A datetime is a date, and encoding one would silently drop its time.
DateFromString: Schema[date, str] = transform_or_fail(
    String,
    decode=_parser(date.fromisoformat, "expected an ISO 8601 date"),
    encode=date.isoformat,
    to=instance_of(date).check(
        filter(
            lambda d: not isinstance(d, datetime),
            message="expected a date without a time",
        )
    ),
)
PathFromString: Schema[Path, str] = transform(
    String, decode=Path, encode=str, to=instance_of(Path)
)


def _resolve(schema: Any) -> Schema[Any, Any]:
    if isinstance(schema, Schema):
        return schema
    if isinstance(schema, type) and issubclass(schema, Struct) and schema is not Struct:
        return schema.__schema__
    raise TypeError(f"expected a Schema or a Struct class, got {schema!r}")


_FIELD = "effecton.schema"


@dataclass(frozen=True)
class _FieldSpec:
    schema: Schema[Any, Any] | None
    key: str | None


type _FieldResolver = Callable[
    [dataclasses.Field[Any], Any, str], tuple[str, Schema[Any, Any]]
]


def _struct_schema(
    cls: type[Any], resolve: _FieldResolver | None = None
) -> Schema[Any, dict[str, object]]:
    """Build a struct codec; resolve gives each field its wire key and schema.

    Struct resolves through S.field metadata and JSON inference; Cli.Args
    passes a resolver keyed by option names with text codecs.
    """
    resolve_field = _struct_field if resolve is None else resolve
    hints = typing.get_type_hints(cls, include_extras=True)
    plan: list[tuple[str, str, Schema[Any, Any], Any]] = []
    owner_of: dict[str, str] = {}
    for f in dataclasses.fields(cls):
        key, schema = resolve_field(f, hints[f.name], f"{cls.__name__}.{f.name}")
        if key in owner_of:
            raise TypeError(
                f"{cls.__name__}: fields {owner_of[key]!r} and {f.name!r} "
                f"share the wire key {key!r}"
            )
        owner_of[key] = f.name
        if f.default is not MISSING:
            # A default is a decoded value, so the schema's encode side checks it.
            checked = schema._encode(f.default, ())
            if isinstance(checked, _Issues):
                reasons = "; ".join(str(issue) for issue in checked.issues)
                raise TypeError(
                    f"{cls.__name__}.{f.name}: the default {f.default!r} "
                    f"does not satisfy its schema: {reasons}"
                )
        plan.append((f.name, key, schema, f.default))

    def decode_struct(raw: object, path: IssuePath) -> Any:
        if not isinstance(raw, Mapping):
            return _Issues((TypeMismatch(path, "object", raw),))
        results: list[Any] = []
        for _, key, schema, default in plan:
            if key in raw:
                results.append(schema._decode(raw[key], (*path, key)))
            elif default is not MISSING:
                results.append(default)
            else:
                results.append(_Issues((MissingKey((*path, key)),)))
        names = [name for name, *_ in plan]
        return _collect(lambda vs: cls(**dict(zip(names, vs, strict=True))), results)

    def encode_struct(value: Any, path: IssuePath) -> Any:
        if not isinstance(value, cls):
            return _Issues((TypeMismatch(path, cls.__name__, value),))
        keys = [key for _, key, *_ in plan]
        return _collect(
            lambda vs: dict(zip(keys, vs, strict=True)),
            (s._encode(getattr(value, name), (*path, name)) for name, _, s, _ in plan),
        )

    return Schema(decode_struct, encode_struct)


def _struct_field(
    f: dataclasses.Field[Any], hint: Any, where: str
) -> tuple[str, Schema[Any, Any]]:
    spec: _FieldSpec = f.metadata.get(_FIELD, _FieldSpec(schema=None, key=None))
    if typing.get_origin(hint) is typing.Annotated:
        hint = typing.get_args(hint)[0]
    schema = _infer(hint, where) if spec.schema is None else spec.schema
    return (f.name if spec.key is None else spec.key, schema)


def _infer(annotation: Any, where: str) -> Schema[Any, Any]:
    direct: dict[Any, Schema[Any, Any]] = {
        str: String,
        int: Int,
        float: Float,
        bool: Bool,
        None: Null,
        NoneType: Null,
    }
    if annotation in direct:
        return direct[annotation]
    if (
        isinstance(annotation, type)
        and issubclass(annotation, Struct)
        and annotation is not Struct
    ):
        return annotation.__schema__
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin in (UnionType, typing.Union):
        return Union(*(_infer(arg, where) for arg in args))
    if origin is typing.Literal:
        return Literal(*args)
    if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
        return Array(_infer(args[0], where))
    if origin in (Mapping, dict) and args[0] is str:
        return Record(String, _infer(args[1], where))
    raise TypeError(
        f"{where}: no schema can be inferred for {annotation!r}; "
        "pass one with S.field(schema)"
    )


def _settle(result: Any) -> Effect[Any, ParseError]:
    if isinstance(result, _Issues):
        return fail(ParseError(issues=result.issues))
    return success(result)


def _collect(build: Callable[[list[Any]], Any], results: Iterable[Any]) -> Any:
    """Build from every result, or gather every issue if any result failed."""
    values: list[Any] = []
    issues: list[Issue] = []
    for result in results:
        if isinstance(result, _Issues):
            issues.extend(result.issues)
        else:
            values.append(result)
    return _Issues(tuple(issues)) if issues else build(values)


def _at(path: IssuePath, body: str) -> str:
    location = ""
    for segment in path:
        if isinstance(segment, int):
            location += f"[{segment}]"
        else:
            location += f".{segment}" if location else segment
    return f"{location}: {body}" if location else body
