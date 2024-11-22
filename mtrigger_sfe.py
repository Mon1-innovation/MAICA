import os
import re
import json
import copy
import asyncio
import functools
import traceback
from random import sample
from openai import AsyncOpenAI # type: ignore
import persistent_extraction
from loadenv import load_env

async def wrap_run_in_exc(loop, func, *args, **kwargs):
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs))
    return result

class mt_bound_instance():
    def __init__(self, user_id, chat_session_num):
        self.user_id, self.chat_session_num = user_id, chat_session_num
    def init1(self):
        user_id, chat_session_num = self.user_id, self.chat_session_num
        try:
            with open(f"triggers/{user_id}_{chat_session_num}.json") as savefile:
                pass
        except:
            chat_session_num = 1
        try:
            self.last_modded = os.path.getmtime(f"triggers/{user_id}_{chat_session_num}.json")
            with open(f"triggers/{user_id}_{chat_session_num}.json", 'r', encoding= 'utf-8') as savefile:
                self.sf_content = json.loads(savefile.read())
        except:
            self.sf_content = []
        self.sf_content_temp = copy.deepcopy(self.sf_content)
    def init2(self, user_id=None, chat_session_num=None):
        if not user_id:
            user_id = self.user_id
        if not chat_session_num:
            chat_session_num = self.chat_session_num
        try:
            with open(f"triggers/{user_id}_{chat_session_num}.json") as savefile:
                pass
        except:
            chat_session_num = 1
        try:
            new_last_modded = os.path.getmtime(f"triggers/{user_id}_{chat_session_num}.json")
            if self.sf_content and new_last_modded == self.last_modded:
                pass
            else:
                with open(f"triggers/{user_id}_{chat_session_num}.json", 'r', encoding= 'utf-8') as savefile:
                    self.sf_content = json.loads(savefile.read())
        except:
            self.sf_content = []
        if self.sf_content_temp != self.sf_content:
            self.sf_content_temp = copy.deepcopy(self.sf_content)
    def add_extra(self, extra):
        self.sf_content_temp = copy.deepcopy(self.sf_content)
        if extra:
            self.sf_content_temp.extend(extra)
    def use_only(self, extra):
        self.sf_content_temp = extra
    def get_all_triggers(self):
        return self.sf_content_temp
    def get_valid_triggers(self):
        aff=[];swt=[];met=[];cus=[]
        all_triggers = self.get_all_triggers()
        for trigger in all_triggers:
            match trigger['template']:
                case 'common_affection_template':
                    aff.append(trigger)
                case 'common_switch_template':
                    swt.append(trigger)
                case 'common_meter_template':
                    met.append(trigger)
                case _:
                    cus.append(trigger)
        aff = [aff[0]] if aff else []
        if len(swt) > 6:
            swt = sample(swt, 6)
        if len(met) > 6:
            met = sample(met, 6)
        if len(cus) > 20:
            cus = sample(cus, 20)
        for trigger in swt:
            if len(trigger['exprop']['item_list']) > 72:
                trigger['exprop']['item_list'] = sample(trigger['exprop']['item_list'], 72)
        return aff+swt+met+cus