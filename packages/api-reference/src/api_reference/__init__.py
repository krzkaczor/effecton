"""Render the docs API Reference page from the effecton sources.

griffe reads the package statically; ``collect`` buckets every public name
into the curated ``topics.TOPICS`` order, ``signature`` and ``markdown`` turn
that into the page text, and ``program`` writes it through E.FileSystem.
"""
