"""Import layer 1.1"""
import asyncio

from abc import ABC, abstractmethod
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

@dataclass
class _exprop():
    """Extra props of MTrigger items."""
    type: Literal["switch", "meter", "boolean"]
    item_name: BilingualText
    kwargs: dict = field(default_factory=lambda: {})

    def __post_init__(self):
        match self.type:
            case "switch":
                item_list: list = self.kwargs["item_list"]
                assert item_list, "item_list is empty"
                assert isinstance(item_list, list), "item_list is not list"
                self.item_list = item_list

                curr_item: str = self.kwargs.get("curr_item")
                assert isinstance(curr_item, (str, NoneType)), "curr_item is not str or None"
                self.curr_item = curr_item

                self.suggestion = bool(self.kwargs.get("suggestion", False))
            
            case "meter":
                value_limits: list = self.kwargs["value_limits"]
                assert isinstance(self.value_limits, list) and len(self.value_limits) == 2, "value_limits must be list with 2 elements"
                self.value_limits = value_limits

                self.curr_value = float(self.kwargs.get("curr_value"))

            case "boolean":
                pass

    @classmethod
    def from_dict(cls, type: Literal["switch", "meter", "boolean"], d: dict):
        item_name = BilingualText(
            d["item_name"]["zh"],
            d["item_name"]["en"],
        )
        return cls(type, item_name, d)
    
    def to_properties(self):
        match self.type:
            case "switch":
                item_name = self.item_name
                item_list = self.item_list
                suggestion = self.suggestion

                required_params = [
                    WrappedOpenAIToolProperty(
                        "choice",
                        ["string", "null"],
                        _Bt(
                            f"根据用户的要求, 从以下{item_name.zh}中选出最合适的一项. 如果没有任何一项合适, 则回答null.",
                            f"According to user's request, choose the most proper {item_name.en} from the following list. Output null if none of them is proper."
                        ),
                        enum=item_list + [None],
                    )
                ]
                if suggestion:
                    required_params.append(
                        WrappedOpenAIToolProperty(
                            "suggestion",
                            ["string", "null"],
                            _Bt(
                                f"若你在choice中选择了null, 你需要回答最合适, 但上面未列出的{item_name.zh}. 否则回答null."
                                f"If you chose null in the choice section, you should provide the most proper {item_name.en} not listed above. Otherwise output null."
                            )
                        )
                    )

                return required_params
            
            case "meter":
                item_name = self.item_name
                lower, upper = self.value_limits

                required_params = [
                    WrappedOpenAIToolProperty(
                        "value",
                        ["number", "null"],
                        _Bt(
                            f"根据用户的要求, 为{item_name.zh}选择一个合适的值. 如果合适的值不存在, 则回答null.",
                            f"According to user's request, choose a proper value for {item_name.en}. Output null if the proper value does not exist."
                        ),
                        minimum=lower,
                        maximum=upper,
                    )
                ]

                return required_params
            
            case "boolean":
                return []
        
@dataclass
class BaseTrigger():
    """Base class of MTrigger items."""
    TEMPLATE: ClassVar[str]
    name: str
    exprop: Optional[_exprop] = None

    @classmethod
    def from_dict(cls, d: dict):
        template = d["template"]
        name = d["name"]
        kwargs = d.get("exprop")
        match template:
            case "common_affection_template":
                return AffectionTrigger(name)
            case "common_switch_template":
                return SwitchTrigger(
                    name,
                    _exprop.from_dict("switch", kwargs)
                )
            case "common_meter_template":
                return MeterTrigger(
                    name,
                    _exprop.from_dict("meter", kwargs)
                )
            case "customized":
                return BooleanTrigger(
                    name,
                    _exprop.from_dict("boolean", kwargs)
                )
            case _:
                raise MaicaInputWarning("template cannot be recognized")

    @abstractmethod 
    def to_tool(self) -> WrappedOpenAITool: ...

class AffectionTrigger(BaseTrigger):
    TEMPLATE = "common_affection_template"

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

class SwitchTrigger(BaseTrigger):
    TEMPLATE = "common_switch_template"

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

class MeterTrigger(BaseTrigger):
    TEMPLATE = "common_meter_template"

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

class BooleanTrigger(BaseTrigger):
    TEMPLATE = "customized"

    def to_tool(self):
        item_name = self.exprop.item_name

        return WrappedOpenAITool(
            self.name,
            _Bt(
                f"调用该工具以触发{item_name.zh}.",
                f"Call this tool to trigger {item_name.en}",
            )
        )
    
