import ws
import wiki_scraping
from openai import OpenAI

def make_inspire(session, chat_session_num = 9):
    success = True
    try:
        title, summary = wiki_scraping.get_random_page()
        prompt = f"利用提供的以下信息, 主动和我聊聊{title}: {summary}"
        ori_history = ws.rw_chat_session(session, chat_session_num, 'r', None)
        if ori_history[0]:
            ori_history = ori_history[3]
        print(ori_history)

    except Exception as excepted:
        success = False
        exception = excepted
    #print(summary)


if __name__ == '__main__':
    make_inspire([1, 0, 23], 9)