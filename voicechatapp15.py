
from flask import Flask, request, Response, jsonify, send_from_directory, send_file, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv
import requests
import time
import logging
import re
from pydub import AudioSegment
from io import BytesIO

#　環境変数の読み込み
load_dotenv()

# VoiceVox APIのエンドポイント
VOICEVOX_API_URL = "http://localhost:50021"


# Flaskアプリケーションの作成
app = Flask(__name__, static_folder="static")  

# CORSの設定
CORS(app)

# Socket.IOの設定
socketio = SocketIO(app)

# 会話ログを保持する変数
messages = [
    {"role": "system", "content": "You are a helpful assistant."}
]

#loggingの設定
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    filename="app.log",
    encoding="utf-8"
)

#--------------------------------------------------
# Flaskのエンドポイントの作成
#--------------------------------------------------

# ルートパスへのリクエストを処理する
@app.route("/")
def index():
    logging.info("index.html を返します。")
    return send_from_directory("static", "index15.html")

# VoiceVoxのSpeakerIDリストを取得するエンドポイント
@app.route("/speaker_ids")
def get_speaker_ids():
    url = f"{VOICEVOX_API_URL}/speakers"  # VOICEVOX APIのエンドポイント
    try:
        response = requests.get(url)
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify([])

    voicevox_speakers = []
    if response.status_code == 200:
        speakers = response.json()
        for speaker in speakers:
            name = speaker['name']
            style_names = [style['name'] for style in speaker['styles']]
            style_ids = [style['id'] for style in speaker['styles']]
            for style_id, style_name in zip(style_ids, style_names):
                voicevox_speakers.append(f"<option value={style_id}>Speaker: {name}, {style_name} </option>")
        logging.info("speaker_ids を取得しました。")
        return jsonify(voicevox_speakers)
    else:
        logging.error(f"Error: {response.status_code}")
        return jsonify([])    

# VoiceVoxの音声テストを行うエンドポイント
@app.route("/speaker_test" , methods=["POST"])
def speaker_test():
    speaker = request.json["speaker"]
    text = "こんにちは．初めまして．何かお手伝いできることはありますか？"
    synthesize_response = synthesize_voice(text, speaker)

    # 合成した音声をmp3化
    if synthesize_response is None: return jsonify({"error": "Failed to synthesize voice"}), 400
    audio = AudioSegment.from_file(BytesIO(synthesize_response.content), format="wav")
    mp3_data  = BytesIO()
    audio.export(mp3_data , format="mp3")
    mp3_data .seek(0)  

    # mp3データをWebSocketを通じてクライアントに通知
    socketio.emit('play_audio', {'audio': mp3_data.getvalue()})
    return jsonify({"info": "Speaker Test Process Succeeded"}), 200


# /upload へのリクエストを処理する
@app.route("/upload", methods=["POST"])
def upload_audio():
    # uploads ディレクトリがなければ作成
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    # uploads ディレクトリにファイルがあれば削除
    else:
        for file in os.listdir("uploads"):
            os.remove(os.path.join("uploads", file))

    # 音声ファイルをアップロード
    if "file" not in request.files:
        logging.error("No audio file provided")
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["file"]
    audio_path = os.path.join("uploads", f"input_{len(messages)}.wav") #Uploadされたファイルを残すならこっちをOn
    audio_file.save(audio_path)

    # 音声認識
    text = recognize_speech(audio_path)
    ## 音声認識の結果をWebSocketを通じてクライアントに通知
    if text:
        socketio.emit("SpeechRecognition",{"text": text})
    else:
        return jsonify({"error": "Failed to recognize speech"}), 400    
    
    # AIの応答を取得
    ai_response = get_ai_response(text)
    ## WebSocketを通じてクライアントに通知
    if ai_response:
        socketio.emit('ai_response', {'ai_response': ai_response}) 
    else:
        return jsonify({"error": "Failed to get AI response"}), 400
    
    # AIの応答から音声合成
    speaker = request.form["speaker"]
    synthesize_response = synthesize_voice(ai_response, speaker)


    # 合成した音声をmp3化
    if synthesize_response is None: return jsonify({"error": "Failed to synthesize voice"}), 400
    audio = AudioSegment.from_file(BytesIO(synthesize_response.content), format="wav")
    mp3_data  = BytesIO()
    audio.export(mp3_data , format="mp3")
    mp3_data .seek(0)  

    # mp3データをWebSocketを通じてクライアントに通知
    socketio.emit('play_audio', {'audio': mp3_data.getvalue()})

    return jsonify({"info": "Uploard Process Succeeded"}), 200



# streaming処理するエンドポイント
@app.route("/streaming", methods=["POST"])
def streaming():
    # uploads ディレクトリがなければ作成
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    # uploads ディレクトリにファイルがあれば削除
    else:
        for file in os.listdir("uploads"):
            os.remove(os.path.join("uploads", file))

    # 音声ファイルをアップロード
    if "file" not in request.files:
        logging.error("No audio file provided")
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["file"]
    audio_path = os.path.join("uploads", "input.wav") #Uploadされたファイルを残さないならこっちをOn
    audio_file.save(audio_path)

    # 音声認識
    text = recognize_speech(audio_path)
    ## 音声認識の結果をWebSocketを通じてクライアントに通知
    if text:
        socketio.emit("SpeechRecognition",{"text": text})
    else:
        return jsonify({"error": "Failed to recognize speech"}), 400    
    

    # AIの応答を句単位でストリームするとともに．句単位で音声合成もしていく
    speaker = request.form["speaker"]
    socketio.emit('ai_stream', {'ai_stream': "---Start---"}) # 開始を通知
    for sentence in generate_ai_response(text):
        ## WebSocketを通じてクライアントに通知
        if sentence:
            # 音声合成
            synthesize_response=synthesize_voice(sentence, speaker)
            if synthesize_response is None: return jsonify({"error": "Failed to synthesize voice"}), 400
            ## 合成した音声をmp3化
            audio = AudioSegment.from_file(BytesIO(synthesize_response.content), format="wav")
            mp3_data  = BytesIO()
            audio.export(mp3_data , format="mp3")
            mp3_data .seek(0)
            ## mp3データをWebSocketを通じてクライアントに通知 ここでうまくキューに入れて連続再生させたい
            socketio.emit('ai_stream', {'audio': mp3_data.getvalue(), 'sentens': sentence})
            #socketio.emit('ai_stream', {'ai_stream': sentence})
            ## 0.5秒の無音を入れる．これで句の切り分けが聞きやすくなると思う．
            silent_audio = AudioSegment.silent(duration=500)
            mp3_data  = BytesIO()
            silent_audio.export(mp3_data , format="mp3")
            mp3_data .seek(0)
            socketio.emit('ai_stream', {'audio': mp3_data.getvalue(), 'sentens': "---silent---"}) 
        else:
            return jsonify({"error": "Failed to get AI response"}), 400
    socketio.emit('ai_stream', {'ai_stream': "---End---"}) # 終了を通知

    
    return jsonify({"info": "Process Succeeded"}), 200


#--------------------------------------------------
# Flaskの各エンドポイント内の処理関数
#--------------------------------------------------
# 音声認識を行う関数
def recognize_speech(audio_path):
    r = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = r.record(source)
        text = r.recognize_google(audio, language="ja-JP")
    return text

# OpenAIのAPIを呼び出してAIの応答を取得する関数
def get_ai_response(text):
    client = OpenAI()
    messages.append({"role": "user", "content": text})
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    ai_response = completion.choices[0].message.content
    messages.append({"role": "assistant", "content": ai_response})
    logging.info(f"AIの応答: {ai_response}")
    return ai_response

# OpenAIのAPIを呼び出してAIの応答をストリームで生成する関数
def generate_ai_response(text):
    client = OpenAI()
    messages.append({"role": "user", "content": text})
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream = True
    )

    sentens = "" # 句を構成するためのバッファ
    message = "" # プロンプトに含めるためにチャンクを結合させるためのためのバッファ
    for chunk in completion:
        # きちんとしたチャンクが帰ってきているかのチェック
        if "choices" in chunk.to_dict() and len(chunk.choices) > 0: #to_dict：辞書型に変えないと”choices”が見つからないようなので
            content  = chunk.choices[0].delta.content
            if content:
                message += content
                # 1文字ずつ取り出してチェックする
                for i in range(len(content)):
                    char = content[i]
                    sentens += char
                    if char in "。．.？?！!\n": #今見ているのが区切り文字だった場合
                        if i < len(content)-1: # i が最後の文字でないなら，次の文字をチェック
                            if content[i+1] not in "。．.？?！!\n": #次の文字が区切り文字でないならyield
                                logging.debug(f"句: {sentens}")
                                yield sentens
                                sentens = ""
                            else: #もし次の文字が区切り文字なら，現時点の区切り文字はスルー
                                continue
                        else: #iが最後の文字の場合，現時点でyield
                            logging.debug(f"句: {sentens}")
                            yield sentens
                            sentens = ""
    # 最後の句を返す
    if sentens:
        yield sentens
    
    # message をmessagesに追加
    messages.append({"role": "assistant", "content": message})
    logging.info(f"AIの応答: {message}")



# VoiceVox APIで音声合成を行なう関数
def synthesize_voice(text, speaker):
    # 1. テキストから音声合成のためのクエリを作成
    query_payload = {'text': text, 'speaker': speaker}
    query_response = requests.post(f'{VOICEVOX_API_URL}/audio_query', params=query_payload)

    if query_response.status_code != 200:
        logging.error(f"Error in audio_query: {query_response.text}")
        print(f"Error in audio_query: {query_response.text}")
        return

    query = query_response.json()

    # 2. クエリを元に音声データを生成
    synthesis_payload = {'speaker': speaker}
    synthesis_response = requests.post(f'{VOICEVOX_API_URL}/synthesis', params=synthesis_payload, json=query)

    if synthesis_response.status_code == 200:
        logging.info("音声データを生成しました。")
        return synthesis_response
    else:
        logging.error(f"Error in synthesis: {synthesis_response.text}")
        return None


# テキストを句単位に区切る
def preprocess_text(text):
    # テキストの前処理
    text = re.sub(r"[。．.]", "。\n", text)
    text = re.sub(r"[？?]", "？\n", text)
    text = re.sub(r"[！!]", "！\n", text)
    return text


if __name__ == "__main__":
    logging.info("#####アプリケーションを起動します。#####")
    socketio.run(app, debug=True)
