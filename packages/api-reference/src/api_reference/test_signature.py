import griffe

from api_reference import signature


def render(code, name):
    with griffe.temporary_visited_module(code, module_name="m") as module:
        obj = module[name]
        assert isinstance(obj, griffe.Object)
        return signature.render(obj, name.rsplit(".", 1)[-1])


def test_renders_parameter_kinds_and_markers():
    code = "def f(a, b=1, /, c=2, *, d: int, **kw: str) -> None: ...\n"

    text = render(code, "f")

    assert text == "def f(a, b=1, /, c=2, *, d: int, **kw: str) -> None"


def test_star_args_replaces_the_keyword_only_marker():
    code = "def g(*args: int, k: str = 'x') -> None: ...\n"

    text = render(code, "g")

    assert text == "def g(*args: int, k: str = 'x') -> None"


def test_renders_type_parameters_with_bounds_defaults_and_paramspec():
    code = "def h[T: Base = Never, **P](x: Callable[P, T]) -> T: ...\n"

    text = render(code, "h")

    assert text == "def h[T: Base = Never, **P](x: Callable[P, T]) -> T"


def test_renders_each_overload_and_hides_the_implementation():
    code = (
        "from typing import overload\n"
        "@overload\n"
        "def s(x: int) -> int: ...\n"
        "@overload\n"
        "def s(x: str) -> str: ...\n"
        "def s(x): ...\n"
    )

    text = render(code, "s")

    assert text == (
        "@overload\ndef s(x: int) -> int\n\n@overload\ndef s(x: str) -> str"
    )


def test_wraps_a_long_signature_one_parameter_per_line():
    code = (
        "def flat_map[B, E2: EffectonError, R2](\n"
        "    self, f: Callable[[A], Effect[B, E2, R2]]\n"
        ") -> Effect[B, E | E2, R | R2]: ...\n"
    )

    text = render(code, "flat_map")

    assert text == (
        "def flat_map[B, E2: EffectonError, R2](\n"
        "    f: Callable[[A], Effect[B, E2, R2]],\n"
        ") -> Effect[B, E | E2, R | R2]"
    )


def test_drops_a_bare_self_but_keeps_an_annotated_one():
    code = (
        "class Binder:\n"
        "    def plain(self, x: int) -> int: ...\n"
        "    def bound[A2](self: Binder[A2], impl: T) -> A2: ...\n"
    )

    plain = render(code, "Binder.plain")
    bound = render(code, "Binder.bound")

    assert plain == "def plain(x: int) -> int"
    assert bound == "def bound[A2](self: Binder[A2], impl: T) -> A2"


def test_renders_a_dataclass_with_decorators_bases_and_fields():
    code = (
        "@final\n"
        "@dataclass(frozen=True)\n"
        "class Err(EffectonError):\n"
        "    path: str\n"
        "    retries: int = 3\n"
        "    _hidden: int = 0\n"
        "    @property\n"
        "    def name(self) -> str: ...\n"
    )

    text = render(code, "Err")

    assert text == (
        "@final\n"
        "@dataclass(frozen=True)\n"
        "class Err(EffectonError):\n"
        "    path: str\n"
        "    retries: int = 3"
    )


def test_a_class_without_fields_shows_an_ellipsis_body():
    code = (
        "class Effect[A, E: EffectonError = Never, R = Never]:\n    def m(self): ...\n"
    )

    text = render(code, "Effect")

    assert text == "class Effect[A, E: EffectonError = Never, R = Never]:\n    ..."


def test_renders_a_property_as_an_annotated_attribute():
    code = "class P:\n    @property\n    def parent(self) -> P: ...\n"

    text = render(code, "P.parent")

    assert text == "parent: P"


def test_renders_a_parametrised_type_alias():
    code = "type ReadError[T] = FileNotFound | PermissionDenied[T]\n"

    text = render(code, "ReadError")

    assert text == "type ReadError[T] = FileNotFound | PermissionDenied[T]"


def test_types_an_unannotated_instance_by_its_constructor():
    code = "logger = EffectonLogger(log=_pretty_log)\nLIMIT: int = 5\n"

    instance = render(code, "logger")
    constant = render(code, "LIMIT")

    assert instance == "logger: EffectonLogger"
    assert constant == "LIMIT: int = 5"


def test_a_module_has_no_signature():
    with griffe.temporary_visited_module("x = 1\n", module_name="m") as module:
        text = signature.render(module, "m")

    assert text == ""
