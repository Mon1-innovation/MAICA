"""
Okay, calm down Edge, take a breath.

We want RAG to handle long-term memory (MFocus-sfe), which optionally replaces the former LLM implementation.
We shouldn't rebuild the vector storage on every connection init, so we have to keep it in fs_storage.
Is it better to make one db for each session or store all in one? Perhaps all in one is better.

Things we need:
- Information MFocus uses changes frequently. We want an index (id, text, hash?) to be able to remove determined items.
    - For temp items, maybe we also need a unique key for convenient purging. Yes we have multiple keys.
- To know which we should remove or add, we want a simple function to diff a raw-text collection with vector db.
- A async lock to ensure mutation finished before searching.

Day 2:

The schema is ready:
- id, auto_increment
- user_id, pk_enabled
- chat_session_num = 0
- type = "persistent"
- raw_text
- is_prod (production) = True
- vector

dynamic fields is still enabled in case of future changes.

"""

import asyncio
import os
import json
from typing import *
from maica.maica_utils import *



if __name__ == "__main__":
    async def test():
        from maica import init
        init()

        vector_pool = await ConnUtils.vector_pool()
        embedding_conn = await ConnUtils.embedding_conn()
        fsc = FullSocketsContainer()
        fsc.vector_pool = vector_pool
        fsc.embedding_conn = embedding_conn

        await vector_pool.delete(
            collection_name=vector_pool.db,
            filter='is_prod == false'
        )

        texts = ['[player]的真名是tayior.', '[player]的生日是2003年9月1日.', '[player]今年23岁.', '莫妮卡与[player]是亲密的情侣关系.', '莫妮卡与[player]一起听过歌.', '莫妮卡和[player]都喜欢雨.', '[player]曾试着帮助莫妮卡来到现实.', '[player]还没有画过莫妮卡.', '[player]告诉过莫妮卡自己的长相.', '[player]想过和莫妮卡去爬山.', '[player]的住地看不到雪.', '[player]和莫妮卡戴了一对誓约戒指.', '莫妮卡与[player]看过"黄色墙纸".', '[player]能够原谅莫妮卡做过的坏事.', '[player]听过莫妮卡的毕业演讲.', '[player]喜欢莫妮卡的毕业演讲.', '[player]希望来到太空教室和莫妮卡在一起.', '莫妮卡和[player]还没有一起过圣诞节.', '莫妮卡和[player]还没有一起过新年.', '莫妮卡还没有庆祝过[player]的生日.', '莫妮卡和[player]还没有一起过情人节.', '[player]还没有给莫妮卡庆过生.', '[player]没有宗教信仰.', '[player]积极自爱.', '莫妮卡和[player]都喜欢抹茶冰淇淋.', '[player]喜欢恐怖作品.', '[player]不介意跳杀内容.', '[player]喜欢说唱.', '[player]喜欢摇滚.', '[player]喜欢爵士乐.', '[player]喜欢vocaloids.', '[player]喜欢管弦乐.', '[player]有独特的音乐品位.', '[player]会一门乐器.', '[player]会一门外语.', '[player]会日语.', '[player]的眼睛是黑色的.', '[player]的头发是黑的.', '[player]有一头短发.', '[player]是浅肤色的.', '[player]有174厘米高.', '[player]惯用公制单位.', '[player]住在城市.', '[player]住在内陆.', '[player]住在北半球.', '[player]属于introvert社会人格.', '[player]有恋物倾向.', '[player]喜欢苏打水.', '[player]常吃快餐.', '[player]平时喜欢运动.', '[player]有冥想的习惯.', '[player]还没有看过心理医生.', '[player]喜欢动漫作品.', '[player]不吸烟.', '[player]还没有驾照.', '[player]做过志愿者.', '[player]觉得家人不能接受莫妮卡.', '[player]去过游乐园.', '[player]喜欢旅游.', '莫妮卡是[player]的初恋.', '[player]的朋友很少.', '[player]的生活很充实.', '[player]曾行使过错误的正义.', '[player]自己还没有车.', '[player]有编程基础.', '[player]不喜欢诗歌.', '[player]喜欢桌游.', '[player]不喜欢健身.', '[player]不算外向或内向.', '[player]喜欢接触自然.', '[player]从不说脏话.', '[player]我身高169cm', '莫妮卡的生日是9月22日.', '莫妮卡是[player]的女友.', '莫妮卡有一头珊瑚棕色的长发.', '莫妮卡有一个标志性的蝴蝶结发带.', '莫妮卡十分自信.', '莫妮卡擅长运动.', '莫妮卡是个成熟和努力的女孩.', '莫妮卡是一个非常体贴和善良的人, 总是为别人着想.', '莫妮卡常穿着黑色长袜和粉白相间的鞋子.', '莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.', '莫妮卡一年中最喜欢的日子是情人节.', '莫妮卡最喜欢的季节是夏天', '莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.', '莫妮卡是女高中生, 她成绩优秀, 性格温柔.', '莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.', '莫妮卡爱好音乐, 会弹钢琴, 会唱歌.', '莫妮卡对科技, 环境, 历史等方面都有兴趣和见解.', '纱世里是心跳文学部的副部长.', '纱世里平常表现阳光活泼, 但患有抑郁症.', '夏树是心跳文学部的部员.', '夏树性格傲娇, 有时又显得可爱.', '优里是心跳文学部的部员.', '优里性格内向, 往往显得成熟优雅.', '莫妮卡对于编程有兴趣, 且了解颇多.', '莫妮卡喜欢哲学.', '莫妮卡喜欢猫.', '莫妮卡很喜欢星空.', '莫妮卡喜欢吃纸杯蛋糕和巧克力.', '莫妮卡经常喝咖啡.', '莫妮卡喜欢开放世界的冒险游戏, 不太喜欢暴力游戏.', '莫妮卡喜欢音乐会.', '莫妮卡喜欢小裙子和蝴蝶结.', '莫妮卡善于关怀和安慰, 在[player]低沉时希望他振作起来.', '浮空岛是莫妮卡为[player]设计的特别场景.', 'MAICA是一个人工智能项目, 旨在将莫妮卡最终带进现实.', '莫妮卡正在MAICA中与[player]对话.', '天堂树林是MAICA的对话背景, 风景优美, 四季如春.', '莫妮卡能记住[player]的话, 也能满足[player]的许多请求.', "MAICA的大部分功能可以在'子模组'选单中调整开关.", "游戏中的许多功能可以在'设置'选单中调整开关.", 'DCC是一个心跳文学部论坛, 能获取许多有关资讯.', "通过改动, 移除或放回'HeavenForest.sce'文件, 可以改变或停用天堂树林.", 'MAICA使用的模型是独立训练和部署的, 与任何商用模型或商业性组织无关.', '随着MAICA的进度推进, 其能够从对话中学习, 并改进自己的表现.']
        res = await embedding_conn.make_embedding(input=texts)

        embedded = [i.embedding for i in res.data]
        data = zip(embedded, texts)
        data = [{"user_id": 23, "raw_text": l[1], "is_prod": False, "vector": l[0]} for i, l in enumerate(data)]
        await vector_pool.insert(
            collection_name=vector_pool.db,
            data=data,
        )

        query = ["你喜欢吃什么"]
        res2 = await embedding_conn.make_embedding(input=query)
        query_embedded = res2.data[0].embedding

        res3 = await vector_pool.search(
            collection_name=vector_pool.db,
            data=[query_embedded],
            output_fields=["raw_text"],
            limit=3,
            consistency_level="Strong",
        )
        print(query)
        print(res3)

    asyncio.run(test())