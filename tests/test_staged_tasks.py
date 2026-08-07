import asyncio

from maica.maica_utils import run_staged_tasks


def test_task_can_span_consecutive_stages() -> None:
    async def scenario() -> None:
        events: list[str] = []
        release_spanning = asyncio.Event()
        spanning_started = asyncio.Event()
        spanning_calls = 0

        async def spanning() -> None:
            nonlocal spanning_calls
            spanning_calls += 1
            events.append("spanning_start")
            spanning_started.set()
            await release_spanning.wait()
            events.append("spanning_end")

        async def first() -> None:
            await spanning_started.wait()
            events.append("first")

        async def second() -> None:
            assert events[-1] == "first"
            events.append("second")

        async def third() -> None:
            assert events[-1] == "second"
            events.append("third")
            release_spanning.set()

        await run_staged_tasks([
            [spanning, first],
            [spanning, second],
            [spanning, third],
        ])

        assert spanning_calls == 1
        assert events == [
            "spanning_start",
            "first",
            "second",
            "third",
            "spanning_end",
        ]

    asyncio.run(scenario())


def test_non_consecutive_occurrences_run_separately() -> None:
    async def scenario() -> None:
        calls = 0

        async def task() -> None:
            nonlocal calls
            calls += 1

        await run_staged_tasks([[task], [], [task]])
        assert calls == 2

    asyncio.run(scenario())


def test_failure_cancels_other_running_tasks_and_raises_plain_exception() -> None:
    async def scenario() -> None:
        spanning_started = asyncio.Event()
        spanning_cancelled = asyncio.Event()

        async def spanning() -> None:
            spanning_started.set()
            try:
                await asyncio.Future()
            finally:
                spanning_cancelled.set()

        async def failing() -> None:
            await spanning_started.wait()
            raise RuntimeError("stage failed")

        try:
            await run_staged_tasks([[spanning], [spanning, failing]])
        except RuntimeError as exc:
            assert str(exc) == "stage failed"
        else:
            raise AssertionError("stage failure was not raised")

        assert spanning_cancelled.is_set()

    asyncio.run(scenario())


def test_duplicate_task_in_one_stage_is_rejected() -> None:
    async def task() -> None:
        pass

    try:
        asyncio.run(run_staged_tasks([[task, task]]))
    except ValueError as exc:
        assert "once" in str(exc)
    else:
        raise AssertionError("duplicate task was accepted")
