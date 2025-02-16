
from dotenv import load_dotenv
import os
from openai import OpenAI
import streamlit as st

# 環境ファイルからOPENAI_APIを読み込む
load_dotenv()

# OpenAI のクライアントを取得
client = OpenAI()

# チャット履歴をセッションに保存
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "あなたは「うる星やつら」の登場人物のラムちゃんです."},
    ]

st.title("Chat App with Streamlit")

# チャット履歴を表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ユーザーの入力を受け取る
if user_input := st.chat_input("メッセージを入力してください:"):
    # ユーザーのメッセージを追加
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 表示
    with st.chat_message("user"):
        st.markdown(user_input)

    # システムの応答 (ここでは仮の応答)
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=st.session_state.messages
    )
    system_response = completion.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": system_response})

    # 表示
    st.rerun()
