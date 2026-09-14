---
effecton: patch
---

Add the `E.Tracer` service: `E.with_span(effect, name, kind=..., **attributes)` opens a span around an effect (also as `effect.with_span`), `E.annotate_current_span` adds attributes, `E.current_span` reads the open span, `E.Tracer.Live` is the in-memory default, `E.Tracer.Test` records its spans, and the `test_tracer` pytest fixture provides one
