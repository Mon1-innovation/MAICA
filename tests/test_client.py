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
        {"role": "user", "content": "你好啊"}
    ],
    extra_body={"guided_regex": "^[一-龥]*"},
)
print(completion.choices[0].message.content)