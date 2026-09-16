import griffe

import effecton as E
from api_reference.collect import UnmappedModule, collect
from api_reference.topics import Topic

PACKAGE = {
    "__init__.py": (
        "from pkg import svc as Svc\n"
        "from pkg.f import f\n"
        "from pkg.svc import _now as now\n"
        '__all__ = ["Svc", "f", "now"]\n'
    ),
    "f.py": 'def f(x: int) -> int:\n    """Doc."""\n',
    "svc.py": (
        "import typing\n"
        "from pkg.f import f\n"
        "class Protocol(typing.Protocol):\n"
        "    def now(self) -> int: ...\n"
        "class Live(Protocol):\n"
        "    def now(self) -> int: ...\n"
        "    def extra(self) -> None: ...\n"
        "    def _internal(self) -> None: ...\n"
        "def _now() -> int: ...\n"
        "_HIDDEN = 1\n"
    ),
}
TOPICS = (Topic("Core", ("f",)), Topic("Service", ("svc",)))


def run(topics):
    with griffe.temporary_visited_package("pkg", modules=PACKAGE) as root:
        return E.run_sync_exit(collect(root, topics))


def test_buckets_exports_by_module_in_topic_order():
    result = run(TOPICS)

    assert isinstance(result, E.Succeeded)
    sections = result.value.sections
    assert [section.title for section in sections] == ["Core", "Service"]
    assert [symbol.display for symbol in sections[0].symbols] == ["E.f"]
    assert [symbol.display for symbol in sections[1].symbols] == [
        "E.Svc",
        "E.Svc.Protocol",
        "E.Svc.Live",
        "E.now",
    ]


def test_descends_into_a_submodule_that_shadows_its_function():
    result = run(TOPICS)

    assert isinstance(result, E.Succeeded)
    f = result.value.sections[0].symbols[0]
    assert isinstance(f.obj, griffe.Function)
    assert f.obj.path == "pkg.f.f"


def test_an_implementation_lists_only_what_the_protocol_lacks():
    result = run(TOPICS)

    assert isinstance(result, E.Succeeded)
    by_name = {s.display: s for s in result.value.sections[1].symbols}
    assert [m.display for m in by_name["E.Svc.Protocol"].members] == [
        "E.Svc.Protocol.now"
    ]
    assert [m.display for m in by_name["E.Svc.Live"].members] == ["E.Svc.Live.extra"]


def test_an_export_from_an_unlisted_module_fails():
    result = run((Topic("Core", ("f",)),))

    assert result == E.Failure(cause=E.Fail(UnmappedModule(name="E.Svc", module="svc")))
    assert "api_reference.topics.TOPICS" in str(UnmappedModule("E.Svc", "svc"))


def test_extras_are_appended_with_a_note():
    topics = (Topic("Core", ("f",), extras=("svc.Live",)), Topic("Service", ("svc",)))

    result = run(topics)

    assert isinstance(result, E.Succeeded)
    extra = result.value.sections[0].symbols[-1]
    assert extra.display == "Live"
    assert extra.note is not None and "E.Live" in extra.note
