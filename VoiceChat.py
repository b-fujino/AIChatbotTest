import streamlit as st
import speech_recognition as sr

# チャット履歴を保存するセッション状態を確保
if "messages" not in st.session_state:
    st.session_state["messages"] = []

st.title("シンプルチャットアプリ（音声入力対応）")

def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.write("音声入力を開始...")
        try:
            audio = recognizer.listen(source, timeout=15)
            text = recognizer.recognize_google(audio, language="ja-JP")
            return text
        except sr.UnknownValueError:
            return "音声を認識できませんでした。"
        except sr.RequestError:
            return "音声認識サービスにアクセスできませんでした。"

# 過去のメッセージを表示
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 音声入力ボタン
if st.button("🎙️ 音声入力"):
    user_input = recognize_speech()
else:
    user_input = st.text_input("メッセージを入力してください:", "", key="user_input")

if user_input:
    # ユーザーメッセージを表示
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 簡単な応答をする（今回はエコー）
    bot_response = f"あなたはこう言いました: {user_input}"
    st.session_state["messages"].append({"role": "assistant", "content": bot_response})
    with st.chat_message("assistant"):
        st.markdown(bot_response)
