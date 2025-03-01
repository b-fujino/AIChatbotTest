
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
    return send_from_directory("static", "index13.html")

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
        socketio.emit('ai_response', {'ai_response': ai_response}) #, 'audio': filename})
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
    return jsonify({"info": "Process Succeeded"}), 200


# 音声ファイルを提供するエンドポイント
@app.route("/audio/<filename>")
def get_audio(filename):
    return send_file(os.path.join("output",filename))



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
    # 音声認識の結果を最初に返す
    socketio.emit("SpeechRecognition",{"text": text})
    
    # 続けてストリームで音声合成
    ## まずは openai で応答を取得
    ai_response = get_ai_response(text)
    socketio.emit("AIResponse", {"ai_response": ai_response})

    ## 音声合成
    speaker = request.form["speaker"]
    logging.info(f"AIの応答を取得します。音声合成スピーカーID: {speaker}")    
    

    def generate():
        yield from synthesize_streaming(ai_response, speaker)

    socketio.emit("Streaming", {
        "Response": Response(
            stream_with_context(generate()),
            content_type="application/octet-stream"
        )
    })
    
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


# VoiceVox APIで音声合成を行なう関数
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
        # # 音声ファイルとして保存
        # filename = f"output_{len(messages)}.wav" #合成音声を全部残すならこっちをON
        # #filename = "output.wav" #合成音声を全部残さないならこっちをON
        # file_path = "output/" + filename
        # with open(file_path, 'wb') as f:
        #     f.write(synthesis_response.content)
        # logging.info(f"音声が {filename} に保存されました。")
        # return filename
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

# テキストを句ごとに音声合成してストリーミング
def synthesize_streaming(text, speaker):
    # テキストを句単位に区切る
    logging.debug("テキストを句単位に区切ります。")
    text = preprocess_text(text)
    sentences = text.split("\n")

    # 句ごとに音声合成
    for sentence in sentences:
        if sentence == "": continue
        
        ## クエリ
        query_response = requests.post(
            f'http://localhost:50021/audio_query', 
            params={'text': sentence, 'speaker': speaker}
        )
        if query_response.status_code != 200:
            logging.error(f"Error in audio_query: {query_response.text}")
            return
        
        ## 音声合成
        logging.debug("音声データを生成します。")
        with requests.post(
            f'http://localhost:50021/synthesis', 
            params={'speaker': speaker}, 
            json=query_response.json(), 
            stream=True
        ) as synthesis_response:
            if synthesis_response.status_code != 200:
                logging.error(f"Error in synthesis: {synthesis_response.text}")
                return
            yield "---start---\n".encode("utf-8")
            for chunk in synthesis_response.iter_content(chunk_size=1024):
                logging.info("チャンク生成")
                yield chunk
            yield "---end---\n".encode("utf-8")

            time.sleep(0.2)
        
    


if __name__ == "__main__":
    logging.info("#####アプリケーションを起動します。#####")
    socketio.run(app, debug=True)
