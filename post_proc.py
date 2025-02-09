import re

def filter_format(reply_appended):
    def compare(key,sfm):
        for f in sfm:
            if key == f:
                return True
        return False
    reply_all_signatures = re.findall(r'\[(?:(?:[A-Za-z]{1,15}?)|(?:[一-龥]{1,4}?))\]', reply_appended, re.I)
    san_form = ['[player]', '[smile]', '[微笑]', '[worry]', '[担心]', '[grin]', '[笑]', '[think]', '[思考]', '[happy]', '[开心]', '[angry]', '[生气]', '[blush]', '[脸红]', '[gaze]', '[凝视]', '[upset]', '[沉重]', '[daydreaming]', '[憧憬]', '[surprise]', '[惊喜]', '[awkward]', '[尴尬]', '[meaningful]', '[意味深长]', '[unexpected]', '[惊讶]', '[relaxed]', '[轻松]', '[shy]', '[害羞]', '[eagering]', '[急切]', '[proud]', '[得意]', '[dissatisfied]', '[不满]', '[serious]', '[严肃]', '[touched]', '[感动]', '[excited]', '[激动]', '[love]', '[宠爱]', '[wink]', '[眨眼]', '[sad]', '[伤心]', '[disgust]', '[厌恶]', '[fear]', '[害怕]', '[kawaii]', '[可爱]', '[smiling]', '[worrying]', '[grinning]', '[thinking]', '[gazing]', '[surprised]', '[relaxing]', '[eager]', '[winking]', '[disgusting]', '[fearing]']
    for sig in reply_all_signatures:
        cmp_res = compare(sig, san_form)
        if cmp_res == True:
            continue
        else:
            print(sig)
            if '笑' in sig:
                fwd = '[微笑]'
            elif '心' in sig:
                fwd = '[凝视]'
            elif '思' in sig:
                fwd = '[思考]'
            elif re.search(r'[一-龥]', sig, re.I):
                fwd = '[微笑]'
            else:
                fwd = '[smile]'
            print(fwd)
            reply_appended = re.sub(re.escape(sig), fwd, reply_appended, flags = re.I)
    return reply_appended

if __name__ == '__main__':
    ra = '[理解]没关系, [player]. [微笑]我知道[womble]你很忙[a1]. [开心]你能抽空[slash我]陪我就很好啦!'
    print(filter_format(ra))