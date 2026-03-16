import asyncio
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import MemoryDB, ToolCallSession, BaseLLM, IngestAgent, ConsolidateAgent, QueryAgent, OrchestratorAgent

async def test_database():
    """测试数据库功能"""
    print("=== 测试数据库功能 ===")
    db = MemoryDB()
    
    # 测试存储记忆
    memory = db.store_memory(
        raw_text="测试记忆内容",
        summary="测试记忆摘要",
        entities=["测试", "记忆"],
        topics=["测试", "记忆"],
        importance=0.8,
        source="test"
    )
    print(f"存储记忆结果: {memory}")
    
    # 测试读取未整合记忆
    unconsolidated = db.read_unconsolidated_memories()
    print(f"未整合记忆: {unconsolidated}")
    
    # 测试存储整合结果
    consolidation = db.store_consolidation(
        source_ids=[memory["memory_id"]],
        summary="测试整合摘要",
        insight="测试整合洞察",
        connections=[{"from_id": memory["memory_id"], "to_id": memory["memory_id"], "relationship": "测试关系"}]
    )
    print(f"存储整合结果: {consolidation}")
    
    # 测试读取所有记忆
    all_memories = db.read_all_memories()
    print(f"所有记忆: {all_memories}")
    
    # 测试读取整合历史
    consolidations = db.read_consolidation_history()
    print(f"整合历史: {consolidations}")
    
    # 测试获取统计信息
    stats = db.get_memory_stats()
    print(f"统计信息: {stats}")
    
    # # 测试删除记忆
    # delete_result = db.delete_memory(memory["memory_id"])
    # print(f"删除记忆结果: {delete_result}")
    
    # # 测试清空所有记忆
    # clear_result = db.clear_all_memories()
    # print(f"清空所有记忆结果: {clear_result}")

async def test_agents():
    """测试智能体功能"""
    print("\n=== 测试智能体功能 ===")
    
    # 初始化数据库
    db = MemoryDB()
    
    # 初始化工具会话
    tool_session = ToolCallSession(db)
    
    # 初始化LLM
    llm = BaseLLM(
       model_name="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base_url=os.getenv("OPENAI_BASE_URL"),
    )
    
    # 初始化智能体
    ingest_agent = IngestAgent(llm, tool_session)
    consolidate_agent = ConsolidateAgent(llm, tool_session)
    query_agent = QueryAgent(llm, tool_session)
    orchestrator = OrchestratorAgent(llm, tool_session, ingest_agent, consolidate_agent, query_agent)
    
    # 测试摄入智能体
    print("测试摄入智能体...")
    ingest_result = await ingest_agent.process("这是一个测试记忆", "test")
    print(f"摄入结果: {ingest_result}")
    
    # 测试整合智能体
    print("\n测试整合智能体...")
    consolidate_result = await consolidate_agent.process()
    print(f"整合结果: {consolidate_result}")
    
    # 测试查询智能体
    print("\n测试查询智能体...")
    query_result = await query_agent.process("你知道什么？")
    print(f"查询结果: {query_result}")
    
    # 测试协调智能体
    print("\n测试协调智能体...")
    orchestrator_result = await orchestrator.process("你知道什么？")
    print(f"协调智能体结果: {orchestrator_result}")

async def main():
    """主测试函数"""
    try:
        await test_database()
        await test_agents()
        print("\n所有测试完成！")
    except Exception as e:
        print(f"测试过程中出错: {e}")

if __name__ == "__main__":
    asyncio.run(main())