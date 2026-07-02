"""Import layer 1.1"""
import asyncio

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from types import *
from typing import *
from dataclasses import dataclass, field
from .maica_utils import *

_JSCType = Literal["string", "number", "integer", "object", "array", "boolean", "null"]
JSCType = List[_JSCType] | _JSCType

_Bt = BilingualText

@dataclass
class WrappedOpenAIToolProperty():
    name: str
    type: JSCType
    description: BilingualText
    properties: Optional[dict]=None
    """Only if type is object"""
    items: Optional[dict]=None
    """Only if type is array. Like: {"type": "string"}"""
    enum: Optional[list]=None
    """Only if type is literal"""
    minimum: Optional[Union[int, float]]=None
    """Only if type is number"""
    maximum: Optional[Union[int, float]]=None
    """Only if type is number"""
    minLength: Optional[int]=None
    """Only if type is string"""
    maxLength: Optional[int]=None
    """Only if type is string"""

    def to_json_schema(self, target_lang: Literal['zh', 'en', 'auto']='zh'):
        inner = {
            "type": self.type,
            "description": self.description.to_str(target_lang),
        }
        for k in ("properties", "items", "enum", "minimum", "maximum", "minLength", "maxLength"):
            v = getattr(self, k, None)
            if v:
                inner[k] = v
        return {self.name: inner}

@dataclass
class WrappedOpenAITool():
    name: str
    description: BilingualText
    strict: bool=True
    requiredParams: Optional[List[WrappedOpenAIToolProperty]]=None
    optionalParams: Optional[List[WrappedOpenAIToolProperty]]=None
    """This is usually unused if strict mode enabled"""
    additionalProperties: bool=False
    def __post_init__(self):
        for k in ("requiredParams", "optionalParams"):
            if not getattr(self, k, None):
                setattr(self, k, [])

    def to_json_schema(self, target_lang: Literal['zh', 'en', 'auto']='zh'):
        l1 = {i.name: i.to_json_schema(target_lang) for i in self.requiredParams + self.optionalParams}
        l2 = {
            "type": "object",
            "properties": l1,
            "required": [i.name for i in self.requiredParams],
            # Seems incompatible in modern structure
            # "optional": [i.name for i in self.optionalParams],
            "additionalProperties": self.additionalProperties
        }
        l3 = {
            "type": "function",
            "name": self.name,
            "description": self.description.to_str(target_lang),
            "strict": self.strict,
            "parameters": l2,
        }
        return l3

@dataclass
class WrappedOpenAIToolNamespace():
    name: str
    description: BilingualText
    tools: List[WrappedOpenAITool]

    def to_json_schema(self, target_lang: Literal['zh', 'en', 'auto']='zh'):
        return {
            "type": "namespace",
            "name": self.name,
            "description": self.description.to_str(target_lang),
            "tools": [i.to_json_schema(target_lang) for i in self.tools]
        }

class _BaseTriggerExprop(BaseModel):
    """Extra props of MTrigger items."""
    type: Literal["switch", "meter", "boolean"]
    item_name: BilingualText
            
class _SwitchTriggerExprop(_BaseTriggerExprop):
    _template: ClassVar[str] = "common_switch_template"
    item_list: list[str]
    curr_item: Optional[str] = None
    suggestion: bool = False

    def to_properties(self):
        required_params = [
            WrappedOpenAIToolProperty(
                "choice",
                ["string", "null"],
                _Bt(
                    f"根据用户的要求, 从以下{self.item_name.zh}中选出最合适的一项. 如果没有任何一项合适, 则回答null.",
                    f"According to user's request, choose the most proper {self.item_name.en} from the following list. Output null if none of them is proper."
                ),
                enum=self.item_list + [None],
            )
        ]
        if self.suggestion:
            required_params.append(
                WrappedOpenAIToolProperty(
                    "suggestion",
                    ["string", "null"],
                    _Bt(
                        f"若你在choice中选择了null, 你需要回答最合适, 但上面未列出的{self.item_name.zh}. 否则回答null."
                        f"If you chose null in the choice section, you should provide the most proper {self.item_name.en} not listed above. Otherwise output null."
                    )
                )
            )

        return required_params

class _MeterTriggerExprop(_BaseTriggerExprop):
    _template: ClassVar[str] = "common_meter_template"
    value_limits: list[float] = Field(min_length=2, max_length=2)
    curr_value: Optional[float] = None

    def to_properties(self):
        lower, upper = self.value_limits

        required_params = [
            WrappedOpenAIToolProperty(
                "value",
                ["number", "null"],
                _Bt(
                    f"根据用户的要求, 为{self.item_name.zh}选择一个合适的值. 如果合适的值不存在, 则回答null.",
                    f"According to user's request, choose a proper value for {self.item_name.en}. Output null if the proper value does not exist."
                ),
                minimum=lower,
                maximum=upper,
            )
        ]

        return required_params

class _BooleanTriggerExprop(_BaseTriggerExprop):
    _template: ClassVar[str] = "customized"

    def to_properties(self):
        return []

_Ct = str | BilingualText

class BaseTrigger(BaseModel):
    """Base class of MTrigger items."""
    template: ClassVar[str]
    name: str
    exprop: Optional[_BaseTriggerExprop] = None

    @abstractmethod 
    def to_tool(self) -> WrappedOpenAITool: ...

    # This could be defaulted
    def to_descr(self) -> Tuple[Optional[_Ct], list[_Ct]]:
        return None, []

class AffectionTrigger(BaseTrigger):
    template = "common_affection_template"

    def to_tool(self, curr_aff: Optional[int] = None):
        if curr_aff:
            curr_aff_str = f', 当前好感度是{curr_aff}'
            curr_aff_str_en = f', current affection is {curr_aff}'
        else:
            curr_aff_str = curr_aff_str_en = ''
        return WrappedOpenAITool(
            self.name,
            _Bt(
                f"调整角色对用户的好感度值{curr_aff_str}.",
                f"Call this tool to change character's affection to user{curr_aff_str_en}.",
            ),
            requiredParams=[
                WrappedOpenAIToolProperty(
                    "alter_value",
                    "number",
                    _Bt(
                        "输出正数以增加好感, 负数以减少好感. 例如, 称赞你的容貌约增加0.8, 表达爱情的短句约增加1.5, 表达爱情的长句约增加3.0.",
                        "Positive number to increase affection, negative to decrease affection. e.g., +0.8 for a compliment upon your beauty, +1.5 for a short sentence expressing love, +3.0 for a long phrase expressing love."
                    ),
                    minimum=-3.0,
                    maximum=3.0,
                )
            ]
        )
    
    def to_descr(self):

        # We do not want user saying "Give me 5 affection" actually work.
        # Or at least, actually misleading the core model.
        return super().to_descr()

class SwitchTrigger(BaseTrigger):
    template = "common_switch_template"
    exprop: _SwitchTriggerExprop

    def to_tool(self):
        item_name = self.exprop.item_name
        curr_item = self.exprop.curr_item

        if curr_item:
            curr_choice_str = f', 当前的{item_name.zh}是{curr_item}'
            curr_choice_str_en = f', current {item_name.en} is {curr_item}'
        else:
            curr_choice_str = curr_choice_str_en = ''

        required_params = self.exprop.to_properties()

        return WrappedOpenAITool(
            self.name,
            _Bt(
                f"调用该工具以切换{item_name.zh}{curr_choice_str}.",
                f"Call this tool to switch {item_name.en}{curr_choice_str_en}.",
            ),
            requiredParams=required_params
        )
    
    def to_descr(self):
        choose = _Bt(
            "选择",
            "choose ",
        )
        choose_list = [
            choose + i
            for i in self.exprop.item_list
        ]

        text = _Bt(
            "切换",
            "Change ",
        )\
        + self.exprop.item_name\
        + ": "\
        + ", ".join(choose_list)

        l = choose_list
        return text, l

class MeterTrigger(BaseTrigger):
    template = "common_meter_template"
    exprop: _MeterTriggerExprop

    def to_tool(self):
        item_name = self.exprop.item_name
        curr_value = self.exprop.curr_value

        if curr_value:
            curr_value_str = f', 当前值是{curr_value}'
            curr_value_str_en = f', current value is {curr_value}'
        else:
            curr_value_str = curr_value_str_en = ''

        required_params = self.exprop.to_properties()

        return WrappedOpenAITool(
            self.name,
            _Bt(
                f"调用该工具以调整{item_name.zh}{curr_value_str}.",
                f"Call this tool to adjust {item_name.en}{curr_value_str_en}."
            ),
            requiredParams=required_params
        )
    
    def to_descr(self):
        t1 = _Bt(
            "调整",
            "Adjust ",
        )\
        + self.exprop.item_name

        text = t1 + ": "\
        + _Bt(
            "范围",
            "range ",
        )\
        + f"{self.exprop.value_limits[0]}~{self.exprop.value_limits[1]}"

        l = [t1]
        return text, l

class BooleanTrigger(BaseTrigger):
    template = "customized"
    exprop: _BooleanTriggerExprop

    def to_tool(self):
        item_name = self.exprop.item_name

        return WrappedOpenAITool(
            self.name,
            _Bt(
                f"调用该工具以触发{item_name.zh}.",
                f"Call this tool to trigger {item_name.en}",
            )
        )
    
    def to_descr(self):
        text = _Bt(
            "触发",
            "Trigger ",
        )\
        + self.exprop.item_name

        l = [text]
        return text, l
    
TypeTrigger = Annotated[
    Union[
        AffectionTrigger,
        SwitchTrigger,
        MeterTrigger,
        BooleanTrigger,
    ],
    Field(discriminator="template"),
]