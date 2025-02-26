import streamlit as st
from audio_recorder_streamlit import audio_recorder


#  初期化
if "audio_list" not in st.session_state:
    st.session_state.audio_list = []

audio_bytes = False
audio_bytes = audio_recorder()
if audio_bytes:
    st.session_state.audio_list.append(audio_bytes)

with st.sidebar:
    st.write("# 🎙️録った音")
    if st.session_state.audio_list:

        for audio_bytes in st.session_state.audio_list:
            st.audio(audio_bytes, format="audio/wav")
