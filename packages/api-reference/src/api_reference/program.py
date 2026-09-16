"""Write the rendered page to disk through the FileSystem service."""

import effecton as E
from api_reference import markdown
from api_reference.collect import Reference


@E.gen
def write_reference(
    out: E.Path, reference: Reference
) -> E.EffectGen[
    E.Path,
    E.FileSystem.FileNotFound
    | E.FileSystem.PermissionDenied
    | E.FileSystem.PathAlreadyExists
    | E.FileSystem.PathIsADirectory
    | E.FileSystem.PathIsNotADirectory,
    E.FileSystem.Protocol,
]:
    fs = yield from E.require(E.FileSystem.Protocol)

    yield from fs.make_directory(out.parent, recursive=True)
    yield from fs.write_file_string(out, markdown.render_page(reference))
    return out
