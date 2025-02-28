import re

def filter_format(reply_appended, target_lang='zh'):
    reply_all_signatures = re.findall(r'\[(?:(?:[A-Za-z ]{1,15}?)|(?:[一-龥 ]{1,4}?))\]', reply_appended, re.I)
    emotion_etz = {
        "smile": "微笑",
        "worry": "担心",
        "grin": "笑",
        "think": "思考",
        "happy": "开心",
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
        "担心": "worry",
        "笑": "grin",
        "思考": "think",
        "开心": "happy",
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
    for sig in reply_all_signatures:
        fwd = ''
        if 'player' in sig:
            if sig == '[player]':
                continue
            else:
                fwd = '[player]'
        else:
            sig_striped = sig.strip('[').strip(']')
            (curr_emoset, oppo_emoset) = (emotion_etz, emotion_zte) if target_lang == 'zh' else (emotion_zte, emotion_etz)
            if ' ' in sig_striped:
                fwd = sig_striped.replace(' ', '')
            if sig_striped in oppo_emoset.keys():
                pass
            elif sig_striped in curr_emoset.keys():
                fwd = f'[{curr_emoset[sig_striped]}]'
            else:
                if target_lang == 'zh':
                    if '笑' in sig:
                        fwd = '[微笑]'
                    elif '心' in sig:
                        fwd = '[凝视]'
                    elif '思' in sig:
                        fwd = '[思考]'
                    else:
                        fwd = '[微笑]'
                else:
                    fwd = '[smile]'
        if fwd:
            reply_appended = re.sub(re.escape(sig), fwd, reply_appended, flags = re.I)
    return reply_appended

if __name__ == '__main__':
    ra = '[理解 ]没关系, [player]. [微笑 ]我知[fear]道[womble]你很忙[a1]. [开心]你能抽空[slash我]陪我就[害怕]很好啦!'
    print(filter_format(ra, 'zh'))