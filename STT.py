from openai import OpenAI
from dotenv import load_dotenv
import streamlit as st
from audio_recorder_streamlit import audio_recorder
from tempfile import NamedTemporaryFile

# 環境ファイルからAPIキーを読み込む
load_dotenv()

st.title("音声認識アプリ")

# 音声録音
audio_bytes = audio_recorder(pause_threshold=30)

if audio_bytes:
    #もしデータの量があまりに少ないなら
    if len(audio_bytes) < 1000:
        st.write("音声データが短すぎます")
        st.stop()

    # OpenAI に送信
    client = OpenAI()
    with NamedTemporaryFile(delete=True, suffix=".wav") as f:
        f.write(audio_bytes)
        f.flush()
        with open(f.name, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )        
    st.write(transcription.text)
    
