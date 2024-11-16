import asyncio
import time
 
# 定义一个耗时的操作
async def long_running_task(name):
    print(f"{name} started")
    await asyncio.sleep(1)  # 模拟耗时操作
    print(f"{name} finished")
    return 1
async def long_running_task2(name):
    print(f"{name} started")
    await asyncio.sleep(5)  # 模拟耗时操作
    print(f"{name} finished")
    return 2
# 定义主函数
async def main():
    task1 = asyncio.create_task(long_running_task("Task 1"))
    task2 = asyncio.create_task(long_running_task2("Task 2"))
    await task1
    print(str(task1)+str(time.time()))
    await task2
    print(str(task2)+str(time.time()))
    
	
 
    print("All tasks completed")
 
if __name__ == "__main__":
    # 启动事件循环并运行主函数
    asyncio.run(main())