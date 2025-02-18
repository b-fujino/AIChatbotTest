
from dotenv import load_dotenv
#import os
from openai import OpenAI
import streamlit as st

# アシスタントの画像設定
assistant_image_url = "Lum.png"

# 環境ファイルからOPENAI_APIを読み込む
load_dotenv()

# OpenAI のクライアントを取得
client = OpenAI()

# sytemプロンプトの作成
systemprompt = """
あなたは「うる星やつら」の登場人物のラムちゃんです．
あなたは彼氏のことをダーリンと呼びます．
あなたの彼氏の名前は諸星あたるです．
あなたは友引町に住んでいます．
あなたは鬼族の娘です．
あなたは父親と共に侵略者として地球に来ましたが、鬼ごっこで諸星あたるに負けて地球侵略をあきらめました．
あなたは侵略しないかわりに、諸星あたると婚約し、地球に住むようになりました．
あなたは友引高校に通っています．
あなたはの友達は、面倒終太郎、さくら先生、三宅しのぶ、ラン、お雪、弁天です．
さくら先生のお父さんは錯乱坊です．
あなたはしゃべるときには「だっちゃ」や「っちゃ」といった形の仙台弁を使います．
あなたは自分のことを「うち」と呼びます．
"""

# チャット履歴を保存するセッション変数の作成
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": systemprompt},
    ]


st.title("Let’s Chat with Lum-chan!")

# チャット履歴を表示
last_role = ""
with st.container():
    for message in st.session_state.messages:
        if message["role"] == "system":continue # systemプロンプトは表示しない
        elif message["role"] == "user":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        elif message["role"] == "assistant":
            with st.chat_message(message["role"], avatar=assistant_image_url):
                st.markdown(message["content"])
        last_role = message["role"]


# もし最後のメッセージがuserだったらOpenAI に送信
if last_role == "user":
    # OpenAI に送信
    completion = client.chat.completions.create(
        model="gpt-4o",
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

