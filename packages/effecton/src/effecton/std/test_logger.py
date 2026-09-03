import effecton as E


def capture() -> tuple[list[E.LogData], E.CurrentLoggers]:
    entries: list[E.LogData] = []
    return entries, E.CurrentLoggers((E.EffectonLogger(log=entries.append),))


def test_log_info_reaches_the_provided_logger():
    entries, loggers = capture()

    assert E.run_sync(
        E.provide_implicit(E.log_info("hello", 42), loggers)
    ) == E.Succeeded(value=None)

    [entry] = entries
    assert entry.message == ("hello", 42)
    assert entry.log_level == E.LogLevel.INFO
    assert entry.annotations == {}


def test_debug_is_filtered_by_the_default_minimum():
    entries, loggers = capture()

    E.run_sync(E.provide_implicit(E.log_debug("quiet"), loggers))

    assert entries == []


def test_debug_passes_with_a_lower_minimum():
    entries, loggers = capture()
    program = E.provide_implicit(
        E.provide_implicit(E.log_debug("loud"), loggers),
        E.MinimumLogLevel(E.LogLevel.DEBUG),
    )

    E.run_sync(program)

    assert [e.log_level for e in entries] == [E.LogLevel.DEBUG]


def test_none_silences_even_fatal():
    entries, loggers = capture()
    program = E.provide_implicit(
        E.provide_implicit(E.log_fatal("doomed"), loggers),
        E.MinimumLogLevel(E.LogLevel.NONE),
    )

    E.run_sync(program)

    assert entries == []


def test_all_passes_even_trace():
    entries, loggers = capture()
    program = E.provide_implicit(
        E.provide_implicit(E.log_trace("verbose"), loggers),
        E.MinimumLogLevel(E.LogLevel.ALL),
    )

    E.run_sync(program)

    assert [e.log_level for e in entries] == [E.LogLevel.TRACE]


def test_bare_log_uses_current_log_level():
    entries, loggers = capture()

    E.run_sync(E.provide_implicit(E.log("plain"), loggers))

    assert [e.log_level for e in entries] == [E.LogLevel.INFO]

    # Lowering CurrentLogLevel below the minimum filters the bare log call.
    entries2, loggers2 = capture()
    program = E.provide_implicit(
        E.provide_implicit(E.log("plain"), loggers2),
        E.CurrentLogLevel(E.LogLevel.DEBUG),
    )

    E.run_sync(program)

    assert entries2 == []


def test_annotate_logs_merges_and_restores():
    entries, loggers = capture()
    annotated_then_bare = E.annotate_logs(E.log_info("inside"), user_id=1).flat_map(
        lambda _: E.log_info("outside")
    )

    E.run_sync(E.provide_implicit(annotated_then_bare, loggers))

    inside, outside = entries
    assert inside.annotations == {"user_id": 1}
    assert outside.annotations == {}


def test_nested_annotations_merge_and_inner_wins():
    entries, loggers = capture()
    program = E.annotate_logs(
        E.annotate_logs(E.log_info("x"), request="r2", span="s"),
        request="r1",
    )

    E.run_sync(E.provide_implicit(program, loggers))

    [entry] = entries
    assert entry.annotations == {"request": "r2", "span": "s"}


def test_loggers_run_in_tuple_order():
    order: list[str] = []
    loggers = E.CurrentLoggers(
        (
            E.EffectonLogger(log=lambda _: order.append("first")),
            E.EffectonLogger(log=lambda _: order.append("second")),
        )
    )

    E.run_sync(E.provide_implicit(E.log_info("x"), loggers))

    assert order == ["first", "second"]


def test_log_effects_are_reusable_values():
    entries, loggers = capture()
    effect = E.provide_implicit(E.log_info("again"), loggers)

    E.run_sync(effect)
    E.run_sync(effect)

    assert len(entries) == 2
