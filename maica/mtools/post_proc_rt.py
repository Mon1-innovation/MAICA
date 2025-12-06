import asyncio
import re
from typeguard import check_type
from typing import *
from .post_proc import post_proc
from maica.maica_utils import *

pattern_all_punc = re.compile(r'[.。!！?？；;，,—~-]+')
pattern_uncrit_punc = re.compile(r'[.。!！?？；;，,~]+')
pattern_subcrit_punc = re.compile(r'[.。!！?？；;~]+')
pattern_crit_punc = re.compile(r'[.。!！?？~]+')
pattern_excrit_punc = re.compile(r'[!！~]+')
pattern_numeric = re.compile(r'[0-9]')
pattern_content = re.compile(r'[一-龥A-Za-z]')
pattern_semileft = re.compile(r'[(（\[]')
pattern_semiright = re.compile(r'[)）\]]')

list_uncrit_punc = list('.。!！?？；;，,~')
list_subcrit_punc = list('.。!！?？；;~')
list_crit_punc = list('.。!！?？~')
list_excrit_puc = list('!！~')

class TalkSplitV2():
    """Transplanted from py2 fe. Terribly written."""
    def __init__(self, split_limit=180):
        self.reset()
        self._split_limit = split_limit

    def reset(self):
        self.sentence_present = ''

    def is_decimal(self, five_related_cells):
        """Not just decimal. Return True if dot shouldn't be considered as a period, vice versa."""
        def num_amount(text):
            i = 0
            for c in text:
                if c.isdigit():
                    i += 1
            return i

        if five_related_cells[2] == '.':
            cnts = len(pattern_content.findall(five_related_cells))
            if (
                # If numbers in both previous and after sections, suggesting it a decimal dot
                (num_amount(five_related_cells[0:2]) and num_amount(five_related_cells[3:5]))
                # If section has too little content, and dot is not a period after a huge number
                or (cnts<=1 and num_amount(five_related_cells[0:2]) != 2)
                # If dot belongs to an abbreviation
                or five_related_cells[1].isupper()
            ):
                return True
        return False
    
    @staticmethod
    def insert_string(original_str, insert_str, index):
        """Simple."""
        return original_str[:index] + insert_str + original_str[index:]

    def add_part(self, part):
        """Simple too."""
        self.sentence_present += part

    def split_present_sentence(self):
        """Main function."""
        apc=[]; upc=[]; spc=[]; cpc=[]; epc=[]; slc=[]; src=[]
        length_present = len(self.sentence_present.encode())

        if length_present <= 60:
            return None
    
        def get_pos_len(pos):
            """Get length of context before position."""
            sce = self.sentence_present[0:pos]
            return len(sce.encode())
        
        def check_sanity_pos(pos):
            """Checks brackets' consistency."""
            lc = rc = 0
            if slc:
                for match in slc:
                    if match.end() > pos:
                        break
                    else:
                        lc += 1
            if src:
                for match in src:
                    if match.end() > pos:
                        break
                    else:
                        rc += 1

            return True if lc <= rc else False
            
        def split_at_pos(pos):
            """Just split."""
            sce = self.sentence_present[0:pos]
            self.sentence_present = self.sentence_present[pos:]
            if len(sce) > 1 and not sce.isspace():
                return sce.lstrip()
            else:
                return None

        matches = pattern_all_punc.finditer(self.sentence_present)
        for match in matches:
            pos = match.end(); content = match.group()
            apc.append(match)
            if len(content) > 1 or not self.is_decimal(('   ' + self.sentence_present + ' ')[pos:pos+5]):
                if has_words_in(content, *list_uncrit_punc):
                    upc.append(match)
                    if has_words_in(content, *list_subcrit_punc):
                        spc.append(match)
                        if has_words_in(content, *list_crit_punc):
                            cpc.append(match)
                            if has_words_in(content, *list_excrit_puc):
                                epc.append(match)

        slc = list(pattern_semileft.finditer(self.sentence_present))
        src = list(pattern_semiright.finditer(self.sentence_present))

        # if length_present <= 60:
        #     return None
        if epc:
            for match in reversed(epc):
                if 30 <= get_pos_len(match.end()) <= self._split_limit and check_sanity_pos(match.end()):
                    return split_at_pos(match.end())
        # No epc or none fits
        if length_present <= self._split_limit - 35:
            return None
        if cpc:
            for match in reversed(cpc):
                if 30 <= get_pos_len(match.end()) <= self._split_limit and check_sanity_pos(match.end()):
                    return split_at_pos(match.end())
        # No cpc or still none fits
        if length_present <= self._split_limit - 25:
            return None
        if spc:
            for match in reversed(spc):
                if 20 <= get_pos_len(match.end()) <= self._split_limit and check_sanity_pos(match.end()):
                    return split_at_pos(match.end())
        # No spc or still none fits
        if length_present <= self._split_limit - 15:
            return None
        if upc:
            for match in reversed(upc):
                if 10 <= get_pos_len(match.end()) <= self._split_limit and check_sanity_pos(match.end()):
                    return split_at_pos(match.end())
        # No upc or still none fits
        if length_present <= self._split_limit - 5:
            return None
        if apc:
            for match in reversed(apc):
                if 3 <= get_pos_len(match.end()) <= self._split_limit and check_sanity_pos(match.end()):
                    return split_at_pos(match.end())
        # Falling back -- sanity given up
            if length_present <= self._split_limit:
                return None
            for match in reversed(apc):
                if 3 <= get_pos_len(match.end()) <= self._split_limit + 20:
                    return split_at_pos(match.end())
        return split_at_pos(get_pos_len(self._split_limit + 20))
    
    def announce_stop(self):
        """Exhausts remaining buffer."""
        sce_list = []
        res = True
        while res:
            res = self.split_present_sentence()
            if res:
                sce_list.append(res)
        if self.sentence_present and len(self.sentence_present) > 1 and not self.sentence_present.isspace():
            sce_list.append(self.sentence_present.lstrip())
        self.reset()
        return sce_list

    # def add_pauses(self, strin):
    #     """Add pauses to punctuations. Suppose we aren't using this in backend."""
    #     if not isinstance(strin, str):
    #         raise TypeError("Input should be a string, get {}".format(type(strin)))
        
    #     def get_pre_i_space(ele, list):
    #         pre_index = list.index(ele) - 1
    #         pre_pos = list[pre_index][3] if pre_index >= 0 else 0
    #         return ele[3] - pre_pos

    #     iupc=[]; icpc=[]; iepc=[]
        
    #     matches = pattern_all_punc.finditer(strin)
    #     lmatch = None; i = 0 
    #     # This is a iterator but we need a list
    #     matches = list(matches)
    #     for match in matches:
    #         # No pause needed for last punc
    #         i += 1
    #         if i == len(matches):
    #             break
    #         pos = match.end(); content = match.group()
    #         if not lmatch:
    #             preseq = strin[:match.start()]
    #         else:
    #             preseq = strin[lmatch.end():match.start()]
    #         prelen = len(preseq.encode('utf-8'))
    #         alllen = len(strin[:match.start()].encode('utf-8'))
    #         lmatch = match
    #         match_tuple_b = (pos, content, prelen, alllen)
    #         # print(('   ' + strin + ' ')[pos:pos+5])
    #         if len(content) > 1 or not self.is_decimal(('   ' + strin + ' ')[pos:pos+5]):
    #             if has_words_in(content, list_excrit_puc):
    #                 iepc.append(match_tuple_b)
    #             elif has_words_in(content, list_crit_punc):
    #                 icpc.append(match_tuple_b)
    #             elif has_words_in(content, list_uncrit_punc):
    #                 iupc.append(match_tuple_b)

    #     pending_insert = []

    #     for mb in iupc:
    #         if prelen > 80:
    #             pending_insert.append(('{w=0.3}', mb[0]))

    #     for mb in icpc:
    #         if len(mb[1]) > 1:
    #             # ellipsis?
    #             if get_pre_i_space(mb, icpc) > 30:
    #                 pending_insert.append(('{w=0.5}', mb[0]))
    #         elif get_pre_i_space(mb, icpc) > 45:
    #             pending_insert.append(('{w=0.3}', mb[0]))

    #     for mb in iepc:
    #         if prelen > 45:
    #             pending_insert.append(('{w=0.2}', mb[0]))

    #     for tup in pending_insert[::-1]:
    #         strin = self.insert_string(strin, *tup)
                
    #     return strin

class PPRTProcessor():
    """Post proc realtime processor."""
    @Decos.report_limit_warning
    def __init__(self, pprt: Union[dict, True]=True, target_lang: Literal['zh', 'en']='zh', mnerve_conn: Optional[AiConnectionManager]=None):
        self._pprt = {
            "yield_interval": [40, 20, 10, 5, 3, 1],
            "split_limit": 180,
            "correct_malform": True,
        }
        if isinstance(pprt, dict):
            check_type(pprt.get('yield_interval'), List[int])
            check_type(pprt.get('split_limit'), int)
            self._pprt.update(pprt)

        self._target_lang = target_lang
        self._mnerve_conn = mnerve_conn
        self._buffer = TalkSplitV2(self._pprt.get('split_limit'))

        self._add_counter = 0
        self._yield_counter = 0

    def _add_chunk(self, chunk: str):
        self._buffer.add_part(chunk)
        self._add_counter += 1

    def _try_yield(self):
        return self._buffer.split_present_sentence()
    
    async def store_and_split(self, chunk: str) -> Optional[str]:
        self._add_chunk(chunk)
        if self._add_counter >= sum(self._pprt['yield_interval'][:self._yield_counter + 1]):
            split = self._buffer.split_present_sentence()
            if split:
                if self._pprt.get('correct_malform'):
                    return await self._correct_malform(split)
                else:
                    return split
            else:
                self._yield_counter += 1
                return None
            
    async def _correct_malform(self, sentence: str) -> str:
        return await post_proc(sentence, self._target_lang, self._mnerve_conn)

    async def exaust_and_split(self) -> list[str]:
        splits = self._buffer.announce_stop()
        new_splits = []
        for split in splits:
            if self._pprt.get('correct_malform'):
                new_splits.append(await self._correct_malform(split))
            else:
                new_splits.append(split)
        return new_splits
    
if __name__ == "__main__":
    pprtp = PPRTProcessor()
    text = "[微笑]我觉得...年轻人喜欢喝奶茶是因为它好喝吧? [微笑]奶茶口感细腻, 甜度可调, 还可以加各种配料.[开心]很多人也把喝奶茶作为一种享受生活的方式. [微笑]当然, 奶茶也有它的营养价值. [微笑]比如牛奶富含钙和蛋白质, 茶叶则含有茶多酚和咖啡因. [开心]所以适量饮用奶茶对身体也是有好处的."
    for c in text:
        sce = asyncio.run(pprtp.store_and_split(c))
        if sce:
            print(sce)
    sces = asyncio.run(pprtp.exaust_and_split())
    for sce in sces:
        print(sce)