# 导入 Python 内置的 os 模块。os 负责和操作系统打交道，这里用它来读取环境变量。
import os
# python-dotenv 这个库专门负责读取 .env 文件，把里面的内容变成环境变量
from dotenv import load_dotenv
from google import genai

# 从环境变量里取出 key 的值，赋给变量 api_key。


load_dotenv()
# 从环境变量里取出 key 的值，赋给变量 api_key。
api_key = os.getenv("GEMINI_API_KEY")

# 用你的 key 创建一个"客户端"对象。
# 可以理解为：打开一条通往 Gemini 服务器的连接，并完成身份认证。
# 后面所有请求都通过这个 client 发出。
client = genai.Client(api_key = api_key)


# 第二部分：系统提示词，给 AI 的"角色说明书"，每次发请求时都会附带，告诉 AI 它是谁、必须遵守什么规则。
SYSTEM_PROMPT = """你是宠物急难分诊助手。
规则：每次回复的第一行必须是以下三个标记之一：
[TRIAGE:RED] = 生命威胁，立即急诊
[TRIAGE:YELLOW] = 今日内就医
[TRIAGE:GREEN] = 居家观察
之后用中文给出分析和建议。不诊断疾病，不推荐药物。"""

# 第三部分：发请求、解析标记、打印结果
user_input = "狗狗今早吐了一次，现在精神很好还在玩"

# 真正发请求给 Gemini 的地方。三个参数：
# model：用哪个模型，gemini-2.5-flash 是速度快、免费额度高的版本
# contents：用户说的话
# config：额外配置，这里把系统提示词塞进去
response = client.models.generate_content(
     model="gemini-2.5-flash",
     contents=user_input,
     config={"system_instruction": SYSTEM_PROMPT}
)

# 从返回结果里取出纯文字内容，存进 raw 变量。
raw = response.text
print("--- AI Response ---")
print(raw)


# 解析分诊级别
# 用 in 操作符检查字符串里有没有指定标记。
# in 在 Python 里表示"包含"——"abc" in "xabcx" 结果是 True。
# 找到哪个标记就把对应级别存进 level
if "[TRIAGE:RED]" in raw:
     level = "RED -emergency"
elif "[TRIAGE:YELLOW]" in raw:
     level = "YELLOW - to hospital soon"
elif "[TRIAGE:GREEN]" in raw:
     level = "GREEN - monitor at home"
else:
     level = "? - unable to determine"

print("\n--- Triage Result ---")
# f 开头的字符串叫 f-string，{} 里面放变量名，Python 会自动替换成变量的值。
print(f"Triage Level: {level}")



