import threading
from collections.abc import Mapping
from datetime import date, datetime
from typing import Annotated, Any, Literal

import pytest

import effecton as E

S = E.Schema


def ok(value: object):
    return E.Succeeded(value)


def bad(*issues: S.Issue):
    return E.Failure(cause=E.Fail(S.ParseError(issues=issues)))


class Address(S.Struct):
    city: str
    zip_code: str = S.field(key="zip")


class Base(S.Struct):
    id: str


class Child(Base):
    count: int


class User(S.Struct):
    name: str
    age: int = S.field(
        S.Int.check(S.filter(lambda n: n >= 0, message="expected a number at least 0"))
    )
    created: datetime = S.field(S.DateTimeFromString, key="createdAt")
    address: Address
    role: Literal["admin", "member"] = "member"
    nickname: str | None = None
    tags: tuple[str, ...] = ()
    scores: Mapping[str, int]


def test_string_decodes_and_encodes_a_str():
    decoded = E.run_sync_exit(S.decode(S.String)("hi"))
    encoded = E.run_sync_exit(S.encode(S.String)("hi"))

    assert decoded == ok("hi")
    assert encoded == ok("hi")


def test_string_rejects_other_types_with_a_type_mismatch():
    r = E.run_sync_exit(S.decode(S.String)(1))

    assert r == bad(S.TypeMismatch(path=(), expected="string", actual=1))


def test_int_is_strict_about_bool_and_float():
    from_bool = E.run_sync_exit(S.decode(S.Int)(True))
    from_float = E.run_sync_exit(S.decode(S.Int)(1.0))
    from_int = E.run_sync_exit(S.decode(S.Int)(7))

    assert from_bool == bad(S.TypeMismatch(path=(), expected="integer", actual=True))
    assert from_float == bad(S.TypeMismatch(path=(), expected="integer", actual=1.0))
    assert from_int == ok(7)


def test_float_accepts_int_and_float_but_not_bool():
    from_int = E.run_sync_exit(S.decode(S.Float)(1))
    from_float = E.run_sync_exit(S.decode(S.Float)(1.5))
    from_bool = E.run_sync_exit(S.decode(S.Float)(False))

    assert from_int == ok(1)
    assert from_float == ok(1.5)
    assert from_bool == bad(S.TypeMismatch(path=(), expected="number", actual=False))


def test_bool_null_and_unknown():
    a_bool = E.run_sync_exit(S.decode(S.Bool)(True))
    not_bool = E.run_sync_exit(S.decode(S.Bool)(1))
    a_null = E.run_sync_exit(S.decode(S.Null)(None))
    not_null = E.run_sync_exit(S.decode(S.Null)(0))
    anything = E.run_sync_exit(S.decode(S.Unknown)([1, "x"]))

    assert a_bool == ok(True)
    assert not_bool == bad(S.TypeMismatch(path=(), expected="boolean", actual=1))
    assert a_null == ok(None)
    assert not_null == bad(S.TypeMismatch(path=(), expected="null", actual=0))
    assert anything == ok([1, "x"])


def test_literal_accepts_only_its_values_and_keeps_bool_apart_from_int():
    schema = S.Literal("a", 1)

    hit = E.run_sync_exit(S.decode(schema)("a"))
    miss = E.run_sync_exit(S.decode(schema)("b"))
    bool_is_not_one = E.run_sync_exit(S.decode(schema)(True))
    encode_miss = E.run_sync_exit(S.encode(schema)("b"))

    assert hit == ok("a")
    assert miss == bad(S.TypeMismatch(path=(), expected="'a' | 1", actual="b"))
    assert bool_is_not_one == bad(
        S.TypeMismatch(path=(), expected="'a' | 1", actual=True)
    )
    assert encode_miss == bad(S.TypeMismatch(path=(), expected="'a' | 1", actual="b"))


def test_encode_checks_the_runtime_type_too():
    r = E.run_sync_exit(S.encode(S.Int)("x"))  # ty: ignore[invalid-argument-type]

    assert r == bad(S.TypeMismatch(path=(), expected="integer", actual="x"))


def test_decode_is_lazy_until_run():
    calls: list[object] = []
    spy: S.Schema[object, object] = S.Schema(
        lambda raw, path: calls.append(raw) or raw, lambda value, path: value
    )

    effect = S.decode(spy)("x")

    assert calls == []
    assert E.run_sync_exit(effect) == ok("x")
    assert calls == ["x"]


def test_parse_error_renders_one_line_per_issue_with_paths():
    error = S.ParseError(
        issues=(
            S.TypeMismatch(path=(), expected="string", actual=1),
            S.MissingKey(path=("users", 2, "createdAt")),
            S.RefinementFailed(path=("name",), message="too short", actual=""),
            S.TransformFailed(path=("a", "b"), message="not ISO 8601", actual="x"),
            S.InvalidJson(path=(), reason="Expecting value"),
            S.NoUnionMember(
                path=("id",),
                actual=1.5,
                issues=(S.TypeMismatch(path=("id",), expected="string", actual=1.5),),
            ),
        )
    )

    rendered = str(error)

    assert rendered == "\n".join(
        [
            "expected string, got 1",
            "users[2].createdAt: is missing",
            "name: too short, got ''",
            "a.b: not ISO 8601, got 'x'",
            "invalid JSON: Expecting value",
            "id: no union member matched 1.5",
            "  id: expected string, got 1.5",
        ]
    )


def test_array_decodes_to_a_tuple_and_encodes_to_a_list():
    schema = S.Array(S.Int)

    from_list = E.run_sync_exit(S.decode(schema)([1, 2]))
    from_tuple = E.run_sync_exit(S.decode(schema)((1, 2)))
    encoded = E.run_sync_exit(S.encode(schema)((1, 2)))

    assert from_list == ok((1, 2))
    assert from_tuple == ok((1, 2))
    assert encoded == ok([1, 2])


def test_array_collects_every_item_issue_with_its_index():
    r = E.run_sync_exit(S.decode(S.Array(S.Int))([1, "x", 3, None]))

    assert r == bad(
        S.TypeMismatch(path=(1,), expected="integer", actual="x"),
        S.TypeMismatch(path=(3,), expected="integer", actual=None),
    )


def test_array_rejects_non_sequences_and_strings():
    not_a_list = E.run_sync_exit(S.decode(S.Array(S.String))("ab"))
    encode_a_list = E.run_sync_exit(S.encode(S.Array(S.Int))([1]))  # ty: ignore[invalid-argument-type]

    assert not_a_list == bad(S.TypeMismatch(path=(), expected="array", actual="ab"))
    assert encode_a_list == bad(S.TypeMismatch(path=(), expected="tuple", actual=[1]))


def test_record_round_trips_and_reports_key_and_value_issues():
    schema = S.Record(S.String, S.Int)

    decoded = E.run_sync_exit(S.decode(schema)({"a": 1}))
    encoded = E.run_sync_exit(S.encode(schema)({"a": 1}))
    broken = E.run_sync_exit(S.decode(schema)({"a": "x", 2: 3}))
    not_a_mapping = E.run_sync_exit(S.decode(schema)([]))

    assert decoded == ok({"a": 1})
    assert encoded == ok({"a": 1})
    assert broken == bad(
        S.TypeMismatch(path=("a",), expected="integer", actual="x"),
        S.TypeMismatch(path=(2,), expected="string", actual=2),
    )
    assert not_a_mapping == bad(S.TypeMismatch(path=(), expected="object", actual=[]))


def test_record_keys_go_through_their_own_schema():
    schema = S.Record(S.IntFromString, S.Int)

    decoded = E.run_sync_exit(S.decode(schema)({"1": 2}))
    encoded = E.run_sync_exit(S.encode(schema)({1: 2}))

    assert decoded == ok({1: 2})
    assert encoded == ok({"1": 2})


def test_tuple_is_fixed_length_and_positional():
    schema = S.Tuple(S.String, S.Int)

    decoded = E.run_sync_exit(S.decode(schema)(["a", 1]))
    encoded = E.run_sync_exit(S.encode(schema)(("a", 1)))
    wrong_length = E.run_sync_exit(S.decode(schema)(["a"]))
    wrong_item = E.run_sync_exit(S.decode(schema)([1, "a"]))

    assert decoded == ok(("a", 1))
    assert encoded == ok(["a", 1])
    assert wrong_length == bad(
        S.TypeMismatch(path=(), expected="array of 2 items", actual=["a"])
    )
    assert wrong_item == bad(
        S.TypeMismatch(path=(0,), expected="string", actual=1),
        S.TypeMismatch(path=(1,), expected="integer", actual="a"),
    )


def test_union_takes_the_first_member_that_matches():
    schema = S.Union(S.Int, S.String)

    an_int = E.run_sync_exit(S.decode(schema)(1))
    a_str = E.run_sync_exit(S.decode(schema)("a"))
    encoded = E.run_sync_exit(S.encode(schema)("a"))

    assert an_int == ok(1)
    assert a_str == ok("a")
    assert encoded == ok("a")


def test_union_reports_every_members_issues_when_none_matches():
    r = E.run_sync_exit(S.decode(S.Union(S.Int, S.String))(1.5))

    assert r == bad(
        S.NoUnionMember(
            path=(),
            actual=1.5,
            issues=(
                S.TypeMismatch(path=(), expected="integer", actual=1.5),
                S.TypeMismatch(path=(), expected="string", actual=1.5),
            ),
        )
    )


def test_null_or_accepts_none_in_both_directions():
    schema = S.NullOr(S.Int)

    a_none = E.run_sync_exit(S.decode(schema)(None))
    an_int = E.run_sync_exit(S.decode(schema)(1))
    encoded = E.run_sync_exit(S.encode(schema)(None))

    assert a_none == ok(None)
    assert an_int == ok(1)
    assert encoded == ok(None)


def test_instance_of_passes_instances_in_both_directions():
    schema = S.instance_of(datetime)
    moment = datetime(2026, 9, 20, 10, 30)

    decoded = E.run_sync_exit(S.decode(schema)(moment))
    encoded = E.run_sync_exit(S.encode(schema)(moment))
    rejected = E.run_sync_exit(S.decode(schema)("x"))

    assert decoded == ok(moment)
    assert encoded == ok(moment)
    assert rejected == bad(S.TypeMismatch(path=(), expected="datetime", actual="x"))


def test_transform_maps_both_directions():
    schema = S.transform(S.String, decode=len, encode=lambda n: "x" * n)

    decoded = E.run_sync_exit(S.decode(schema)("abc"))
    encoded = E.run_sync_exit(S.encode(schema)(3))
    wrong_wire_type = E.run_sync_exit(S.decode(schema)(1))

    assert decoded == ok(3)
    assert encoded == ok("xxx")
    assert wrong_wire_type == bad(S.TypeMismatch(path=(), expected="string", actual=1))


def test_transform_or_fail_reports_invalid_as_a_transform_issue():
    def halve(n: int) -> int | S.Invalid:
        return n // 2 if n % 2 == 0 else S.Invalid("expected an even number")

    schema = S.transform_or_fail(S.Int, decode=halve, encode=lambda n: n * 2)

    decoded = E.run_sync_exit(S.decode(schema)(4))
    rejected = E.run_sync_exit(S.decode(schema)(3))

    assert decoded == ok(2)
    assert rejected == bad(
        S.TransformFailed(path=(), message="expected an even number", actual=3)
    )


def test_an_exception_inside_a_transform_is_a_defect():
    boom = ValueError("boom")

    def explode(_: str) -> int:
        raise boom

    schema = S.transform(S.String, decode=explode, encode=str)

    r = E.run_sync_exit(S.decode(schema)("x"))

    assert r == E.Failure(cause=E.Die(defect=boom))


def test_a_guarded_transform_never_calls_its_function_on_a_foreign_value():
    seen: list[object] = []

    def remember(n: int) -> int | S.Invalid:
        seen.append(n)
        return n

    schema = S.transform_or_fail(S.Int, decode=remember, encode=remember, to=S.Int)

    r = E.run_sync_exit(S.encode(schema)("x"))  # ty: ignore[invalid-argument-type]

    assert r == bad(S.TypeMismatch(path=(), expected="integer", actual="x"))
    assert seen == []


def test_null_or_encodes_none_without_entering_its_member():
    an_int = E.run_sync_exit(S.encode(S.NullOr(S.IntFromString))(None))
    a_path = E.run_sync_exit(S.encode(S.NullOr(S.PathFromString))(None))
    a_moment = E.run_sync_exit(S.encode(S.NullOr(S.DateTimeFromString))(None))
    checked_text = E.run_sync_exit(
        S.encode(
            S.NullOr(S.String.check(S.filter(lambda s: len(s) >= 1, message="empty")))
        )(None)
    )
    checked_int = E.run_sync_exit(
        S.encode(
            S.NullOr(S.Int.check(S.filter(lambda n: n > 0, message="not positive")))
        )(None)
    )

    assert an_int == ok(None)
    assert a_path == ok(None)
    assert a_moment == ok(None)
    assert checked_text == ok(None)
    assert checked_int == ok(None)


def test_union_encode_passes_a_value_its_first_member_cannot_take():
    r = E.run_sync_exit(S.encode(S.Union(S.DateFromString, S.String))("abc"))

    assert r == ok("abc")


def test_builtin_transforms_reject_wrongly_typed_values_on_encode():
    from_bool = E.run_sync_exit(S.encode(S.IntFromString)(True))
    from_text = E.run_sync_exit(S.encode(S.IntFromString)("x"))  # ty: ignore[invalid-argument-type]
    a_datetime = E.run_sync_exit(S.encode(S.DateFromString)(datetime(2026, 9, 20, 10)))

    assert from_bool == bad(S.TypeMismatch(path=(), expected="integer", actual=True))
    assert from_text == bad(S.TypeMismatch(path=(), expected="integer", actual="x"))
    assert a_datetime == bad(
        S.RefinementFailed(
            path=(),
            message="expected a date without a time",
            actual=datetime(2026, 9, 20, 10),
        )
    )


@pytest.mark.parametrize(
    ("schema", "value"),
    [
        (S.IntFromString, 42),
        (S.FloatFromString, 1.5),
        (S.DateTimeFromString, datetime(2026, 9, 20, 10, 30)),
        (S.DateFromString, date(2026, 9, 20)),
        (S.PathFromString, E.Path("/a/b")),
    ],
)
def test_every_builtin_transform_round_trips_bare_and_inside_null_or(
    schema: S.Schema[Any, Any], value: Any
):
    nullable = S.NullOr(schema)

    bare = E.run_sync_exit(S.decode(schema)(E.run_sync(S.encode(schema)(value))))
    through_null = E.run_sync_exit(
        S.decode(nullable)(E.run_sync(S.encode(nullable)(value)))
    )
    a_none = E.run_sync_exit(S.encode(nullable)(None))

    assert bare == ok(value)
    assert through_null == ok(value)
    assert a_none == ok(None)


def test_builtin_string_transforms_round_trip():
    an_int = E.run_sync_exit(S.decode(S.IntFromString)("42"))
    a_float = E.run_sync_exit(S.decode(S.FloatFromString)("1.5"))
    a_moment = E.run_sync_exit(S.decode(S.DateTimeFromString)("2026-09-20T10:30:00"))
    a_day = E.run_sync_exit(S.decode(S.DateFromString)("2026-09-20"))
    a_path = E.run_sync_exit(S.decode(S.PathFromString)("/a/b"))
    int_back = E.run_sync_exit(S.encode(S.IntFromString)(42))
    moment_back = E.run_sync_exit(
        S.encode(S.DateTimeFromString)(datetime(2026, 9, 20, 10, 30))
    )
    day_back = E.run_sync_exit(S.encode(S.DateFromString)(date(2026, 9, 20)))
    path_back = E.run_sync_exit(S.encode(S.PathFromString)(E.Path("/a/b")))

    assert an_int == ok(42)
    assert a_float == ok(1.5)
    assert a_moment == ok(datetime(2026, 9, 20, 10, 30))
    assert a_day == ok(date(2026, 9, 20))
    assert a_path == ok(E.Path("/a/b"))
    assert int_back == ok("42")
    assert moment_back == ok("2026-09-20T10:30:00")
    assert day_back == ok("2026-09-20")
    assert path_back == ok("/a/b")


def test_builtin_string_transforms_reject_malformed_text():
    not_int = E.run_sync_exit(S.decode(S.IntFromString)("4x"))
    not_float = E.run_sync_exit(S.decode(S.FloatFromString)("nope"))
    not_moment = E.run_sync_exit(S.decode(S.DateTimeFromString)("yesterday"))
    not_day = E.run_sync_exit(S.decode(S.DateFromString)("2026-13-40"))

    assert not_int == bad(
        S.TransformFailed(path=(), message="expected an integer string", actual="4x")
    )
    assert not_float == bad(
        S.TransformFailed(path=(), message="expected a number string", actual="nope")
    )
    assert not_moment == bad(
        S.TransformFailed(
            path=(), message="expected an ISO 8601 datetime", actual="yesterday"
        )
    )
    assert not_day == bad(
        S.TransformFailed(
            path=(), message="expected an ISO 8601 date", actual="2026-13-40"
        )
    )


def test_filter_guards_decode_and_encode():
    even = S.Int.check(
        S.filter(lambda n: n % 2 == 0, message="expected an even number")
    )

    passed = E.run_sync_exit(S.decode(even)(2))
    decode_rejected = E.run_sync_exit(S.decode(even)(3))
    encode_rejected = E.run_sync_exit(S.encode(even)(3))
    wrong_type = E.run_sync_exit(S.decode(even)("x"))

    assert passed == ok(2)
    assert decode_rejected == bad(
        S.RefinementFailed(path=(), message="expected an even number", actual=3)
    )
    assert encode_rejected == bad(
        S.RefinementFailed(path=(), message="expected an even number", actual=3)
    )
    assert wrong_type == bad(S.TypeMismatch(path=(), expected="integer", actual="x"))


def test_check_reports_every_failing_check():
    schema = S.String.check(
        S.filter(lambda s: len(s) >= 3, message="expected a length of at least 3"),
        S.pattern(r"^[a-z]+$"),
    )

    r = E.run_sync_exit(S.decode(schema)("A"))

    assert r == bad(
        S.RefinementFailed(
            path=(), message="expected a length of at least 3", actual="A"
        ),
        S.RefinementFailed(
            path=(), message="expected a string matching ^[a-z]+$", actual="A"
        ),
    )


def test_pattern_finds_a_match_in_both_directions():
    lowercase = S.String.check(S.pattern(r"^[a-z]+$"))
    failure = S.RefinementFailed(
        path=(), message="expected a string matching ^[a-z]+$", actual="AB"
    )

    matched = E.run_sync_exit(S.decode(lowercase)("ab"))
    decode_rejected = E.run_sync_exit(S.decode(lowercase)("AB"))
    encode_rejected = E.run_sync_exit(S.encode(lowercase)("AB"))

    assert matched == ok("ab")
    assert decode_rejected == bad(failure)
    assert encode_rejected == bad(failure)


RAW_USER = {
    "name": "Ada",
    "age": 36,
    "createdAt": "2026-09-20T10:30:00",
    "address": {"city": "London", "zip": "N1"},
    "scores": {"a": 1},
}


def test_struct_decodes_into_a_frozen_dataclass_with_defaults():
    r = E.run_sync_exit(S.decode(User)({**RAW_USER, "ignored": True}))

    assert r == ok(
        User(
            name="Ada",
            age=36,
            created=datetime(2026, 9, 20, 10, 30),
            address=Address(city="London", zip_code="N1"),
            scores={"a": 1},
        )
    )


def test_struct_encodes_every_field_under_its_wire_key():
    user = User(
        name="Ada",
        age=36,
        created=datetime(2026, 9, 20, 10, 30),
        address=Address(city="London", zip_code="N1"),
        nickname="ada",
        tags=("a",),
        scores={"a": 1},
    )

    r = E.run_sync_exit(S.encode(User)(user))

    assert r == ok(
        {
            "name": "Ada",
            "age": 36,
            "createdAt": "2026-09-20T10:30:00",
            "address": {"city": "London", "zip": "N1"},
            "role": "member",
            "nickname": "ada",
            "tags": ["a"],
            "scores": {"a": 1},
        }
    )


def test_struct_round_trips():
    encoded = E.run_sync(S.encode(User)(E.run_sync(S.decode(User)(RAW_USER))))

    again = E.run_sync_exit(S.decode(User)(encoded))

    assert again == E.run_sync_exit(S.decode(User)(RAW_USER))


def test_struct_collects_every_issue_with_wire_key_paths():
    raw = {
        "name": 1,
        "age": -1,
        "address": {"city": "London"},
        "role": "owner",
        "tags": ["a", 2],
    }

    r = E.run_sync_exit(S.decode(User)(raw))

    assert r == bad(
        S.TypeMismatch(path=("name",), expected="string", actual=1),
        S.RefinementFailed(
            path=("age",), message="expected a number at least 0", actual=-1
        ),
        S.MissingKey(path=("createdAt",)),
        S.MissingKey(path=("address", "zip")),
        S.TypeMismatch(path=("role",), expected="'admin' | 'member'", actual="owner"),
        S.TypeMismatch(path=("tags", 1), expected="string", actual=2),
        S.MissingKey(path=("scores",)),
    )


def test_struct_rejects_non_mappings_and_foreign_instances():
    not_a_mapping = E.run_sync_exit(S.decode(Address)([]))
    wrong_instance = E.run_sync_exit(S.encode(Address)("x"))  # ty: ignore[invalid-argument-type]

    assert not_a_mapping == bad(S.TypeMismatch(path=(), expected="object", actual=[]))
    assert wrong_instance == bad(
        S.TypeMismatch(path=(), expected="Address", actual="x")
    )


def test_struct_instances_are_frozen_and_keyword_only():
    address = Address(city="London", zip_code="N1")

    with pytest.raises(AttributeError):
        address.city = "Paris"  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError):
        Address("London", "N1")  # ty: ignore[missing-argument, too-many-positional-arguments]


def test_struct_classes_nest_inside_array_and_null_or():
    many = E.run_sync_exit(S.decode(S.Array(Address))([{"city": "A", "zip": "1"}]))
    none = E.run_sync_exit(S.decode(S.NullOr(Address))(None))
    via_schema = E.run_sync_exit(
        S.decode(S.Union(S.struct_schema(Address), S.String))("x")
    )

    assert many == ok((Address(city="A", zip_code="1"),))
    assert none == ok(None)
    assert via_schema == ok("x")


def test_an_annotation_with_no_inferable_schema_fails_at_class_definition():
    with pytest.raises(TypeError) as raised:

        class Event(S.Struct):
            at: datetime

    assert str(raised.value) == (
        "Event.at: no schema can be inferred for <class 'datetime.datetime'>; "
        "pass one with S.field(schema)"
    )


def test_two_fields_sharing_a_wire_key_fail_at_class_definition():
    with pytest.raises(TypeError) as raised:

        class Point(S.Struct):
            a: int = S.field(key="x")
            b: int = S.field(key="x")

    assert str(raised.value) == "Point: fields 'a' and 'b' share the wire key 'x'"


def test_a_renamed_field_colliding_with_another_field_name_fails():
    with pytest.raises(TypeError) as raised:

        class Pair(S.Struct):
            a: int = S.field(key="b")
            b: int

    assert str(raised.value) == "Pair: fields 'a' and 'b' share the wire key 'b'"


def test_a_default_that_fails_its_schemas_check_fails_at_class_definition():
    with pytest.raises(TypeError) as raised:

        class Port(S.Struct):
            number: int = S.field(
                S.Int.check(
                    S.filter(lambda n: 0 < n < 65536, message="expected a port")
                ),
                default=0,
            )

    assert str(raised.value) == (
        "Port.number: the default 0 does not satisfy its schema: expected a port, got 0"
    )


def test_a_default_of_the_wrong_type_fails_at_class_definition():
    with pytest.raises(TypeError) as raised:

        class Config(S.Struct):
            retries: int = S.field(S.Int, default="3")  # ty: ignore[invalid-argument-type]

    assert str(raised.value) == (
        "Config.retries: the default '3' does not satisfy its schema: "
        "expected integer, got '3'"
    )


def test_a_default_is_validated_on_the_decoded_side():
    class Event(S.Struct):
        at: datetime = S.field(S.DateTimeFromString, default=datetime(2026, 1, 1))
        tags: tuple[str, ...] = ()
        nickname: str | None = None

    decoded = E.run_sync_exit(S.decode(Event)({}))

    assert decoded == ok(Event(at=datetime(2026, 1, 1), tags=(), nickname=None))


def test_an_empty_wire_key_is_honored():
    class Odd(S.Struct):
        value: int = S.field(key="")

    decoded = E.run_sync_exit(S.decode(Odd)({"": 1}))
    encoded = E.run_sync_exit(S.encode(Odd)(Odd(value=1)))

    assert decoded == ok(Odd(value=1))
    assert encoded == ok({"": 1})


def test_an_annotation_of_struct_itself_fails_at_class_definition():
    with pytest.raises(TypeError) as raised:

        class Wrapper(S.Struct):
            inner: S.Struct

    assert str(raised.value) == (
        "Wrapper.inner: no schema can be inferred for "
        "<class 'effecton.std.schema.Struct'>; pass one with S.field(schema)"
    )


def test_a_struct_subclass_keeps_the_inherited_fields():
    decoded = E.run_sync_exit(S.decode(Child)({"id": "a", "count": 1}))
    encoded = E.run_sync_exit(S.encode(Child)(Child(id="a", count=1)))

    assert decoded == ok(Child(id="a", count=1))
    assert encoded == ok({"id": "a", "count": 1})


def test_issue_paths_use_wire_keys_to_decode_and_field_names_to_encode():
    decoded = E.run_sync_exit(S.decode(Address)({"city": "London", "zip": 1}))
    encoded = E.run_sync_exit(
        S.encode(Address)(Address(city="London", zip_code=1))  # ty: ignore[invalid-argument-type]
    )

    assert decoded == bad(S.TypeMismatch(path=("zip",), expected="string", actual=1))
    assert encoded == bad(
        S.TypeMismatch(path=("zip_code",), expected="string", actual=1)
    )


def test_decode_json_parses_then_decodes():
    r = E.run_sync_exit(S.decode_json(Address)('{"city": "London", "zip": "N1"}'))

    assert r == ok(Address(city="London", zip_code="N1"))


def test_decode_json_reports_malformed_text_as_an_issue():
    r = E.run_sync_exit(S.decode_json(S.Int)("{nope"))

    assert r == bad(
        S.InvalidJson(
            path=(),
            reason="Expecting property name enclosed in double quotes: "
            "line 1 column 2 (char 1)",
        )
    )


def test_decode_json_reports_a_number_python_refuses_to_build_as_an_issue():
    r = E.run_sync_exit(S.decode_json(S.Int)("1" + "0" * 5000))

    assert r == bad(
        S.InvalidJson(
            path=(),
            reason="Exceeds the limit (4300 digits) for integer string conversion: "
            "value has 5001 digits; use sys.set_int_max_str_digits() to "
            "increase the limit",
        )
    )


def test_decode_json_reports_deeply_nested_text_as_an_issue():
    # The C JSON scanner overflows only once it exhausts the C stack, whose
    # size follows `ulimit -s` on the main thread (unlimited on some CI hosts),
    # so decode on a thread with a fixed 1 MiB stack instead.
    exits: list[E.Exit[object, S.ParseError]] = []

    def decode():
        exits.append(E.run_sync_exit(S.decode_json(S.Unknown)("[" * 100000)))

    previous = threading.stack_size(1 << 20)
    try:
        thread = threading.Thread(target=decode)
        thread.start()
    finally:
        threading.stack_size(previous)
    thread.join()

    assert exits == [bad(S.InvalidJson(path=(), reason="nesting is too deep"))]


def test_decode_json_rejects_non_text_input():
    r = E.run_sync_exit(S.decode_json(S.Int)(1))  # ty: ignore[invalid-argument-type]

    assert r == bad(S.TypeMismatch(path=(), expected="JSON text", actual=1))


def test_encode_json_encodes_then_serializes():
    r = E.run_sync_exit(S.encode_json(Address)(Address(city="London", zip_code="N1")))

    assert r == ok('{"city": "London", "zip": "N1"}')


def test_encode_json_of_a_form_json_cannot_serialize_is_a_defect():
    r = E.run_sync_exit(S.encode_json(S.instance_of(datetime))(datetime(2026, 9, 20)))

    match r:
        case E.Failure(cause=E.Die(defect=defect)):
            assert isinstance(defect, TypeError)
        case _:
            pytest.fail(f"expected a defect, got {r!r}")


def test_json_round_trip():
    text = E.run_sync(S.encode_json(S.Array(S.DateFromString))((date(2026, 9, 20),)))

    back = E.run_sync_exit(S.decode_json(S.Array(S.DateFromString))(text))

    assert text == '["2026-09-20"]'
    assert back == ok((date(2026, 9, 20),))


def test_annotated_metadata_is_ignored_on_struct_fields():
    class Tagged(S.Struct):
        count: Annotated[int, "some metadata"]
        label: Annotated[str, "x"] = S.field(key="l")

    result = E.run_sync_exit(S.decode(Tagged)({"count": 3, "l": "a"}))

    assert result == ok(Tagged(count=3, label="a"))


def test_struct_schema_accepts_a_custom_field_resolver():
    class Pair(S.Struct):
        left: int
        right: int

    def by_upper_key(f, hint, where):
        return (f.name.upper(), S.IntFromString)

    schema = S._struct_schema(Pair, by_upper_key)

    assert E.run_sync(S.decode(schema)({"LEFT": "1", "RIGHT": "2"})) == Pair(
        left=1, right=2
    )
