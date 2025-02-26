
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st
import speech_recognition as sr
import logging


# アシスタントの画像設定
assistant_image_url = "https://b-fujino.github.io/AIChatbotTest/Lum.png"

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


# 過去のメッセージを表示
for message in st.session_state["messages"]:
    if message["role"] == "system":continue # systemプロンプトは表示しない
    elif message["role"] == "user":
        with st.chat_message(message["role"], avatar="Risa.png"):
            st.markdown(message["content"])
    elif message["role"] == "assistant":    
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <img src="{assistant_image_url}" style="width: 70px; height: 70px; border-radius: 50%; margin-right: 10px;">
            <div style="background-color: #e1f5fe; padding: 10px; border-radius: 10px;">
                {message["content"]}
            </div>
        </div>
        """, unsafe_allow_html=True)
        # with st.chat_message(message["role"], avatar="Lum.png"):
        #    st.markdown(message["content"])



def callback(recognizer, audio):
    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        st.session_state["messages"].append({"role": "user", "content": text})
        with st.chat_message("user"):
            st.markdown(text)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages
        )
        bot_response =  completion.choices[0].message.content
        st.session_state["messages"].append({"role": "assistant", "content": bot_response})
        with st.chat_message("assistant", avatar="Lum.png"):
            st.markdown(bot_response)
    except sr.UnknownValueError:
        st.write("音声を認識できませんでした。")
    except sr.RequestError:
        st.write("音声認識サービスにアクセスできませんでした。")

# 音声認識オブジェクトの作成
if "callback" not in st.session_state:
    st.session_state.callback = callback


# 音声認識オブジェクトの作成
if "recognizer" not in st.session_state:
    st.session_state.recognizer = sr.Recognizer()


# マイクの設定
if "m" not in st.session_state:
    st.session_state.m = sr.Microphone(sample_rate=44100)

# session変数としてstop_listeningを定義
if "stop_listening" not in st.session_state:
    st.session_state["stop_listening"] = None


# セッション状態を初期化
if "is_recording" not in st.session_state:
    st.session_state["is_recording"] = False

if not st.session_state["is_recording"]:
    if st.button("🎙️ 音声入力"):
        with st.session_state.m as source:
            st.session_state.recognizer.adjust_for_ambient_noise(source)  # 1秒間(デフォルト値なので省略してもよいが）環境音をキャリブレーション
        st.session_state["stop_listening"] = st.session_state.recognizer.listen_in_background(st.session_state.m, st.session_state.callback)
        st.write(st.session_state["stop_listening"])
        st.write("音声入力を開始...")
        st.session_state["is_recording"] = True

if st.session_state["is_recording"]:
    if st.button("🛑 音声入力を停止") :
        st.write(st.session_state["stop_listening"])
        st.session_state["stop_listening"](wait_for_stop=False)  # 完全に停止してから後続処理を行う
        st.session_state["is_recording"] = False  # 録音終了後にする
        st.write("音声入力を停止しました.")


