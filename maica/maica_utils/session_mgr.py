"""
Import layer 4.1
This module is for v2 session management, applied for DAA4.
"""
import time
import orjson
from typing import *
from dataclasses import dataclass, field
from .maica_utils import *
from .fsc_late import *

@dataclass
class MaicaSessionItem():
    role: str = ''
    content: str = ''
    # There might be other things here, like tool_call_id
    context: dict = field(default_factory=lambda: {})
        # "target_lang": "zh",
        # "strict_conv": True,
        # "player_name": "[player]",
        # "nsfw_acceptive": True,
        # "known_info": "",
        # "image_urls": [],
        # Extra kvs are valid here, expect them in procedures
    timestamp = time.time()

    def load(self, item: dict):
        assert isinstance(item, dict), f"Session item can only load from dict, {type(item)} {str(item)} found"
        for k, v in item.items():
            setattr(self, k, v)

    def json(self) -> dict:
        return vars(self)
    
    def utilize(self, text_only=False) -> dict:
        d = {"role": self.role}
        content = self.content

        if is_mcore_vl() and not text_only:
            image_urls = self.context.get(image_urls)
            if image_urls:
                content = [
                    {"type": "text", "text": self.content}
                ]
                for url in image_urls:
                    content.append({"type": "image_url", "image_url": {"url": url}})

        d["content"] = content
        return d

class MaicaSession(list):
    """
    This is designed to bind with WsCoroutine.
    """
    session_id: Optional[int] = None
    session_num: Optional[int] = None
    fsc: Optional[FullSocketsContainer] = None

    def __init__(self, *args, **kwargs):
        # Initialize the base list class
        super().__init__(*args, **kwargs)

        self.default_context: dict = {
            "target_lang": "zh",
            "strict_conv": True,
            "player_name": "[player]",
            "nsfw_acceptive": True,
            "known_info": "",
            "image_urls": [],
        }

    # We override append to automatically manage context
    def append(self, object):
        if isinstance(object, MaicaSessionItem):
            object.context = object.context | self.default_context
        return super().append(object)
    
    # Well we have to use insert sometimes
    # We don't patch extend since it's not necessary
    def insert(self, index, object):
        if isinstance(object, MaicaSessionItem):
            object.context = object.context | self.default_context
        return super().insert(index, object)

    def _load(self, item: list, ex_context: Optional[dict] = None):
        assert isinstance(item, list), f"Session can only load from list, {type(item)} {str(item)} found"
        self.clear()
        for i in item:
            si = MaicaSessionItem(); si.load(i)
            if ex_context:
                for k, v in ex_context.items():
                    si.context[k] = v
            self.append(si)

    def load(self, item: Union[list, str]):
        """This also deals with v1 compatibility."""
        match type(item).__name__:
            case "list":
                list_item = item
            case "str":
                try:
                    list_item = orjson.loads(item)
                except Exception as e:
                    try:
                        list_item = orjson.loads(f"[{item}]")
                    except Exception as e:
                        raise MaicaInputWarning(f"Loading {item} is not json or flatterned-json: {str(e)}")
                    
        first_item = list_item[0]
        maica_assert(isinstance(first_item, dict) and first_item.get("role") and first_item.get("content"), full_info=f"Loaded {list_item} is not a V2 or V1 session")

        if len(first_item) <= 2:
            is_v1 = True
        else: is_v1 = False

        self._load(list_item, ex_context={"from_v1": True} if is_v1 else None)

    def sanitize(self):
        # Make sure system is #0
        if not self[0].role == "system":
            self.insert(0, MaicaSessionItem("system"))

        # Likely not necessary but who knows
        if len(self) > 1:
            hard_fixed = []
            while self[1].role != 'user':
                hard_fixed.append(self.pop(1))
            while self[-1].role != 'assistant':
                hard_fixed.append(self.pop(-1))
            if hard_fixed:
                sync_messenger(info=f"Hard fix of session {self.fsc.maica_settings.verification.user_id if self.fsc else 'UNKNOWN'}:{self.session_num} applied, popped {len(hard_fixed)} items: {str(hard_fixed)}", type=MsgType.ERROR if self.session_num != -1 else MsgType.WARN)

    def _prepare_context(self):
        def _basic_gen_system(target_lang, strict_conv):
            if target_lang == 'zh':
                if strict_conv:
                    prompt = G.A.PROMPT_ZC
                else:
                    prompt = G.A.PROMPT_ZW
            else:
                if strict_conv:
                    prompt = G.A.PROMPT_EC
                else:
                    prompt = G.A.PROMPT_EW
            return prompt
        
        # First sanitize
        self.sanitize()
        assert len(self) > 1, "No query could be utilized"

        # Then acquire context
        curr_context = self[-1].context

        # Then generate system prompt from context
        prompt = _basic_gen_system(curr_context['target_lang'], curr_context['strict_conv'])
        if curr_context['nsfw_acceptive']:
            prompt += G.A.PROMPT_ZNP if curr_context['target_lang'] == 'zh' else G.A.PROMPT_ENP
        if curr_context['known_info']:
            prompt += G.A.PROMPT_ZKP if curr_context['target_lang'] == 'zh' else G.A.PROMPT_EKP
        prompt = prompt.format(player_name=curr_context['player_name'], known_info=curr_context['known_info'])

        # Then inject
        # Note that system prompt item should not be modified from external
        self[0].content = prompt

    def json(self) -> list:
        self._prepare_context()
        return [i.json() for i in self]
    
    @overload
    def utilize(self, text_only=False) -> list: ...

    def utilize(self, *args, **kwargs):
        if self.session_num > 0:
            self._prepare_context()
        else:
            self.sanitize()
        return [i.utilize(*args, **kwargs) for i in self]

    # All init_db, to_db, from_db could fill self.session_id on successful execution, normally no need to pre-init
    async def init_db(self):
        user_id = self.fsc.maica_settings.verification.user_id; maica_pool = self.fsc.maica_pool
        assert user_id and self.session_num and maica_pool, "DB cridentials not complete"
        maica_assert(1 <= self.session_num < 10, full_info=f"{self.session_num} is not hosted session")

        # First if row exists already
        sql_expression_1 = "SELECT chat_session_id FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        result = await maica_pool.query_get(expression=sql_expression_1, values=(user_id, self.session_num))

        # Then record or new
        if result:
            chat_session_id, = result
        else:
            sql_expression_2 = "INSERT INTO chat_session (user_id, chat_session_num, content) VALUES (%s, %s, %s)"
            result = await maica_pool.query_modify(expression=sql_expression_2, values=(user_id, self.session_num, "[]"))
            chat_session_id = result[1]
        self.session_id = chat_session_id

    async def to_db(self):
        user_id = self.fsc.maica_settings.verification.user_id; maica_pool = self.fsc.maica_pool
        assert user_id and self.session_num and maica_pool, "DB cridentials not complete"
        maica_assert(1 <= self.session_num < 10, full_info=f"{self.session_num} is not hosted session")

        # First prepare data
        self_content = orjson.dumps(self.json()).decode()

        # Then if this row exists
        sql_expression_1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        result = await maica_pool.query_get(expression=sql_expression_1, values=(user_id, self.session_num))

        # Then update or new
        if result:
            chat_session_id, db_content = result
            sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
            result = await maica_pool.query_modify(expression=sql_expression_2, values=(self_content, chat_session_id))
        else:
            await messenger(self.fsc.websocket, 'save_session_not_present', "Determined session not exist, inserting new. Something might have went wrong if not manually operated DB", "306", self.fsc.traceray_id)
            sql_expression_2 = "INSERT INTO chat_session (user_id, chat_session_num, content) VALUES (%s, %s, %s)"
            result = await maica_pool.query_modify(expression=sql_expression_2, values=(user_id, self.session_num, self_content))
            chat_session_id, db_content = result

        if not self.session_id:
            self.session_id = chat_session_id
    
    async def from_db(self):
        user_id = self.fsc.maica_settings.verification.user_id; maica_pool = self.fsc.maica_pool
        assert user_id and self.session_num and maica_pool, "DB cridentials not complete"
        maica_assert(1 <= self.session_num < 10, full_info=f"{self.session_num} is not hosted session")

        # First get data & existence
        sql_expression_1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        result = await maica_pool.query_get(expression=sql_expression_1, values=(user_id, self.session_num))

        # Then load or warn
        if result:
            chat_session_id, db_content = result
            if db_content:
                self.load(db_content)
            else:
                self.clear()
                await messenger(self.fsc.websocket, 'session_no_content', "Determined session no content, using plain. Something might have went wrong if not manually operated DB", "306", self.fsc.traceray_id)
        else:
            chat_session_id = None; db_content = ''
            self.clear()
            await messenger(self.fsc.websocket, 'session_not_exist', "Determined session not exist, using plain. Something might have went wrong if not manually operated DB", "306", self.fsc.traceray_id)

        if not self.session_id:
            self.session_id = chat_session_id
    
    async def to_archive(self) -> int:
        """This requires session_id to function."""
        user_id = self.fsc.maica_settings.verification.user_id; maica_pool = self.fsc.maica_pool
        assert user_id and maica_pool, "DB cridentials not complete"
        assert self.session_id, "Archiving requires original session_id"

        # First if an open archive exists
        sql_expression_1 = 'SELECT archive_id, content FROM crop_archived WHERE chat_session_id = %s AND archived = 0'
        result = await maica_pool.query_get(expression=sql_expression_1, values=(self.session_id, ))

        # Then update or new
        if result:
            archive_id, archive_content = result
            json_archive: list = orjson.loads(archive_content)
            json_archive.extend(self.json())
            archive_content = orjson.dumps(json_archive).decode()

            # We control archives' length within a fair range by sealing large archives
            should_seal = int(len(archive_content) >= 100000)

            sql_expression_2 = "UPDATE crop_archived SET content = %s, archived = %s WHERE archive_id = %s"
            await maica_pool.query_modify(expression=sql_expression_2, values=(archive_content, should_seal, archive_id))
        else:
            archive_content = orjson.dumps(self.json()).decode()
            should_seal = int(len(archive_content) >= 100000)
            sql_expression_2 = "INSERT INTO crop_archived (chat_session_id, content, archived) VALUES (%s, %s, %s)"
            await maica_pool.query_modify(expression=sql_expression_2, values=(self.session_id, archive_content, should_seal))
    
    async def crop_length(self) -> Tuple[list, Literal[0, 1, 2]]:
        """Making it V2 style."""
        use_api = bool(int(G.A.CALC_TOKENS))
        max_length = self.fsc.maica_settings.basic.max_length
        warn_length = int(max_length * (2/3))
        generate_length = self.fsc.maica_settings.super.max_tokens

        async def _tokens_calc(messages):
            # This method lets model deployment calculate tokens amount
            # With vllm optimizations and local network, it should be fast enough for loop calculation
            # I'm not that sure

            host_info = get_host(G.A.MCORE_ADDR)
            return (await dld_json(f"{host_info[0]}://{host_info[1]}:{host_info[2]}/tokenize", False, False, 'post', carriage={"messages": messages}))['count']

        async def tokens_calc(messages):
            if use_api:
                # vllm is not stable sometimes, so we add sanity check
                count = await _tokens_calc(messages)
                sane_minimal = len(''.join([i['content'] for i in messages]))
                sane_maximal = max_length + generate_length + 100
                if messages:
                    assert sane_minimal < count <= sane_maximal, f"Token counting API bahvior insane, returning {count} out of range {sane_minimal}-{sane_maximal}"
            else:
                # It's binary already, we just take bytes / 3 as a approximation of token count
                return len(orjson.dumps(messages)) / 3

        def tokens_eval(count):
            match count:
                case x if x < warn_length:
                    return 0
                case x if warn_length <= x < max_length:
                    return 1
                case x if max_length <= x:
                    return 2
                
        cycle = 0; last_self_len = len(self)
        archiver = MaicaSession()
        if not self.session_id:
            await self.init_db()
        archiver.default_context = self.default_context
        archiver.session_id = self.session_id

        while True:
            cycle += 1
            messages = self.utilize(text_only=True)
            message_len = await tokens_calc(messages)
            messages_stat = tokens_eval(message_len)

            # If the session exceeds max length, we want to crop it until it goes below warn length
            # So we don't have to perform this too often
            if cycle <= 1:
                initial_stat = messages_stat
                stat_threshold = 0 if initial_stat >= 2 else 1
            if messages_stat <= stat_threshold:
                break

            # Here the session needs cropping
            while self[-1].role != "assistant" and len(self) > 1:
                archiver.insert(0, self.pop(-1))

            # Here be the deadlock preventions
            if last_self_len == len(self):
                raise MaicaDbWarning(f"Session cropper hit unexpected dead loop.\nSelf dump: {str(self)}\nArchiver dump: {str(archiver)}")
            last_self_len = len(self)

            if cycle >= 100:
                sync_messenger(f"Session cropper hit extreme fragmentation.\nSelf dump: {str(self)}\nArchiver dump: {str(archiver)}\nBreaking loop and trying to continue.", type=MsgType.WARN)
                break

        # Now finished cropping
        return archiver, initial_stat
    
    async def wrapped_save(self) -> Literal[0, 1, 2]:
        """V1 comtatible behavior."""
        archiver, stat = await self.crop_length()
        await self.to_db()
        await archiver.to_archive()
        return stat