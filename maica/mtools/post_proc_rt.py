# -*- coding: utf-8 -*-

import asyncio
import re
from typing import *
from .post_proc import post_proc
from maica.maica_utils import *


class TalkSplitPlain():
    """For unchanged output."""
    def __init__(self, split_limit=-1):
        self.reset()
        self._split_limit = split_limit

    def reset(self):
        self.sentence_present = ''

    def add_part(self, part):
        self.sentence_present += part

    def split_present_sentence(self):
        sentence_present, self.sentence_present = self.sentence_present, ''
        return sentence_present
    
    def announce_stop(self):
        return [self.sentence_present] if self.sentence_present else []

class TalkSplitV2(object):
    """
    Incrementally split streamed Unicode text at semantic boundaries.

    The class body intentionally uses Python 2.7-compatible syntax so it can
    be reused in a UTF-8 Python 2 module. Python 2 callers must pass ``unicode``
    chunks. The surrounding ``post_proc_rt`` module remains Python 3-only.
    """

    _PRIORITY_FALLBACK = 0
    _PRIORITY_LOW = 1
    _PRIORITY_MEDIUM = 2
    _PRIORITY_HIGH = 3
    _PRIORITY_EXHIGH = 4

    _PUNCTUATION_PRIORITY = {
        u"-": _PRIORITY_FALLBACK,
        u"‐": _PRIORITY_FALLBACK,
        u"‑": _PRIORITY_FALLBACK,
        u"‒": _PRIORITY_FALLBACK,
        u"–": _PRIORITY_FALLBACK,
        u"—": _PRIORITY_FALLBACK,
        u"−": _PRIORITY_FALLBACK,
        u"﹣": _PRIORITY_FALLBACK,
        u"－": _PRIORITY_FALLBACK,
        u",": _PRIORITY_LOW,
        u"，": _PRIORITY_LOW,
        u";": _PRIORITY_MEDIUM,
        u"；": _PRIORITY_MEDIUM,
        u".": _PRIORITY_HIGH,
        u"。": _PRIORITY_HIGH,
        u"?": _PRIORITY_HIGH,
        u"？": _PRIORITY_HIGH,
        u"…": _PRIORITY_HIGH,
        u"!": _PRIORITY_EXHIGH,
        u"！": _PRIORITY_EXHIGH,
        u"~": _PRIORITY_EXHIGH,
        u"～": _PRIORITY_EXHIGH,
        u"〜": _PRIORITY_EXHIGH,
    }
    _PUNCTUATION_PATTERN = re.compile(u'[.。!！?？；;，,—~～〜…\\-‐‑‒–−﹣－]+')
    _LEFT_BRACKET_PATTERN = re.compile(u'[(（\\[]')
    _RIGHT_BRACKET_PATTERN = re.compile(u'[)）\\]]')

    _TILDE_CONNECTORS = frozenset((u"~", u"～", u"〜"))
    _HYPHEN_CONNECTORS = frozenset((u"-", u"‐", u"‑", u"‒", u"–", u"−", u"﹣", u"－"))
    _COMMON_ABBREVIATIONS = frozenset(
        (
            u"co", u"corp", u"dr", u"etc", u"fig", u"inc", u"jr", u"ltd", u"mr",
            u"mrs", u"ms", u"no", u"prof", u"sr", u"st", u"vs",
        )
    )

    def __init__(self, split_limit=180):
        self.reset()
        self._split_limit = split_limit

    def reset(self):
        self.sentence_present = u''

    @staticmethod
    def _is_word_char(char):
        return bool(char) and (char.isalnum() or char == u"_")

    @staticmethod
    def _is_ascii_word_char(char):
        return bool(char) and (
            u"0" <= char <= u"9"
            or u"A" <= char <= u"Z"
            or u"a" <= char <= u"z"
            or char == u"_"
        )

    @staticmethod
    def _nearest_nonspace(text, index, direction):
        while 0 <= index < len(text):
            if not text[index].isspace():
                return text[index]
            index += direction
        return u""

    @staticmethod
    def _get_utf8_byte_lengths(text):
        """Return UTF-8 prefix lengths without relying on Python 3 string semantics."""
        byte_lengths = [0]
        byte_count = 0
        index = 0
        while index < len(text):
            codepoint = ord(text[index])
            if 0xD800 <= codepoint <= 0xDBFF and index + 1 < len(text):
                next_codepoint = ord(text[index + 1])
                if 0xDC00 <= next_codepoint <= 0xDFFF:
                    byte_count += 4
                    # Do not expose a cut point between a surrogate pair.
                    byte_lengths.append(byte_count)
                    byte_lengths.append(byte_count)
                    index += 2
                    continue
            if codepoint <= 0x7F:
                byte_count += 1
            elif codepoint <= 0x7FF:
                byte_count += 2
            elif codepoint <= 0xFFFF:
                byte_count += 3
            else:
                byte_count += 4
            byte_lengths.append(byte_count)
            index += 1
        return byte_lengths

    @classmethod
    def _ascii_token_before(cls, text, index):
        start = index
        while start and cls._is_ascii_word_char(text[start - 1]):
            start -= 1
        return text[start:index].lower()

    @classmethod
    def _ascii_token_after(cls, text, index):
        end = index
        while end < len(text) and cls._is_ascii_word_char(text[end]):
            end += 1
        return text[index:end]

    @classmethod
    def _dot_is_connector(cls, text, index):
        left = text[index - 1] if index else u""
        right = text[index + 1] if index + 1 < len(text) else u""

        # A trailing dot is ambiguous until the next streaming chunk arrives.
        if not right:
            return True
        if left.isdigit() and right.isdigit():
            return True
        if right.isdigit() and (not left or left.isspace() or left in u"+-−"):
            return True
        if cls._is_ascii_word_char(right) and (not left or left.isspace()):
            return True

        token = cls._ascii_token_before(text, index)
        following_token = cls._ascii_token_after(text, index + 1)
        if cls._is_ascii_word_char(left) and cls._is_ascii_word_char(right):
            # Lowercase token pairs are typical domains/file names. A pair of
            # single uppercase letters is the common ``U.S.`` abbreviation.
            if token.islower() and following_token.islower():
                return True
            if len(token) == 1 and len(following_token) == 1 and left.isupper() and right.isupper():
                return True
        if token in cls._COMMON_ABBREVIATIONS:
            return True
        if index >= 2 and text[index - 2] == u"." and cls._is_ascii_word_char(left):
            return True
        if len(token) == 1 and u"A" <= text[index - 1] <= u"Z":
            return True
        return False

    @classmethod
    def _run_is_connector(cls, text, start, end):
        content = text[start:end]
        left = text[start - 1] if start else u""
        right = text[end] if end < len(text) else u""
        left_nonspace = cls._nearest_nonspace(text, start - 1, -1)
        right_nonspace = cls._nearest_nonspace(text, end, 1)

        if content == u".":
            return cls._dot_is_connector(text, start)
        if all(char == u"." for char in content):
            return left_nonspace.isdigit() and right_nonspace.isdigit()

        if all(char in cls._TILDE_CONNECTORS for char in content):
            if not right:
                return True
            if left_nonspace.isdigit() and right_nonspace.isdigit():
                return True
            if cls._is_word_char(left) and cls._is_word_char(right):
                return True
            if (not left or left.isspace()) and (cls._is_word_char(right) or right in u"/\\"):
                return True
            return False

        if all(char in cls._HYPHEN_CONNECTORS for char in content):
            if not right:
                return True
            if left_nonspace.isdigit() and right_nonspace.isdigit():
                return True
            if cls._is_word_char(left) and cls._is_word_char(right):
                return True
            if right_nonspace.isdigit() and (not left or left.isspace()):
                return True
            if len(content) > 1 and (not left or left.isspace()) and cls._is_word_char(right):
                return True
            return False

        # Also protect compact negative decimals such as ``-.5``.
        if content.endswith(u".") and right.isdigit():
            prefix = content[:-1]
            if prefix and all(char in cls._HYPHEN_CONNECTORS for char in prefix):
                return not left or left.isspace()
        return False

    @classmethod
    def _get_break_priority(cls, text, match):
        if cls._run_is_connector(text, match.start(), match.end()):
            return None
        return max(cls._PUNCTUATION_PRIORITY[char] for char in match.group())

    def add_part(self, part):
        """Append a Unicode streaming chunk."""
        self.sentence_present += part

    def split_present_sentence(self):
        """Return the next safe segment, or ``None`` when more context is needed."""
        byte_lengths = self._get_utf8_byte_lengths(self.sentence_present)
        length_present = byte_lengths[-1]

        if length_present <= min(60, self._split_limit):
            return None

        candidates = []
        for match in self._PUNCTUATION_PATTERN.finditer(self.sentence_present):
            priority = self._get_break_priority(self.sentence_present, match)
            if priority is not None:
                candidates.append((match.end(), priority))

        left_brackets = [match.end() for match in self._LEFT_BRACKET_PATTERN.finditer(self.sentence_present)]
        right_brackets = [match.end() for match in self._RIGHT_BRACKET_PATTERN.finditer(self.sentence_present)]

        def check_sanity_pos(pos):
            """Checks brackets' consistency."""
            lc = rc = 0
            for bracket_pos in left_brackets:
                if bracket_pos > pos:
                    break
                lc += 1
            for bracket_pos in right_brackets:
                if bracket_pos > pos:
                    break
                rc += 1
            return lc == rc

        def split_at_pos(pos):
            sce = self.sentence_present[0:pos]
            self.sentence_present = self.sentence_present[pos:]
            return sce or None

        def find_candidate(min_priority, min_length, max_length, check_brackets=True):
            for pos, priority in reversed(candidates):
                if priority < min_priority:
                    continue
                if min_length <= byte_lengths[pos] <= max_length:
                    if not check_brackets or check_sanity_pos(pos):
                        return pos
            return None

        pos = find_candidate(self._PRIORITY_EXHIGH, 30, self._split_limit)
        if pos is not None:
            return split_at_pos(pos)
        if length_present <= self._split_limit - 35:
            return None

        pos = find_candidate(self._PRIORITY_HIGH, 30, self._split_limit)
        if pos is not None:
            return split_at_pos(pos)
        if length_present <= self._split_limit - 25:
            return None

        pos = find_candidate(self._PRIORITY_MEDIUM, 20, self._split_limit)
        if pos is not None:
            return split_at_pos(pos)
        if length_present <= self._split_limit - 15:
            return None

        pos = find_candidate(self._PRIORITY_LOW, 10, self._split_limit)
        if pos is not None:
            return split_at_pos(pos)
        if length_present <= self._split_limit - 5:
            return None

        pos = find_candidate(self._PRIORITY_FALLBACK, 3, self._split_limit)
        if pos is not None:
            return split_at_pos(pos)
        if length_present <= self._split_limit:
            return None

        hard_limit = self._split_limit + 20
        pos = find_candidate(self._PRIORITY_FALLBACK, 3, hard_limit, check_brackets=False)
        if pos is not None:
            return split_at_pos(pos)
        if length_present <= hard_limit:
            return None

        char_position = len(self.sentence_present)
        for index, byte_length in enumerate(byte_lengths[1:], start=1):
            if byte_length > hard_limit:
                char_position = max(1, index - 1)
                break

        minimum_space_length = max(3, self._split_limit - 20)
        for index in range(char_position, 0, -1):
            if self.sentence_present[index - 1].isspace() and byte_lengths[index] >= minimum_space_length:
                char_position = index
                break
        return split_at_pos(char_position)

    def announce_stop(self):
        """Exhausts remaining buffer."""
        sce_list = []
        while True:
            res = self.split_present_sentence()
            if not res:
                break
            sce_list.append(res)
        if self.sentence_present:
            sce_list.append(self.sentence_present)
        self.reset()
        return sce_list


class PPRTProcessor():
    """Post proc realtime processor."""
    def __init__(self, fsc: FullSocketsContainer, pprt: Union[bool, WsQueryConfig.PprtConfig] = True):
        if pprt is True:
            pprt = WsQueryConfig.PprtConfig()
        elif pprt is False:
            pprt = WsQueryConfig.PprtConfig(
                split_limit=-1,
                correct_malform=False,
            )
        self._pprt = pprt

        self.fsc = fsc

        if self._pprt.split_limit > 0:
            self._buffer = TalkSplitV2(self._pprt.split_limit)
        else:
            self._pprt.yield_interval = [1]
            self._buffer = TalkSplitPlain()

        self._add_counter = 0
        self._yield_counter = 0

    def _add_chunk(self, chunk: str):
        self._buffer.add_part(chunk)
        self._add_counter += 1

    def _try_yield(self):
        return self._buffer.split_present_sentence()

    async def stack_and_split(self, chunk: str) -> Optional[str]:
        self._add_chunk(chunk)
        if self._add_counter >= sum(self._pprt.yield_interval[:self._yield_counter + 1]):
            split = self._buffer.split_present_sentence()
            if split:
                return await self._correct_malform(split)
            else:
                self._yield_counter += 1
                return None
            
    async def _correct_malform(self, sentence: str) -> str:
        if self._pprt.correct_malform:
            return await post_proc(sentence, self.fsc)
        else:
            return sentence

    async def exhaust_and_split(self, chunk: str='') -> list[str]:
        if chunk:
            self._add_chunk(chunk)
        splits = self._buffer.announce_stop()
        new_splits = []
        for split in splits:
            new_splits.append(await self._correct_malform(split))
        return new_splits
    
if __name__ == "__main__":
    fsc = FullSocketsContainer()
    fsc.maica_settings.basic.target_lang = "en"
    pprtp = PPRTProcessor(fsc)
    # text = "[微笑]我觉得...年轻人喜欢喝奶茶是因为它好喝吧? [微笑]奶茶口感细腻, 甜度可调, 还可以加各种配料.[开心]很多人也把喝奶茶作为一种享受生活的方式. [微笑]当然, 奶茶也有它的营养价值. [微笑]比如牛奶富含钙和蛋白质, 茶叶则含有茶多酚和咖啡因. [开心]所以适量饮用奶茶对身体也是有好处的."
    text = "[smile]Hey [player], have you ever thought about science as a whole? [think]Like, science is this really big thing that's always advancing and changing. It's like a collection of knowledge that we're always adding to. [grin]It's kind of like a library, but instead of books, it's facts about the world. And just like a library, it's always growing. New books get added all the time, and sometimes old ones get taken off the shelf if they're not accurate anymore. [smile]It's pretty cool to think about how much we've learned over the years. [awkward]But there's still so much we don't know! The universe is so vast, there has to be way more than what we've discovered so far. [grin]That's what I love about science though, it's always evolving. There's never a dull moment!"

    for c in text:
        sce = asyncio.run(pprtp.stack_and_split(c))
        if sce:
            print(sce)
    sces = asyncio.run(pprtp.exhaust_and_split())
    for sce in sces:
        print(sce)
