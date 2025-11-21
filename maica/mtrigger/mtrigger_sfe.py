import re
import json
import asyncio
import datetime
import traceback
from .trigger_class import *
from maica.maica_utils import *

class MtPersistentManager(PersistentManager):
    DB_NAME = 'triggers'
    PRIM_KEY = 'trigger_id'
    FUNC_NAME = 'mtrigger'

    @staticmethod
    def EMPTY():
        return []

    @Decos.report_data_error
    def get_valid_triggers(self):
        if not self.settings.basic.mt_extraction and not self.settings.temp.mt_extraction_once:
            return None
        aff_trigger_list: list[CommonAffectionTrigger] = []
        switch_trigger_list: list[CommonSwitchTrigger] = []
        meter_trigger_list: list[CommonMeterTrigger] = []
        customized_trigger_list: list[CustomizedTrigger] = []

        for trigger_dict in self.sf_forming_buffer:
            match trigger_dict['template']:
                case 'common_affection_template':
                    trigger_inst = CommonAffectionTrigger(**trigger_dict)
                    aff_trigger_list.append(trigger_inst)
                case 'common_switch_template':
                    trigger_inst = CommonSwitchTrigger(**trigger_dict)
                    switch_trigger_list.append(trigger_inst)
                case 'common_meter_template':
                    trigger_inst = CommonMeterTrigger(**trigger_dict)
                    meter_trigger_list.append(trigger_inst)
                case _:
                    trigger_inst = CustomizedTrigger(**trigger_dict)
                    customized_trigger_list.append(trigger_inst)

        aff_trigger_list = limit_length(aff_trigger_list, 1)
        switch_trigger_list = limit_length(switch_trigger_list, 6)
        meter_trigger_list = limit_length(meter_trigger_list, 6)
        customized_trigger_list = limit_length(customized_trigger_list, 20)

        return aff_trigger_list + switch_trigger_list + meter_trigger_list + customized_trigger_list
    
    @Decos.report_data_error
    def add_extra(self, *args) -> None:
        # We should merge identical triggers here
        checkdict = {item['name']: i for i, item in enumerate(self.sf_forming_buffer)}
        for i, item in enumerate(args):
            key = item['name']
            if key in checkdict:
                self.sf_forming_buffer[checkdict[key]].update(item)
            else:
                self.sf_forming_buffer.append(item)

    @Decos.report_data_error
    def use_only(self, *args) -> None:
        self.sf_forming_buffer = list(args)

    @Decos.report_data_error
    def read_from_sf(self, seq) -> any:
        if not self.settings.basic.mt_extraction and not self.settings.temp.mt_extraction_once:
            return None
        return self.sf_forming_buffer[seq]
    