import nest_asyncio
nest_asyncio.apply()
import re
import json
import asyncio
import datetime
import traceback
from random import sample
from maica_utils import *

class MtBoundCoroutine(SideBoundCoroutine):
    DB_NAME = 'triggers'
    PRIM_KEY = 'trigger_id'
    FUNC_NAME = 'mtrigger'
    DATA_TYPE = list

    def get_valid_triggers(self):
        aff=[];swt=[];met=[];cus=[]
        for trigger in self.sf_forming_buffer:
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
        return aff + swt + met + cus