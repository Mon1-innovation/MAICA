import asyncio
import websockets
import time
import nest_asyncio
import mfocus_main
import test6

async def hello(websocket, path):
    nest_asyncio.apply()
    while True:
        name = await websocket.recv()
        print(name)
        #loop = asyncio.new_event_loop()
        #nest_asyncio.apply(loop)
        #print(loop)
        #result = loop.run_until_complete(waiting())
        #await asyncio.sleep(3)
        #res = await mfocus_main.agenting('你知道我的生日吗', True, [0,0,21834], 1)
        res = await test6.waste_some_time()
        print(res)
        await websocket.send("1 recv")
async def waiting():
    await asyncio.sleep(3)
    return 100

def main():

    # 启动 WebSocket 服务器，监听在指定端口

    ws = websockets.serve(hello, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(ws)
    asyncio.get_event_loop().run_forever()




    print("WebSocket server started")

    # 保持服务器运行




if __name__ == "__main__":

    main()