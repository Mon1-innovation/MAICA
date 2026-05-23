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
        {"role": "user", "content": "Hello"}
    ],
    extra_body={"structured_outputs": {"regex": r"^[^\u4e00-\u9fa5]*$"}},
)
print(completion.choices[0].message.content)

# {"regex": "^[一-龥]*"} ^[^\u4e00-\u9fa5]+$