import gradio as gr
import json
import requests
import os
from typing import List, Dict, Any

# API配置
API_BASE = "http://localhost:8888"

# 工具函数
def call_api(endpoint: str, method: str = "GET", data: Dict[str, Any] = None) -> Dict[str, Any]:
    """调用API"""
    url = f"{API_BASE}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, params=data)
        else:
            response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# 摄入功能
def ingest_text(text: str, source: str) -> str:
    """摄入文本"""
    result = call_api("/ingest", method="POST", data={"text": text, "source": source})
    if "error" in result:
        return f"错误: {result['error']}"
    return result.get("result", "摄入成功")

def ingest_file(file: str, source: str) -> str:
    """摄入文件"""
    if not file:
        return "请选择文件"
    try:
        # 检查文件是否为文本文件
        text_extensions = {'.txt', '.py', '.js', '.html', '.css', '.md', '.json', '.xml', '.csv', '.log'}
        file_ext = os.path.splitext(file)[1].lower()
        
        if file_ext in text_extensions:
            # 文本文件：用utf-8读取
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
            result = call_api("/ingest", method="POST", data={"text": content, "source": source or os.path.basename(file)})
            if "error" in result:
                return f"错误: {result['error']}"
            return result.get("result", "文件摄入成功")
        else:
            # 二进制文件：跳过或尝试读取文本内容
            try:
                # 先尝试用utf-8读取
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                result = call_api("/ingest", method="POST", data={"text": content, "source": source or os.path.basename(file)})
                if "error" in result:
                    return f"错误: {result['error']}"
                return result.get("result", "文件摄入成功")
            except UnicodeDecodeError:
                # 如果utf-8失败，尝试其他编码
                try:
                    with open(file, "r", encoding="latin-1") as f:
                        content = f.read()
                    result = call_api("/ingest", method="POST", data={"text": content, "source": source or os.path.basename(file)})
                    if "error" in result:
                        return f"错误: {result['error']}"
                    return result.get("result", "文件摄入成功")
                except:
                    return f"错误: 无法读取文件 '{file}'，可能是二进制文件，请选择文本文件"
    except Exception as e:
        return f"错误: {str(e)}"

# 查询功能
def query_memory(question: str) -> str:
    """查询记忆"""
    result = call_api("/query", data={"q": question})
    if "error" in result:
        return f"错误: {result['error']}"
    return result.get("result", "无结果")

# 整合功能
def consolidate_memory() -> str:
    """手动触发整合"""
    result = call_api("/consolidate", method="POST")
    if "error" in result:
        return f"错误: {result['error']}"
    return result.get("result", "整合成功")

# 查看记忆
def list_memories() -> List[Dict[str, Any]]:
    """列出所有记忆"""
    result = call_api("/memories")
    if "error" in result:
        return []
    return result.get("memories", [])

# 删除记忆
def delete_memory(memory_id: int) -> str:
    """删除记忆"""
    result = call_api("/delete", method="POST", data={"memory_id": memory_id})
    if "error" in result:
        return f"错误: {result['error']}"
    return result.get("message", "删除成功")

# 清空所有记忆
def clear_all_memories() -> str:
    """清空所有记忆"""
    result = call_api("/clear", method="POST")
    if "error" in result:
        return f"错误: {result['error']}"
    return result.get("message", "清空成功")

# 获取状态
def get_status() -> str:
    """获取状态"""
    result = call_api("/status")
    if "error" in result:
        return f"错误: {result['error']}"
    return json.dumps(result, indent=2, ensure_ascii=False)

# 构建Gradio界面
with gr.Blocks(title="常驻记忆智能体") as app:
    gr.Markdown("# 常驻记忆智能体")
    
    with gr.Tab("摄入"):
        gr.Markdown("## 文本摄入")
        with gr.Row():
            text_input = gr.Textbox(label="文本内容", lines=5, placeholder="请输入要存储的文本...")
            source_input = gr.Textbox(label="来源", placeholder="例如：笔记、文章等")
        ingest_text_btn = gr.Button("摄入文本")
        text_output = gr.Textbox(label="结果", interactive=False)
        
        gr.Markdown("## 文件摄入")
        file_input = gr.File(label="选择文件")
        file_source_input = gr.Textbox(label="来源", placeholder="例如：文件名")
        ingest_file_btn = gr.Button("摄入文件")
        file_output = gr.Textbox(label="结果", interactive=False)
    
    with gr.Tab("查询"):
        gr.Markdown("## 记忆查询")
        query_input = gr.Textbox(label="问题", placeholder="请输入您的问题...")
        query_btn = gr.Button("查询")
        query_output = gr.Textbox(label="回答", lines=5, interactive=False)
    
    with gr.Tab("管理"):
        gr.Markdown("## 记忆管理")
        
        with gr.Row():
            list_btn = gr.Button("列出所有记忆")
            clear_btn = gr.Button("清空所有记忆")
        
        memories_output = gr.Textbox(label="记忆列表", lines=10, interactive=False)
        
        with gr.Row():
            memory_id_input = gr.Number(label="记忆ID", precision=0)
            delete_btn = gr.Button("删除记忆")
        delete_output = gr.Textbox(label="删除结果", interactive=False)
        
        gr.Markdown("## 记忆整合")
        consolidate_btn = gr.Button("手动触发整合")
        consolidate_output = gr.Textbox(label="整合结果", interactive=False)
    
    with gr.Tab("状态"):
        gr.Markdown("## 系统状态")
        status_btn = gr.Button("获取状态")
        status_output = gr.Textbox(label="状态信息", lines=10, interactive=False)
    
    # 事件绑定
    ingest_text_btn.click(
        fn=ingest_text,
        inputs=[text_input, source_input],
        outputs=text_output
    )
    
    ingest_file_btn.click(
        fn=ingest_file,
        inputs=[file_input, file_source_input],
        outputs=file_output
    )
    
    query_btn.click(
        fn=query_memory,
        inputs=query_input,
        outputs=query_output
    )
    
    list_btn.click(
        fn=lambda: json.dumps(list_memories(), indent=2, ensure_ascii=False),
        inputs=[],
        outputs=memories_output
    )
    
    delete_btn.click(
        fn=delete_memory,
        inputs=memory_id_input,
        outputs=delete_output
    )
    
    clear_btn.click(
        fn=clear_all_memories,
        inputs=[],
        outputs=delete_output
    )
    
    consolidate_btn.click(
        fn=consolidate_memory,
        inputs=[],
        outputs=consolidate_output
    )
    
    status_btn.click(
        fn=get_status,
        inputs=[],
        outputs=status_output
    )

if __name__ == "__main__":
    app.launch(share=False, server_port=8501)