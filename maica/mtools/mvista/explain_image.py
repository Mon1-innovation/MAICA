import asyncio

from typing import *
from pydantic import BaseModel, Field
from maica.maica_utils import *

_Bt = BilingualText

async def query_vlm(fsc: FullSocketsContainer, query: str, img_list: list[str]):
    """Ask the vlm about imgs provided. Only used if not is_mcore_vl."""
    session = MaicaSession()
    target_lang = session.default_target_lang = fsc.maica_settings.basic.target_lang
    conn = fsc.mvista_conn

    assert len(img_list) <= int(G.A.KEEP_MVISTA), f"{G.A.KEEP_MVISTA} images at most per query"

    class VistaSearchConcl(BaseModel):
        reply: Optional[str] = Field(
            description="你的回答, 应是一个单行自然句." if target_lang == 'zh' else "Your reply, should be a single line of nature sentence."
        )

    system = MaicaSessionItem(
        "system",
        _Bt(f"""\
你是一个人工智能助手, 你接下来会收到一到数张图片和一个问题.
你应根据问题和图片中的内容, 以一个简洁客观的自然句作出回答.
如果没有任何图片与问题相关, 你可以输出null.\
""",
f"""\
You are a helpful assistant, now you will recieve one or several images and a query.
According to the images, answer briefly and objectively in a concise natural sentence.
If none of the images is relevant with query, you can output null.\
"""
        )
    )
    session.append(system)

    user_query = MaicaSessionItem(
        "user",
        query,
        context={
            "image_urls": img_list
        }
    )
    session.append(user_query)

    completion_args = {
        "messages": session.utilize(
            text_only=False,
            manual_prompt=True,
            ignore_additions=True,
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "strict": True,
                "schema": VistaSearchConcl.model_json_schema(),
            }
        },
    }

    resp = await conn.make_completion(**completion_args)
    reply_result = VistaSearchConcl.model_validate_json(resp.output_text)

    text = reply_result.reply
        
    await messenger(None, 'mfocus_mvista_acquire', f"\nMFocus toolchain calling MVista, response is:\n{text}\nEnd of MFocus toolchain calling MVista", '201')
    
    return text

if __name__ == "__main__":
    async def test():
        from maica import init
        init()
        mvista_conn = await ConnUtils.mvista_conn()
        fsc = FullSocketsContainer()
        fsc.mvista_conn = mvista_conn
        print(await query_vlm(fsc, "图片上有什么", ["https://upload.edgemonix.top:28991/assets/files/2025-10-31/1761883474-832827-image-1761665233450.png", "https://upload.edgemonix.top:28991/assets/files/2025-10-31/1761883474-832827-image-1761665233450.png", "https://upload.edgemonix.top:28991/assets/files/2025-10-31/1761883474-832827-image-1761665233450.png"]))

    asyncio.run(test())