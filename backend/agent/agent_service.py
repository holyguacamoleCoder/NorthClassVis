from loop import LoopState
from loop import AgentLoop
from common.llm_client import LLMClient

def pipeline():
    messages = []
    while True:
        # 用户循环输入问题
        try:
            query = input("请输入问题: ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ["exit", "quit", "q"]:
            break
        messages.append({
            "role": "user",
            "content": query,
        })
        loop_state = LoopState(messages)

        # 每个问题视作一个turn，进入agent loop
        agent_loop = AgentLoop(loop_state, llm_client=LLMClient())
        agent_loop.run_loop()

        # 每个turn结束后，输出结果
        print(loop_state.messages[-1]["content"])
            
        
if __name__ == "__main__":
    pipeline()