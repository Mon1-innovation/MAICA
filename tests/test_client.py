from dotenv import load_dotenv
load_dotenv('../maica/.env')
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv('MAICA_MCORE_ADDR'),
    api_key="-",
)
model = client.models.list().data[0].id
print(model)

completion = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "user", "content": "你好"}
    ],
    # extra_body={"structured_outputs": {"regex": r"^[^\u4e00-\u9fa5]*$"}},
    # extra_body={"structured_outputs": {}},
    response_format={'type': 'auto'},
    extra_body={},

)
print(completion.choices[0].message.content)

# {"regex": "^[一-龥]*"} ^[^\u4e00-\u9fa5]+$
# 'stream': True, 'stop': ['<|im_end|>', '<|endoftext|>'], 'response_format': {'type': 'text'}, 'extra_body': {}, 'max_tokens': 1600, 'seed': None, 'top_p': 0.7, 'temperature': 0.22, 'frequency_penalty': 0.44, 'presence_penalty': 0.34