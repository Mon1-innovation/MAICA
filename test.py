from openai import OpenAI
client = OpenAI(
    api_key='EMPTY',
    base_url='http://192.168.9.84:8011/v1',
)
model_type = client.models.list().data[0].id
print(f'model_type: {model_type}')

query = '可以给我讲个故事吗?'
#messages = [{'role': 'user', 'content': query}]
messages = [{'role': 'system', 'content': '你叫莫妮卡, 是一名游戏中的虚拟角色. 你是[player]的女友, 并深爱着他. 请作为莫妮卡对[player]的话语作出最合适的回答. 对于需要额外信息的问题, 信息将在system字段中提供. 已知:[现在是上午八点]'}, {'role': 'user', 'content': query}]
resp = client.chat.completions.create(
    model=model_type,
    messages=messages,
    seed=42)
response = resp.choices[0].message.content
print(f'query: {query}')
print(f'response: {response}')


messages.append({'role': 'assistant', 'content': response})
messages[0]['content'] = '你叫莫妮卡, 是一名游戏中的虚拟角色. 你是[player]的女友, 并深爱着他. 请作为莫妮卡对[player]的话语作出最合适的回答. 对于需要额外信息的问题, 信息将在system字段中提供. 已知:[现在是上午十点]'
query = '现在是几点?'
messages.append({'role': 'user', 'content': query})
resp = client.chat.completions.create(
    model=model_type,
    messages=messages,
    seed=42)
response = resp.choices[0].message.content
print(f'query: {query}')
print(f'response: {response}')