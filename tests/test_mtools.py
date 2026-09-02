import asyncio
from types import SimpleNamespace

import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from maica.maica_utils import DatabaseUtils, FullSocketsContainer, SqlBaseData
from maica.mtools import mspire
from maica.mtools.mpostal import make_postmail
from maica.mtools.post_proc import post_proc
from maica.mtools.post_proc_rt import TalkSplitV2


def test_mspire_cache_keeps_the_prompt_used_to_generate_hash() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        old_factory = DatabaseUtils.SessionData
        DatabaseUtils.SessionData = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SqlBaseData.metadata.create_all)

            fsc = FullSocketsContainer()
            fsc.maica_settings.verification.user_id = 7
            prompt = "prompt used for training"
            cached = await mspire.ms_from_cache(prompt, fsc)

            assert cached.prompt == prompt
            assert cached.result is None

            cached.result = "generated answer"
            await mspire.ms_to_cache(cached, fsc)

            async with DatabaseUtils.SessionData() as dbs:
                row = await dbs.scalar(sqlalchemy.select(mspire.SqlMsCache))
                assert row is not None
                assert row.hash == cached.hash
                assert row.prompt == prompt
                assert row.content == "generated answer"
        finally:
            DatabaseUtils.SessionData = old_factory
            await engine.dispose()

    asyncio.run(scenario())


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


def test_mspire_precise_page_bypasses_search_and_closes_client(monkeypatch) -> None:
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
            self.page_calls = []
            self.closed = False
            clients.append(self)

        async def search(self, **kwargs):
            self.search_calls.append(kwargs)
            return SimpleNamespace(pages={"Result": FakePage()})

        def page(self, title):
            self.page_calls.append(title)
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

        assert (title, summary) == ("search term", "Summary")
        assert clients[0].search_calls == []
        assert clients[0].page_calls == ["search term"]
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


def test_realtime_splitter_keeps_astral_characters_intact_at_hard_limit() -> None:
    text = "a" * 198 + "😀" + "b" * 10
    splitter = TalkSplitV2(split_limit=180)
    splitter.add_part(text)
    first = splitter.split_present_sentence()
    assert first == "a" * 198
    assert len(first.encode("utf-8")) <= 200
    assert "".join([first] + splitter.announce_stop()) == text


def test_realtime_splitter_distinguishes_tilde_tone_from_ranges() -> None:
    range_splitter = TalkSplitV2(split_limit=80)
    range_splitter.add_part("a" * 30 + "1~2" + "b" * 30)
    assert range_splitter.split_present_sentence() is None

    spaced_range_splitter = TalkSplitV2(split_limit=80)
    spaced_range_splitter.add_part("a" * 30 + "1 ～ 2" + "b" * 30)
    assert spaced_range_splitter.split_present_sentence() is None

    tone_splitter = TalkSplitV2(split_limit=80)
    expected = "a" * 30 + "hello~"
    tone_splitter.add_part(expected + " " + "b" * 30)
    assert tone_splitter.split_present_sentence() == expected


def test_realtime_splitter_waits_for_tilde_and_hyphen_right_context() -> None:
    for left, right in (("1~", "2"), ("well-", "known")):
        splitter = TalkSplitV2(split_limit=80)
        splitter.add_part("a" * 70 + left)
        assert splitter.split_present_sentence() is None
        splitter.add_part(right + "b" * 5)
        assert splitter.split_present_sentence() is None


def test_realtime_splitter_does_not_split_at_word_hyphens_or_numeric_dashes() -> None:
    for connector in ("well-known", "1-2", "1 - 2", "1–2", "１－２", "全﹣角"):
        splitter = TalkSplitV2(split_limit=80)
        splitter.add_part("a" * 70 + connector + "b" * 10)
        assert splitter.split_present_sentence() is None

    dash_splitter = TalkSplitV2(split_limit=80)
    expected = "a" * 70 + "word—"
    dash_splitter.add_part(expected + "word" + "b" * 20)
    assert dash_splitter.split_present_sentence() == expected


def test_realtime_splitter_protects_decimal_domain_and_abbreviation_dots() -> None:
    for connector in ("3.14", ".5", ".env", "example.com", "Dr. Smith", "e.g. value"):
        splitter = TalkSplitV2(split_limit=80)
        splitter.add_part("a" * 30 + " " + connector + "b" * 30)
        assert splitter.split_present_sentence() is None

    sentence_splitter = TalkSplitV2(split_limit=80)
    expected = "a" * 30 + "Hi."
    sentence_splitter.add_part(expected + " Next" + "b" * 25)
    assert sentence_splitter.split_present_sentence() == expected

    no_space_sentence_splitter = TalkSplitV2(split_limit=80)
    expected = "a" * 30 + "Hello."
    no_space_sentence_splitter.add_part(expected + "World" + "b" * 25)
    assert no_space_sentence_splitter.split_present_sentence() == expected


def test_realtime_splitter_waits_for_context_after_a_streaming_dot() -> None:
    decimal_splitter = TalkSplitV2(split_limit=80)
    decimal_splitter.add_part("a" * 70 + "12.")
    assert decimal_splitter.split_present_sentence() is None
    decimal_splitter.add_part("34" + "b" * 5)
    assert decimal_splitter.split_present_sentence() is None

    sentence_splitter = TalkSplitV2(split_limit=80)
    sentence_splitter.add_part("a" * 70 + "END.")
    assert sentence_splitter.split_present_sentence() is None
    sentence_splitter.add_part(" next")
    assert sentence_splitter.split_present_sentence() == "a" * 70 + "END."


def test_realtime_splitter_preserves_single_character_tail() -> None:
    for text in ("a", "好"):
        splitter = TalkSplitV2()
        splitter.add_part(text)
        assert splitter.announce_stop() == [text]


def test_realtime_splitter_preserves_space_before_final_tail() -> None:
    text = "a" * 30 + "! " + "b" * 30
    splitter = TalkSplitV2(split_limit=80)
    splitter.add_part(text)
    first = splitter.split_present_sentence()
    assert first == "a" * 30 + "!"
    assert "".join([first] + splitter.announce_stop()) == text


def test_realtime_splitter_preserves_whitespace_only_input() -> None:
    for text in (" ", " " * 100):
        splitter = TalkSplitV2(split_limit=40)
        splitter.add_part(text)
        assert "".join(splitter.announce_stop()) == text


def test_realtime_splitter_recognizes_unicode_ellipsis() -> None:
    splitter = TalkSplitV2(split_limit=80)
    expected = "a" * 30 + "……"
    splitter.add_part(expected + "b" * 30)
    assert splitter.split_present_sentence() == expected


def test_realtime_splitter_preserves_backend_priority_thresholds() -> None:
    cases = (
        ("!", "!", 60),
        (".", ".", 145),
        (";", ";", 155),
        (",", ",", 165),
        (" - ", " -", 175),
    )
    for punctuation, expected_punctuation, inactive_length in cases:
        prefix = "a" * 30
        splitter = TalkSplitV2(split_limit=180)
        suffix_length = inactive_length - len(prefix + punctuation)
        suffix = "B" + "b" * (suffix_length - 1)
        splitter.add_part(prefix + punctuation + suffix)
        assert splitter.split_present_sentence() is None
        splitter.add_part("b")
        assert splitter.split_present_sentence() == prefix + expected_punctuation
