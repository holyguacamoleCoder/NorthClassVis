from loop import LoopState
from loop import AgentLoop
from common.llm_client import LLMClient

def pipeline():
    loop_state = LoopState(messages=[])
    llm_client = LLMClient()
    while True:
        try:
            query = input("请输入问题: ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ["exit", "quit", "q"]:
            break
        loop_state.messages.append({
            "role": "user",
            "content": query,
        })

        agent_loop = AgentLoop(loop_state, llm_client=llm_client)
        agent_loop.run_loop()

        last = loop_state.messages[-1] if loop_state.messages else None
        if last and last.get("role") == "assistant":
            print(last.get("content") or "")
            
        
if __name__ == "__main__":
    pipeline()