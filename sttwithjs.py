import streamlit as st
import os
import openai
import base64
import requests
from pathlib import Path
from typing import Optional

# === Whisper APIを叩くための設定 ===
# 例: 環境変数または secrets で管理するのが望ましい
openai.api_key = st.secrets["OPENAI_API_KEY"]  # または os.environ["OPENAI_API_KEY"] etc.

# --- カスタムコンポーネントの最小例 ---
# streamlit はローカルの html を iframe 化して表示できる
# その中で postMessage を受け取り, component_value として Python 側で受け取ることが可能
def audio_recorder_component():
    # st.components.v1.iframe だと双方向通信がやや面倒なので st.components.v1.html を使う方法
    # (ただし、iframe ではなく生の HTML 埋め込みになる点に注意)
    # return_value は postMessage の受信で受け取れる
    component_html = Path("index.html").read_text(encoding="utf-8")
    return_value = st.components.v1.html(
        component_html,
        height=200,
        # 受け取りたいイベントを有効にする
        scrolling=True
    )
    return return_value

# postMessage受信を処理するため、st.experimental_data_editor などのイベントと同様に
# JS側のwindow.parent.postMessage(...)を Python で受け取るためには、
# streamlit >= 1.18 以降なら "components.iframe" か "components.html" の引数に
#  何らかのパラメータを設定する必要があるが、現状はサポートが不安定なので注意。
# 簡易的には hiddenのテキスト入力などにJSで代入させ、Python側でdetectする方法もある。


# --- Whisper API を叩いて音声認識する関数 ---
def transcribe_audio(base64_wav: str) -> str:
    """
    Base64エンコードされたwav音声をOpenAI Whisper APIに送って文字起こしし，結果文字列を返す
    """
    # 一時ファイルとして書き出し
    wav_data = base64.b64decode(base64_wav)
    temp_wav_path = "temp.wav"
    with open(temp_wav_path, "wb") as f:
        f.write(wav_data)

    # Whisper API 呼び出し
    # whisper-1 の transcriptions エンドポイントを叩く
    # python-openai ライブラリでは以下のように呼べます:
    audio_file = open(temp_wav_path, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    text = transcript["text"]

    # 後片付け
    audio_file.close()
    os.remove(temp_wav_path)
    return text


def main():
    st.title("音声認識デモ (スペースキー押下で録音)")

    # カスタムコンポーネントの埋め込み
    st.markdown("### 音声録音")
    component_value = audio_recorder_component()

    # 実際には postMessage を受け取るには、標準のやり方だと st_js_event など使うなど
    # 工夫が必要です。ここでは「component_value に値が入る」と想定したサンプルです。
    # うまく取得できない場合は hidden input や session_state を駆使して実装します。
    #
    # 例: component_value = st.session_state.get("audio_base64", None)

    if "audio_base64" not in st.session_state:
        st.session_state["audio_base64"] = None

    # 下記のように JavaScript から hidden_input に書き込ませる方法で受け取る例
    # (このサンプルでは省略)

    # 「録音が完了し，Base64データを受信したら」文字起こしを実行
    if st.session_state["audio_base64"]:
        # Whisper に送って文字起こし
        text_result = transcribe_audio(st.session_state["audio_base64"])
        st.write("認識結果:")
        st.write(text_result)

        # 一度使ったらクリアしておく（ループ実行で連続取得されないように）
        st.session_state["audio_base64"] = None

if __name__ == "__main__":
    main()

