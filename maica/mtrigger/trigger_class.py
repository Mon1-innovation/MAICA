import traceback
from typing import *
from maica.maica_utils import *

STRUCTURE_NOT_INTACT = MaicaInputWarning(f'Trigger structure not intact', '400', 'maica_mtrigger_item_bad')

class CommonTrigger():
    template = None
    """Should always exist."""
    name = None
    """Should always exist."""
    def __init__(self, **kwargs):
        try:
            self.name = kwargs.get('name')
            assert self.name, 'Trigger name absent'
        except Exception as e:
            raise e

class _exprop():
    item_list: Optional[list] = None
    curr_item: Optional[str] = None
    suggestion: Optional[bool] = None
    value_limits: Optional[list] = None
    curr_value: Optional[str] = None
    def __init__(self, **kwargs):
        prop_list = ['item_list', 'curr_item', 'suggestion', 'value_limits', 'curr_value']
        try:
            self.item_name = _item_name(**kwargs.get('item_name'))
            """Should always exist."""
            for acceptable_key in prop_list:
                if kwargs.get(acceptable_key) != None:
                    setattr(self, acceptable_key, kwargs.get(acceptable_key))
            if self.item_list:
                assert isinstance(self.item_list, list), 'Item list not list'
                self.item_list = limit_length(self.item_list, 72)
            if self.value_limits:
                assert isinstance(self.value_limits, list), 'Value limits not list'
                assert len(self.value_limits) == 2, 'Value limits not two'
        except Exception as e:
            raise e

class _item_name():
    def __init__(self, **kwargs):
        try:
            self.zh, self.en = kwargs.get('zh'), kwargs.get('en')
            assert self.zh and self.en, 'Item name absent'
        except Exception as e:
            raise e

class CommonAffectionTrigger(CommonTrigger):
    template = 'common_affection_template'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
class CommonSwitchTrigger(CommonTrigger):
    template = 'common_switch_template'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self.exprop = _exprop(**kwargs.get('exprop'))
            assert self.exprop.item_list, 'No item list provided for switch'
        except Exception as e:
            raise MaicaInputWarning(f'Trigger {self.name} not intact: {str(e)}') from e
        
class CommonMeterTrigger(CommonTrigger):
    template = 'common_meter_template'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self.exprop = _exprop(**kwargs.get('exprop'))
            assert self.exprop.value_limits
        except Exception as e:
            raise MaicaInputWarning(f'Trigger {self.name} not intact: {str(e)}') from e

class CustomizedTrigger(CommonTrigger):
    template = 'customized'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self.exprop = _exprop(**kwargs.get('exprop'))
        except Exception as e:
            raise MaicaInputWarning(f'Trigger {self.name} not intact: {str(e)}') from e