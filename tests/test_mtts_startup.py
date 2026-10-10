import asyncio

from maica import maica_starter


def test_all_target_includes_tts_connection_when_mtts_is_installed(monkeypatch) -> None:
    monkeypatch.setattr(maica_starter, "mtts_installed", True)

    connection_names = maica_starter._connection_names_for_target("all")

    assert connection_names == maica_starter._CHAT_CONNS_LIST + maica_starter._TTS_CONNS_LIST


def test_all_target_does_not_require_tts_connection_without_mtts(monkeypatch) -> None:
    monkeypatch.setattr(maica_starter, "mtts_installed", False)

    connection_names = maica_starter._connection_names_for_target("all")

    assert connection_names == maica_starter._CHAT_CONNS_LIST


def test_all_target_does_not_start_broken_mtts(monkeypatch) -> None:
    monkeypatch.setattr(maica_starter, "mtts_installed", True)
    monkeypatch.setattr(maica_starter, "mtts_import_error", RuntimeError("missing dependency"))

    assert maica_starter._connection_names_for_target("all") == maica_starter._CHAT_CONNS_LIST


def test_all_target_passes_mtts_connection_to_both_services(monkeypatch) -> None:
    class Connection:
        async def close(self) -> None:
            return None

    async def scenario() -> None:
        connection_names = []
        service_kwargs = []

        async def create_connections(names):
            connection_names.extend(names)
            return [Connection() for _ in names]

        async def start_service(**kwargs):
            service_kwargs.append(kwargs)

        monkeypatch.setattr(maica_starter, "mtts_installed", True)
        monkeypatch.setattr(maica_starter, "_create_root_connections", create_connections)
        monkeypatch.setattr(maica_starter, "maica_start_all", start_service)
        monkeypatch.setattr(maica_starter, "mtts_start_all", start_service)

        await maica_starter.start_all("all")

        assert "mtts_conn" in connection_names
        assert len(service_kwargs) == 2
        assert all("mtts_conn" in kwargs for kwargs in service_kwargs)

    asyncio.run(scenario())


def test_all_target_keeps_chat_running_when_mtts_is_absent(monkeypatch) -> None:
    async def scenario() -> None:
        started = []

        async def create_connections(names):
            assert "mtts_conn" not in names
            return []

        async def start_chat(**_kwargs):
            started.append("chat")

        async def unexpected_tts(**_kwargs):
            raise AssertionError("MTTS must not start when it is not installed")

        monkeypatch.setattr(maica_starter, "mtts_installed", False)
        monkeypatch.setattr(maica_starter, "_create_root_connections", create_connections)
        monkeypatch.setattr(maica_starter, "maica_start_all", start_chat)
        monkeypatch.setattr(maica_starter, "mtts_start_all", unexpected_tts)

        await maica_starter.start_all("all")

        assert started == ["chat"]

    asyncio.run(scenario())
