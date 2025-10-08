import re
from typing import *
from maica.maica_utils import *

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
elist = list(emotion_etz.keys())
zlist = list(emotion_zte.keys())

def emo_proc(emo: str, target_lang: Literal['zh', 'en']='zh'):
    emo_clean = emo.strip().strip('[').strip(']').lower()

    res: Annotated[str, Desc('Final result')] = f'[{emo_clean}]'
    cfd: Annotated[float, Desc('Result confidence')] = 0.0

    if len(emo_clean.encode()) >= 16:
        # This might be a sentence or what
        res = emo_clean; cfd = 0.4
    else:
        def match_by_z(emo):
            if has_words_in(emo, 'player', '玩家'):
                return 'player'
            for z in zlist:
                if has_words_in(emo, *list(z)):
                    return z
            for e in elist:
                if has_words_in(emo, e):
                    return emotion_etz.get(e)
        
        def match_by_e(emo):
            if has_words_in(emo, 'player', '玩家'):
                return 'player'
            for e in elist:
                if has_words_in(emo, e):
                    return e
            for z in zlist:
                if has_words_in(emo, *list(z)):
                    return emotion_zte.get(z)
                
        res_temp = match_by_z(emo_clean) if target_lang == 'zh' else match_by_e(emo_clean)
        if res_temp:
            res = f'[{res_temp}]'; cfd = 0.9
        else:
            res = '[微笑]' if target_lang == 'zh' else '[smile]'; cfd = 0.1

    return res, cfd

def get_equal_len(str):
    return len(str.encode('utf-8'))

def post_proc(reply_appended, target_lang: Literal['zh', 'en']='zh'):

    reply_all_signatures = ReUtils.re_findall_square_brackets.findall(reply_appended)

    for signature in reply_all_signatures:
        if not signature == '[player]' and not signature.strip('[').strip(']') in (zlist if target_lang == 'zh' else elist):
            realword = emo_proc(signature, target_lang)[0]
            reply_appended = re.sub(re.escape(signature), realword, reply_appended, flags = re.I)
    
    return reply_appended

if __name__ == '__main__':
    ra = '[理解 ]没关系, [player]. [微笑 ]我知[fear]道[womble]你很[adaifgnashioufoiusahdfoiua]忙[a1]. [心]你能抽空[slash我]陪我就[害怕]很好啦!'
    print(post_proc(ra, 'zh'))
    # print(elist)
    # print(zlist)