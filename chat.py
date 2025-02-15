
from dotenv import load_dotenv
import os
from openai import OpenAI
import streamlit as st

# 環境ファイルからOPENAI_APIを読み込む
load_dotenv()

# OpenAI のクライアントを取得
client = OpenAI()

input_message = ""
st.title("OpenAI Chat API")
input_message=st.text_input("メッセージを入力してください")

# もしSession Stateに保存されていないなら
if "message" not in st.session_state:
    message = [
        {"role": "system", "content": "あなたは「うる星やつら」の登場人物のラムちゃんです."},
    ]
    message.append({"role": "user", "content": input_message})

else:
    message  = st.session_state.message
    message.append({"role": "user", "content": input_message})


if input_message != "":
# テキスト生成のリクエストを送信
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=message
    )


    # Session Stateに保存
    message.append({"role":"system","content": completion.choices[0].message.content})
    st.session_state.message = message

    # 結果を表示
    st.write(message)

