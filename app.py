
import streamlit as st

st.title('インタフェースを整える')

# 初期化
allinputs = ""

# テキストを入力
input_text = st.text_input('Input a text')
st.write('You input:', input_text)

# 過去の入力も表示
allinputs += input_text+"  \n" # 改行するにはスペース2つと改行文字を入れる 
st.write('All inputs:', allinputs)
