import asyncio
from types import SimpleNamespace

from maica.maica_utils import FullSocketsContainer
from maica.mtools import mspire
from maica.mtools.mpostal import make_postmail
from maica.mtools.post_proc import post_proc
from maica.mtools.post_proc_rt import TalkSplitV2


def test_mspire_prompt_supports_english() -> None:
    async def fake_fetch(_fsc):
        return "a topic", "a summary"

    async def scenario() -> None:
        old_fetch = mspire.fetch_ms_meta
        mspire.fetch_ms_meta = fake_fetch
        try:
            fsc = FullSocketsContainer()
            fsc.maica_settings.basic.target_lang = "en"
            prompt = await mspire.make_inspire(fsc)
            assert "a topic" in prompt.en
            assert "a summary" in prompt.en
        finally:
            mspire.fetch_ms_meta = old_fetch

    asyncio.run(scenario())


def test_mspire_passes_query_and_closes_client(monkeypatch) -> None:
    clients = []

    class FakePage:
        title = "Result"

        async def exists(self):
            return True

        @property
        async def summary(self):
            return "Summary"

    class FakeWikipedia:
        def __init__(self, **_kwargs):
            self.search_calls = []
            self.closed = False
            clients.append(self)

        async def search(self, **kwargs):
            self.search_calls.append(kwargs)
            return SimpleNamespace(pages={"Result": FakePage()})

        def page(self, _title):
            return FakePage()

        async def close(self):
            self.closed = True

    async def scenario() -> None:
        monkeypatch.setattr(mspire, "ProxiedAsyncWikipedia", FakeWikipedia)
        fsc = FullSocketsContainer()
        fsc.maica_settings.basic.target_lang = "en"
        fsc.maica_settings.temp.mspire.type = "precise_page"
        fsc.maica_settings.temp.mspire.title = ["search term"]
        title, summary = await mspire.fetch_ms_meta(fsc)

        assert (title, summary) == ("Result", "Summary")
        assert clients[0].search_calls == [
            {"query": "search term", "ns": mspire.Namespace.MAIN, "limit": 1}
        ]
        assert clients[0].closed

    asyncio.run(scenario())


def test_mpostal_forms_a_letter_without_calling_a_regex_object() -> None:
    class FakeConnection:
        async def make_completion(self, **_kwargs):
            return SimpleNamespace(output_text='{"is_poem":false,"confidence":0.9}')

    async def scenario() -> None:
        fsc = FullSocketsContainer()
        fsc.mfocus_conn = FakeConnection()
        fsc.maica_settings.basic.target_lang = "en"
        fsc.maica_settings.temp.mpostal.content = "  Dear Monika,\n  Hello.  "
        prompt = await make_postmail(fsc)
        assert "Dear Monika" in prompt.en
        assert "Your reply should be a letter" in prompt.en

    asyncio.run(scenario())


def test_post_processing_awaits_emotion_correction_before_indexing() -> None:
    async def scenario() -> None:
        fsc = FullSocketsContainer()
        fsc.maica_settings.basic.target_lang = "en"
        assert await post_proc("[unknown]Hello", fsc) == "[smile]Hello"

    asyncio.run(scenario())


def test_realtime_splitter_uses_byte_limit_as_a_byte_limit() -> None:
    splitter = TalkSplitV2(split_limit=180)
    splitter.add_part("你" * 100)
    first = splitter.split_present_sentence()
    assert first
    assert len(first.encode("utf-8")) <= 200
    assert splitter.sentence_present
