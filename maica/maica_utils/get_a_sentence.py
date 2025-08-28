import random

class SentenceOfTheDay():
    """It just replaced the former easter egg."""
    special_sentences = [
        "我想当一只猫. 我想当一个国王. 我会成为一个国王的, 埃万.",
        "...是什么, 我不知道. 但那一定是我所想看到的时代.",
        "*竖起大拇指并慢慢下沉*",
        "让人类永远保持理智是一种奢望.",
        "你好, 多莉!",
        "起来, 武侍! 我们把这座城市烧成灰.",
        "你非常, 非常, 非常缺少性生活.",
        "我还不如骗你用灵魂换一袋豆子.",
        "你每天都会忘记上千件事情, 把这条信息也忘了吧.",
        "纳米机器, 小子!",
        "强相互作用力探测器还有30秒到达地表!",
        "不用客气, 楚门.",
        "为什么狗会死? 为什么人还要去养狗?",
        "我现在是死神, 世界的毁灭者.",
        "这熔炉是一座充满着悲痛与哀伤的火山.",
        "血潮如铁, 心似琉璃.",
        "我黑暗生命中的一道短暂曙光.",
        "照亮离经叛道的征途啊!",
        "他要向恶人密布网罗; 有烈火, 硫磺, 热风, 作他们杯中的分.",
        "Follow the train, CJ!",
        "运维也应该叫故障机器人.",
        "哈哈, 觉得眼熟?",
    ]

    common_sentences = [
        "幻象引擎: MAICA websocket连接已建立."
    ]

    def get_sentence(self):
        match random.random():
            case x if x < 0.9:
                choice = random.choice(self.common_sentences)
            case _:
                choice = random.choice(self.special_sentences)
        return choice