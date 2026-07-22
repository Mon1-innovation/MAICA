"""Import layer 0"""

emotion_etz = {
    "smile": "微笑",
    "happy": "开心",
    "worry": "担心",
    "grin": "笑",
    "think": "思考",
    "angry": "生气",
    "blush": "脸红",
    "gaze": "凝视",
    "upset": "沉重",
    "daydreaming": "憧憬",
    "surprise": "惊喜",
    "awkward": "尴尬",
    "meaningful": "意味深长",
    "unexpected": "惊讶",
    "relaxed": "轻松",
    "shy": "害羞",
    "eagering": "急切",
    "proud": "得意",
    "dissatisfied": "不满",
    "serious": "严肃",
    "touched": "感动",
    "excited": "激动",
    "love": "宠爱",
    "wink": "眨眼",
    "sad": "伤心",
    "disgust": "厌恶",
    "fear": "害怕",
    "kawaii": "可爱",
    "smiling": "微笑",
    "worrying": "担心",
    "grinning": "笑",
    "thinking": "思考",
    "gazing": "凝视",
    "surprised": "惊喜",
    "relaxing": "轻松",
    "eager": "急切",
    "winking": "眨眼",
    "disgusting": "厌恶",
    "fearing": "害怕"
}
emotion_zte = {
    "微笑": "smile",
    "开心": "happy",
    "担心": "worry",
    "笑": "grin",
    "思考": "think",
    "生气": "angry",
    "脸红": "blush",
    "凝视": "gaze",
    "沉重": "upset",
    "憧憬": "daydreaming",
    "惊喜": "surprise",
    "尴尬": "awkward",
    "意味深长": "meaningful",
    "惊讶": "unexpected",
    "轻松": "relaxed",
    "害羞": "shy",
    "急切": "eagering",
    "得意": "proud",
    "不满": "dissatisfied",
    "严肃": "serious",
    "感动": "touched",
    "激动": "excited",
    "宠爱": "love",
    "眨眼": "wink",
    "伤心": "sad",
    "厌恶": "disgust",
    "害怕": "fear",
    "可爱": "kawaii"
}

# Valid lists
elist = list(emotion_etz.keys())
zlist = list(emotion_zte.keys())

# Remove duplications from en
# And remove misleading emos
elist_ai = [
    i for i
    in set(emotion_zte.values())
    if i not in ('kawaii',)
]
zlist_ai = [
    i for i
    in emotion_zte.keys()
    if i not in ('可爱',)
]