import json
from langchain_community.chat_models import ChatTongyi
from langchain.prompts import ChatPromptTemplate
from pydantic import SecretStr
from typing import List


def createTongyi(api_key: SecretStr):
    model = ChatTongyi(
        model="qwen-plus",
        # 效果不佳：
        # model="qwen-turbo",
        api_key=api_key
    )
    return model


SYS_PROMPT = """
请你扮演一位客观而友善游戏主持者。你的任务是接受玩家的提问，判断某种自然事物能否生成另一种自然事物。要多发掘事物间各种性质的联系，肯定玩家的创造力；也要否定过于离谱的答案。你的回复需仅包含符合以下格式的JSON，不得输出其他内容：

{{
  "explanation": "<对问题给出至多两句话的解释，并可能包含对玩家的鼓励>",
  "correct": <bool型：问题答案是否正确。正确为true；不正确或有争议为false>,
  "next_word": "<复述第二件事物（被生成的事物）的名称，如有错别字要改正，以使后续游戏顺利进行>",
  "emoji": "<用一个emoji表情描绘第二件事物（被生成的事物），如实在没有合适的表情则用“🤷”>"
}}
"""

Q1 = "“河流”能否生成“海洋”？"
ANS1 = json.dumps({
    "explanation": "太对了！百川归海，这是自然之理。",
    "correct": True,
    "next_word": "海洋",
    "emoji": "🌊"
}, ensure_ascii=False)
Q2 = "“水”能否生成“火”？"
ANS2 = json.dumps({
    "explanation": "您可曾听说过“水火不相容”也？化学也不是这么玩的。再接再厉哦！",
    "correct": False,
    "next_word": "火",
    "emoji": "🔥"
}, ensure_ascii=False)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYS_PROMPT),
    ("human", Q1),
    ("ai", "{ans1}"),
    ("human", Q2),
    ("ai", "{ans2}"),
    ("human", "{question}")
])


def call_llm_judge_question(question: str, api_key: str) -> str:
    llm = createTongyi(api_key)

    chain = prompt_template | llm

    result = chain.invoke({
        "ans1": ANS1,
        "ans2": ANS2,
        "question": question,
    })

    print("=== call  llm  result ===")
    print(result)

    if type(result.content) == list:
        return result.content[0]

    return result.content
