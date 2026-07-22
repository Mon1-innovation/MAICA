
import asyncio
import os
import orjson

from typing import *

from maica.maica_utils import *


class GenericModelHelper(AsyncCreator):
    """Main toolbox."""

    def __init__(self, csc: ConnSocketsContainer):
        """This is not per-user, so we use csc."""
        self.csc = csc
        if not csc.is_vector_ready:
            raise MaicaDbWarning("vector_db is not usable")

    async def _ainit(self):
        # This class is only instantialized once in the entire lc, so no need to further optimize
        # What about we just use user = -1 to store dataset vectors

        def _json_to_friendly(obj: list | dict):
            if isinstance(obj, list):
                msg_obj = obj

            elif isinstance(obj, dict):
                for possible_key in ('messages', 'conversations'):
                    if (
                        possible_key in obj
                        and isinstance(obj[possible_key], list)
                    ):
                        msg_obj = obj[possible_key]
                        break
                else:
                    raise MaicaDbWarning(f"No matching messages in object: {str(obj)}")
                
            else:
                raise MaicaDbWarning(f"Object is not list or dict: {str(obj)}")
            
            if not msg_obj:
                raise MaicaDbWarning("Processed object is empty")
            
            def translate_kv(d: dict):
                # Compat ms-swift format
                if "from" in d:
                    d["role"] = d.pop("from")
                if "value" in d:
                    d["content"] = d.pop("value")

            for i in msg_obj:
                translate_kv(i)

            # Now we have standard conversation objs, form readable conversations
            tlist = []
            for i in msg_obj:
                if i["role"] in ('user', 'assistant'):
                    tlist.append(f"{i["role"]}: {i["content"]}")
            
            text = "; ".join(tlist)
            return text
        
        def json_to_friendly(*args, **kwargs):
            try:
                return _json_to_friendly(*args, **kwargs)
            except Exception as e:
                sync_messenger(info=f"Error processing line: {str(e)}, skipping...")

        try:
            base_path = get_inner_path('mtools/generic')
            ds_set = set()
            with os.scandir(base_path) as ds_file_entries:
                for entry in ds_file_entries:
                    if entry.is_file() and entry.name.endswith('.jsonl'):
                        with open(entry.path, 'r', encoding='utf-8') as file:
                            ds_set.update(
                                json_to_friendly(orjson.loads(line))
                                for line in file
                                if line.strip()
                            )
        
            sync_messenger(info=f"[maica-gnrc] Loaded dataset lines for generic: {len(ds_set)}", type=MsgType.DEBUG)

        except Exception as e:
            sync_messenger(info=f"[maica-gnrc] Datasets may not exist: {str(e)}, ignoring and continuing", type=MsgType.DEBUG)

        if not ds_set:
            raise MaicaDbWarning("No dataset line found finally")

        await self.csc.vector_pool.cross_insert(
            embedding_conn=self.csc.embedding_conn,
            data=ds_set,
            filter={
                "user_id": -1,
            }
        )

    async def search(self, query: str):
        vector_pool = self.csc.vector_pool

        res_set = await vector_pool.embed_search(
            embedding_conn=self.csc.embedding_conn,
            data=[query],
            filter={
                "user_id": -1,
            },
            cfd_min=0,
        )

        return res_set