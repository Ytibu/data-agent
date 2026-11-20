import os

from dotenv import load_dotenv
load_dotenv(override=True)

from langchain.chat_models import init_chat_model
from app.conf.app_config import app_config


# 构建langchain模型对象
llm = init_chat_model(
    model="mimo-v2.6-flash",
    model_provider=app_config.llm.model_provider,
    base_url="https://api.xiaomimimo.com/v1",
    api_key=os.getenv("MIMO_API_KEY"),
    temperature=0
)

if __name__ == '__main__':
    for chunk in llm.stream("who are you?"):
        print(chunk.text,end="")
