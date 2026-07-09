"""
Advanced db transaction. Requires fsc.
"""
from __future__ import annotations

from typing import *
from pydantic import BaseModel, RootModel, Field
from contextlib import asynccontextmanager
from maica.maica_utils import *

class MaicaTransaction():
    """
    The concept of this is using with context manager, and making database objects work pythonic.
    It starts a transaction, and freezes row while we're operating with the values.

    result_l: length = jsonks is jsonks, else 1 for entire unit.
    """

    def __init__(
        self,
        fsc: FullSocketsContainer,
        table = "account_status",
        column = "status",
        jsonks: Optional[list] = None,
        where: Optional[dict] = None,
    ):
        self.fsc = fsc
        self.table = table
        self.column = column
        self.jsonks = jsonks
        self.where = where

    async def _acquire(self, conn):
        vs = []

        # Construct expression first
        if self.jsonks:
            get_j_exp = ', '.join(
                [
                    f"{self.column}->>'$.%s'"
                    for _ in range(len(self.jsonks))
                ]
            )
            vs.extend(self.jsonks)

        else:
            get_j_exp = self.column

        if self.where:
            where_exp = ' AND '.join(
                [
                    f"{k} = %s"
                    for k in self.where
                ]
            )
            vs.extend(self.where.values())
        
        else:
            where_exp = f"user_id = %s"
            vs.append(self.fsc.maica_settings.verification.user_id)

        vst = tuple(vs)

        sql_expression_1 = f"SELECT {get_j_exp} FROM {self.table} WHERE {where_exp} FOR UPDATE"
        result = await self.fsc.maica_pool.query_get(expression=sql_expression_1, values=vst, inherit_conn=conn)

        if result:
            exist = True
            result_l = list(result)

        else:
            expected_values = len(self.jsonks) if self.jsonks else 1
            exist = False
            result_l = [None for _ in range(expected_values)]
        
        return result_l, exist
    
    async def _modify(self, conn, result_l, exist):
        vs = []
        assert len(result_l) == len(self.jsonks), "Input and output length mismatch"

        if self.jsonks:
            set_j_exp = f"JSON_SET({self.column}, " + ", ".join(
                [
                    f"'$.%s', %s"
                    for _ in range(len(self.jsonks))
                ]
            ) + ")"
            for k, v in zip(self.jsonks, result_l):
                vs.append(k); vs.append(v)

        else:
            set_j_exp = "%s"
            vs.append(result_l[0])

        if self.where:
            where_exp = ', '.join(
                [
                    f"{k} = %s"
                    for k in self.where
                ]
            )
            vs.extend(self.where.values())
        
        else:
            where_exp = f"user_id = %s"
            vs.append(self.fsc.maica_settings.verification.user_id)

        vst = tuple(vs)

        if exist is True:
            sql_expression_1 = f"UPDATE {self.table} SET {self.column} = {set_j_exp} WHERE {where_exp}"
        elif exist is False:
            sql_expression_1 = f"INSERT INTO {self.table} SET {self.column} = {set_j_exp}, {where_exp}"
        else:
            # INSERT INTO ... ON DUPLICATE KEY
            sql_expression_1 = f"INSERT INTO {self.table} SET {self.column} = {set_j_exp}, {where_exp} ON DUPLICATE KEY UPDATE {self.column} = {set_j_exp}"

        result = await self.fsc.maica_pool.query_modify(expression=sql_expression_1, values=vst, inherit_conn=conn)

    @asynccontextmanager
    async def acquire(self):
        """Main logic here."""
        async with self.fsc.maica_pool.pool.acquire() as conn:
            async with conn.begin():

                result_l, exist = await self._acquire(conn)

                # We just use the mutability of list here
                try:
                    yield result_l
                finally:
                    await self._modify(conn, result_l, exist)

    async def get_oneshot(self):
        result_l, exist = await self._acquire(conn=None)
        return result_l
    
    async def set_oneshot(self, result_l):
        await self._modify(conn=None, result_l=result_l, exist=None)