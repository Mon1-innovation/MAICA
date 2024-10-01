from maica_ws import *
import asyncio


async def main(instance):
    await instance.send_query(expression=("SELECT 42;"), fetchall=True)
    task = await asyncio.create_task(instance.run_hash_dcc(identity="edge", is_email=False, pwd="qazplm147369Xx"))
    print(task)


a = consql()
print('111')
asyncio.run(main(a))
