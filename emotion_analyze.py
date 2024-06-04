import re
import json
from openai import OpenAI # type: ignore
def emotioning(input):
    client = OpenAI(
        api_key='EMPTY',
        base_url='http://192.168.9.84:8021/v1',
    )
    model_type = client.models.list().data[0].id
    print(model_type)
    system_init = """
Analyze the emotion contained in the following sentence. Output one of the following emotions, then output a number from 1 to 3 to describe how strong it is. Do not directly answer the sentence.
If you think the sentence contains multiple emotions, Output them one by one.
If you dont think the sentence contains any emotion, say None.
You can output these emotions:
1. [happy] means the speaker is likely feeling happy.

2. [sad] means the speaker is likely feeling sad.

3. [concerned] means the speaker is likely concerning about something.

4. [angry] means the speaker is likely feeling angry.
Begin!
"""
    messages = [{'role': 'system', 'content': system_init}, {'role': 'user', 'content': input}]
    resp = client.chat.completions.create(
        model=model_type,
        messages=messages,
        stop=['Observation:'],
        seed=42)
    response = resp.choices[0].message.content
    return response
    #print(f"first response is {response}")


if __name__ == "__main__":
    emotioning('现在几点了?')
    print(emotioning)