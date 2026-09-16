import effecton as E
from api_reference.collect import Reference
from api_reference.program import write_reference

OUT = E.Path("/repo/docs/src/pages/api.md")


def test_writes_the_page_creating_parent_directories():
    fs = E.FileSystem.Test()

    result = E.run_sync_exit(
        write_reference(OUT, Reference(())).provide(E.FileSystem.Protocol)(fs)
    )

    assert result == E.Succeeded(value=OUT)
    content = fs.files[OUT]
    assert isinstance(content, str)
    assert content.startswith("---\ntitle: API Reference\n")
    assert OUT.parent in fs.directories


def test_fails_when_the_target_directory_is_a_file():
    fs = E.FileSystem.Test(files={OUT.parent: "not a directory"})

    result = E.run_sync_exit(
        write_reference(OUT, Reference(())).provide(E.FileSystem.Protocol)(fs)
    )

    assert result == E.Failure(
        cause=E.Fail(E.FileSystem.PathAlreadyExists(path=OUT.parent))
    )
