import os
import re
import json
import time
import pyperclip
import requests
from collections import deque

# ===== 配置区域 =====
with open("./.key", "r", encoding="utf-8") as f:
    DEEPSEEK_API_KEY = f.readline()
# DEEPSEEK_API_KEY = "YOUR_API_KEY"  # 替换为你的DeepSeek API密钥
API_URL = "https://api.deepseek.com/v1/chat/completions"
MAX_CONTEXT_LENGTH = 3000  # 最大上下文长度(字符)
CONTEXT_WINDOW = 3  # 上下文记忆段落数
GLOSSARY_FILE = "translation_glossary.json"  # 术语库文件

# ===== 术语管理 =====
def load_glossary():
    """加载术语库"""
    if os.path.exists(GLOSSARY_FILE):
        with open(GLOSSARY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_glossary(glossary):
    """保存术语库"""
    with open(GLOSSARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)

def update_glossary(text, translation):
    """从翻译结果中提取新术语"""
    glossary = load_glossary()
    updated = False
    
    # 识别技术术语 (英文+中文组合)
    term_pairs = re.findall(r'([A-Z][a-zA-Z0-9_]+)\s*[：:]\s*([\u4e00-\u9fff]+)', text + translation)
    
    for en, cn in term_pairs:
        if en not in glossary:
            glossary[en] = cn
            print(f"✨ 发现新术语: {en} -> {cn}")
            updated = True
    
    if updated:
        save_glossary(glossary)
    
    return glossary

# ===== 上下文管理 =====
context_queue = deque(maxlen=CONTEXT_WINDOW)  # 上下文记忆

def build_context_prompt():
    """构建上下文提示"""
    if not context_queue:
        return ""
    
    context_prompt = "\n\n【上下文参考】："
    for i, (src, trans) in enumerate(context_queue, 1):
        context_prompt += f"\n--- 上文{i} ---\n原文: {src}\n译文: {trans}"
    return context_prompt

# ===== DeepSeek API 交互 =====
def translate_text(text, glossary={}, retries=3):
    """调用DeepSeek API进行翻译"""
    context_prompt = build_context_prompt()
    glossary_str = "\n".join([f"{k}: {v}" for k, v in glossary.items()])
    
    prompt = (
        f"你是一位专业的技术文档翻译专家。请将以下技术内容准确翻译成中文：\n\n"
        f"{text}\n\n"
        f""
        f"【重要要求】：\n"
        f"1. 保持技术术语一致性（参考术语表）\n"
        f"2. 保留所有数字、符号和专有名词格式\n"
        f"3. 技术术语表：\n{glossary_str}\n"
        f"4. 只输出译文，不需要输出任何其它内容\n"
        f"{context_prompt}"
    )
    
    # 确保不超过上下文限制
    if len(prompt) > MAX_CONTEXT_LENGTH:
        excess = len(prompt) - MAX_CONTEXT_LENGTH
        prompt = prompt[excess:]
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 2000
    }
    
    for attempt in range(retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            translation = result['choices'][0]['message']['content'].strip()
            
            # 清理API返回的额外内容
            if "```" in translation:
                translation = re.sub(r'```[^\n]*\n', '', translation)
                translation = re.sub(r'\n```$', '', translation)
            
            return translation
        
        except Exception as e:
            print(f"尝试 {attempt+1}/{retries} 失败: {str(e)}")
            time.sleep(2 ** attempt)  # 指数退避
    
    raise Exception("API请求失败，请检查网络或API密钥")

# ===== 主工作流 =====
def main():
    glossary = load_glossary()
    print(f"✅ 已加载 {len(glossary)} 条术语")
    print("准备就绪! 复制文本后按Enter进行翻译 (输入'q'退出)")
    
    while True:
        input(">>> 复制文本后按Enter (或输入 'q' 退出) ")
        
        if pyperclip.paste().strip().lower() == 'q':
            print("退出翻译系统")
            break
        
        source_text = pyperclip.paste().strip()
        if not source_text:
            print("剪贴板为空!")
            continue
        
        print(f"📋 获取文本 ({len(source_text)}字符)")
        print("="*50)
        print(source_text[:500] + ("..." if len(source_text) > 500 else ""))
        print("="*50)
        
        try:
            translation = translate_text(source_text, glossary)
            pyperclip.copy(translation)
            
            # 更新上下文记忆
            context_queue.append((source_text, translation))
            
            # 提取并更新术语库
            # glossary = update_glossary(source_text, translation)
            
            print("\n✅ 翻译完成 (已复制到剪贴板):")
            print("="*50)
            print(translation[:500] + ("..." if len(translation) > 500 else ""))
            print("="*50)
            
        except Exception as e:
            print(f"❌ 翻译失败: {str(e)}")

if __name__ == "__main__":
    main()