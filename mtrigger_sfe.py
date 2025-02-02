import os
import re
import json
import copy
import asyncio
import aiomysql
import functools
import traceback
from random import sample
from openai import AsyncOpenAI # type: ignore
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
        self.loop = asyncio.get_event_loop()
        self.valid_triggers = None

    def __del__(self):
        try:
            self.loop.run_until_complete(self._close_pools())
        except:
            pass

    async def _init_pools(self) -> None:
        global maicapool
        try:
            async with maicapool.acquire() as testc:
                pass
        except:
            maicapool = await aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.maicadb,loop=self.loop,autocommit=True)
            print("Mfocus recreated maicapool")

    async def _close_pools(self) -> None:
        global maicapool
        try:
            maicapool.close()
            await maicapool.wait_closed()
        except:
            pass

    async def send_query(self, expression, values=None, pool='maicapool', fetchall=False) -> list:
        global maicapool
        pool = maicapool
        if pool.closed:
            await self._init_pools()
            pool = maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if not values:
                    await cur.execute(expression)
                else:
                    await cur.execute(expression, values)
                #print(cur.description)
                results = await cur.fetchone() if not fetchall else await cur.fetchall()
                #print(results)
        return results

    async def send_modify(self, expression, values=None, pool='maicapool', fetchall=False) -> int:
        global maicapool
        pool = maicapool
        if pool.closed:
            await self._init_pools()
            pool = maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if not values:
                    await cur.execute(expression)
                else:
                    await cur.execute(expression, values)
                await conn.commit()
                lrid = cur.lastrowid
        return lrid

    async def init1(self):
        user_id, chat_session_num = self.user_id, self.chat_session_num
        try:
            sql_expression1 = 'SELECT content FROM triggers WHERE user_id = %s AND chat_session_num = %s'
            result = await self.send_query(sql_expression1, (user_id, chat_session_num))
            if not result:
                chat_session_num = 1
                sql_expression2 = 'SELECT content FROM triggers WHERE user_id = %s AND chat_session_num = %s'
                result = await self.send_query(sql_expression2, (user_id, chat_session_num))
                content = result[0]
            else:
                content = result[0]
            self.sf_content = json.loads(content)
        except:
            self.sf_content = []
        self.sf_content_temp = self.sf_content
    async def init2(self, user_id=None, chat_session_num=None):
        if not user_id:
            user_id = self.user_id
        if not chat_session_num:
            chat_session_num = self.chat_session_num
        try:
            sql_expression1 = 'SELECT content FROM persistents WHERE user_id = %s AND chat_session_num = %s'
            result = await self.send_query(sql_expression1, (user_id, chat_session_num))
            if not result:
                chat_session_num = 1
                sql_expression2 = 'SELECT content FROM persistents WHERE user_id = %s AND chat_session_num = %s'
                result = await self.send_query(sql_expression2, (user_id, chat_session_num))
                content = result[0]
            else:
                content = result[0]
            self.sf_content = json.loads(content)
        except:
            self.sf_content = []
        self.sf_content_temp = self.sf_content
    def add_extra(self, extra):
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
            if len(trigger['exprop']['item_list']) == 0:
                swt.remove(trigger)
            if len(trigger['exprop']['item_list']) > 72:
                trigger['exprop']['item_list'] = sample(trigger['exprop']['item_list'], 72)
        self.valid_triggers = aff+swt+met+cus
        return self.valid_triggers