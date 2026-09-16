"""Smoke test against the real package: every export lands on the page."""

import effecton as E
from api_reference import markdown
from api_reference.collect import collect, load
from api_reference.topics import TOPICS


def test_every_export_and_extra_is_on_the_page():
    root = load()

    result = E.run_sync_exit(collect(root, TOPICS))

    assert isinstance(result, E.Succeeded)
    text = markdown.render_page(result.value)
    for name in E.__all__:
        assert f"\n### E.{name}\n" in text, name
    for topic in TOPICS:
        for extra in topic.extras:
            assert f"\n### {extra.rsplit('.', 1)[-1]}\n" in text, extra
    assert "\n### E.FileSystem.Protocol\n" in text
    assert "\n#### E.Effect.flat_map\n" in text
