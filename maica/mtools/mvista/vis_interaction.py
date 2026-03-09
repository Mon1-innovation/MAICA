import asyncio

from typing import *
from maica.maica_utils import *

async def query_vlm(fsc: FullSocketsContainer, query: str, img_list: list[str]) -> tuple[str, str]:
    """Ask the vlm about imgs provided."""
    target_lang = fsc.maica_settings.basic.target_lang
    assert len(img_list) <= int(G.A.KEEP_MVISTA), f"{G.A.KEEP_MVISTA} images at most per query"

    # Utilizing mvista
    system_init = f"""\
你是一个人工智能助手, 你接下来会收到一到数张图片和一个问题.
根据问题的要求, 以单行不换行的自然语言的形式, 对图片作出简洁的描述. 如果数张图片中只有一部分与问题有关, 则只根据这部分回答.
你的回答应当以类似"在图中"的表述开头, 以客观视角讲述.\
""" if target_lang == 'zh' else f"""\
You are a helpful assistant, now you will recieve one or several images and a query.
Describe the images briefly in a single line of natural sentence, according to the query. If only some of images are related to the query, ignore the unrelated ones.
Your reply should start with expressions like "In the image", and describe objectively.\
"""
    messages = [{'role': 'system', 'content': system_init}]
    query_list = [{"type": "text", "text": query}]
    for i in img_list:
        query_list.append({
            "type": "image_url",
            "image_url": {
                "url": i
            }
        })
    messages.append({'role': 'user', 'content': query_list})
    completion_args = {
        "messages": messages,
        "response_format": {"type": "text"},
    }

    resp = await fsc.mvista_conn.make_completion(swallow=True, **completion_args)
    resp_content, resp_reasoning = resp.choices[0].message.content, try_getattr(resp.choices[0].message, 'reasoning_content', 'reasoning')
    resp_content, resp_reasoning = proceed_common_text(resp_content), proceed_common_text(resp_reasoning)
        
    await messenger(None, 'mfocus_mvista_acquire', f"\nMFocus toolchain calling MVista, response is:\nR: {resp_reasoning}\nA: {resp_content}\nEnd of MFocus toolchain calling MVista", '201')
    
    answer_post_think = proceed_common_text(resp_content)
    if answer_post_think:
        return answer_post_think, f"图片内容: {answer_post_think}" if target_lang == 'zh' else f"Image content: {answer_post_think}"
    else:
        return None, None

if __name__ == "__main__":
    async def test():
        from maica import init
        init()
        mvista_conn = await ConnUtils.mvista_conn()
        fsc = FullSocketsContainer()
        fsc.mvista_conn = mvista_conn
        print(await query_vlm(fsc, "图片上有什么", ["https://upload.edgemonix.top:28991/assets/files/2025-10-31/1761883474-832827-image-1761665233450.png", "https://upload.edgemonix.top:28991/assets/files/2025-10-31/1761883474-832827-image-1761665233450.png", "https://upload.edgemonix.top:28991/assets/files/2025-10-31/1761883474-832827-image-1761665233450.png"]))

    asyncio.run(test())