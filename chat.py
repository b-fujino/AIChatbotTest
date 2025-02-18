
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
last_role = ""
with st.container():
    for message in st.session_state.messages:
        if message["role"] == "system":continue # systemプロンプトは表示しない
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
        last_role = message["role"]


# もし最後のメッセージがuserだったらOpenAI に送信
if last_role == "user":
    # OpenAI に送信
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=st.session_state.messages
    )
    system_response = completion.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": system_response})

    # 表示
    st.rerun()


# ユーザーの入力を受け取る
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area("メッセージを入力してください:", key = "input")
    submit_button = st.form_submit_button(label="送信")

if submit_button:
    # ユーザーのメッセージを追加
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()

