from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import os
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit
import threading
import requests
import json
import time
import logging

#　環境変数の読み込み
load_dotenv()

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

#--------------------------------------------------
#loggingの設定
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    filename="app.log",
    encoding="utf-8"
)
#--------------------------------------------------


# ルートパスへのリクエストを処理する
@app.route("/")
def index():
    logging.info("index.html を返します。")
    return send_from_directory("static", "index11.html")

# /upload へのリクエストを処理する
@app.route("/upload", methods=["POST"])
def upload_audio():
    logging.info("音声ファイルをアップロードします。")
    if "file" not in request.files:
        logging.error("No audio file provided")
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["file"]
    audio_path = os.path.join("uploads", f"input_{len(messages)}.wav")
    audio_file.save(audio_path)
    logging.info(f"Saved audio file to {audio_path}")

    # 音声認識
    r = sr.Recognizer()
    start_time = time.time()
    with sr.AudioFile(audio_path) as source:
        audio = r.record(source)
        text = r.recognize_google(audio, language="ja-JP")
    logging.info(f"音声認識結果: {text}")
    logging.info(f"音声認識時間: {time.time() - start_time} [sec]")

    # 音声認識の結果を最初に返す
    response = jsonify({"text": text})
    
    # 別スレッドでAIの応答を取得
    speaker = request.form["speaker"]
    logging.info(f"AIの応答を取得します。音声合成スピーカーID: {speaker}")
    threading.Thread(target=get_ai_response, args=(text, speaker)).start()
    
    return response

# 音声ファイルを提供するエンドポイント
@app.route("/audio/<filename>")
def get_audio(filename):
    logging.info(f"音声ファイル {filename} を返します。")
    return send_file(os.path.join("output",filename))

# VoiceVoxのSpeakerIDリストを取得するエンドポイント
@app.route("/speaker_ids")
def get_speaker_ids():
    url = "http://localhost:50021/speakers"  # VOICEVOX APIのエンドポイント
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
    filename = synthesize_voice(text, speaker)
    return jsonify({"audio": filename})
#--------------------------------------------------

# AIの応答を取得する関数 
def get_ai_response(text, speaker):
    
    # 現在の時刻取得
    start = time.time()

    # OpenAIのAPIを呼び出してAIの応答を取得
    client = OpenAI()
    messages.append({"role": "user", "content": text})
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    ai_response = completion.choices[0].message.content
    messages.append({"role": "assistant", "content": ai_response})
    logging.info(f"AIの応答: {ai_response}")

    # 処理時間の計算
    ai_time = time.time() - start
    logging.info(f"AIレスポンス時間: {ai_time} [sec]")

    # 音声合成
    filename = synthesize_voice(ai_response, speaker)

    # 処理時間の計算
    voice_time = time.time() - start - ai_time
    logging.info(f"音声合成時間: {voice_time} [sec]")
    
    # WebSocketを通じてクライアントに通知
    socketio.emit('ai_response', {'ai_response': ai_response, 'audio': filename})



# 音声合成を行なう関数
def synthesize_voice(text, speaker):
    # 1. テキストから音声合成のためのクエリを作成
    query_payload = {'text': text, 'speaker': speaker}
    query_response = requests.post(f'http://localhost:50021/audio_query', params=query_payload)

    if query_response.status_code != 200:
        logging.error(f"Error in audio_query: {query_response.text}")
        print(f"Error in audio_query: {query_response.text}")
        return

    query = query_response.json()

    # 2. クエリを元に音声データを生成
    synthesis_payload = {'speaker': speaker}
    synthesis_response = requests.post(f'http://localhost:50021/synthesis', params=synthesis_payload, json=query)

    if synthesis_response.status_code == 200:
        # 音声ファイルとして保存
        filename = f"output_{len(messages)}.wav"
        file_path = "output/" + filename
        with open(file_path, 'wb') as f:
            f.write(synthesis_response.content)
        logging.info(f"音声が {filename} に保存されました。")
        return filename
    else:
        logging.error(f"Error in synthesis: {synthesis_response.text}")
        return None


if __name__ == "__main__":
    logging.info("#####アプリケーションを起動します。#####")
    socketio.run(app, debug=True)
