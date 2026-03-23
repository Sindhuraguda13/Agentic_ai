import streamlit as st
from langchain_community.llms import Ollama
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
import pyttsx3
import tempfile
import threading
from pydub import AudioSegment
from langchain.memory import ConversationBufferMemory

st.markdown("""
<style>

/* Remove ugly button boxes */
button {
    background: none !important;
    border: none !important;
    padding: 0 !important;
    font-size: 16px !important;
}

/* Align icons properly */
[data-testid="column"] {
    display: flex;
    align-items: center;
}

/* Reduce spacing */
.stButton {
    margin: 0 !important;
}

/* Hover effect */
button:hover {
    opacity: 0.6;
}
/* Remove uploader box border */
[data-testid="stFileUploader"] {
    border: none;
}

/* Make upload button look like icon */
[data-testid="stFileUploader"] button {
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
}

/* Reduce spacing */
[data-testid="stHorizontalBlock"] {
    align-items: center;
}

/* Chat input styling */
textarea {
    border-radius: 12px !important;
}
/* Hide drag-drop text */
[data-testid="stFileUploaderDropzone"] {
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
}

/* Hide text inside uploader */
[data-testid="stFileUploaderDropzone"] div {
    display: none !important;
}

/* Style upload button as icon */
[data-testid="stFileUploader"] button {
    background: none !important;
    border: none !important;
    font-size: 20px !important;
    cursor: pointer;
}

/* Add paperclip icon */
[data-testid="stFileUploader"] button::before {
    content: "📎";
}           

</style>
""", unsafe_allow_html=True)
                    
# -------------------------
# Load Model
# -------------------------
@st.cache_resource
def load_model():
    return Ollama(model="llama3", num_predict=900)

llm = load_model()
from langchain.memory import ConversationBufferMemory

if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory()
memory = ConversationBufferMemory()

# -------------------------
# Text-to-Speech
# -------------------------
engine = pyttsx3.init()

def speak(text):
    st.session_state.speaking = True
    engine.say(text)
    engine.runAndWait()
    st.session_state.speaking = False

# -------------------------
# Session State
# -------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_audio" not in st.session_state:
    st.session_state.last_audio = None

if "speaking" not in st.session_state:
    st.session_state.speaking = False

if "last_response" not in st.session_state:
    st.session_state.last_response = ""

# -------------------------
# UI
# -------------------------
st.title("Local AI Voice Assistant 🤖")

# -------------------------
# Display Chat History
# -------------------------
import pyperclip

for i, msg in enumerate(st.session_state.messages):

    with st.chat_message(msg["role"]):

        col1, col2 = st.columns([10,2])

        # Message
        with col1:
            st.markdown(msg["content"])

        # Icons (side-by-side)
        with col2:
            cols = st.columns(2)

            # Copy
            with cols[0]:
                if st.button("⧉", key=f"copy_{i}", help="Copy"):
                    import pyperclip
                    pyperclip.copy(msg["content"])
                    st.toast("Copied!")

            # Edit (only user)
            if msg["role"] == "user":
                with cols[1]:
                    if st.button("✏", key=f"edit_{i}", help="Edit"):
                        st.session_state.edit_index = i


if "edit_index" in st.session_state:

    idx = st.session_state.edit_index

    new_text = st.text_input(
        "Edit your message",
        value=st.session_state.messages[idx]["content"]
    )

    col_save, col_cancel = st.columns(2)

    with col_save:
        if st.button("Save"):
            st.session_state.messages[idx]["content"] = new_text
            del st.session_state.edit_index
            st.rerun()

    with col_cancel:
        if st.button("Cancel"):
            del st.session_state.edit_index
            st.rerun()

# -------------------------
# Input Row
# -------------------------
col1, col2 = st.columns([8,1])
# FIRST create columns
col_file, col_input, col_mic = st.columns([1,8,1])
# 📎 File Upload
with col_file:
    uploaded_file = st.file_uploader(
        "",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        label_visibility="collapsed"
    )

with col1:
    prompt = st.chat_input("Ask something...", key="chat_input")

with col2:
    audio = mic_recorder(
        start_prompt="🎤",
        stop_prompt="⏹",
        key="mic"
    )

# -------------------------
# Speech to Text
# -------------------------
def speech_to_text(audio_bytes):
    recognizer = sr.Recognizer()

    temp_webm = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    temp_webm.write(audio_bytes)
    temp_webm.close()

    webm_file = temp_webm.name
    wav_file = webm_file.replace(".webm", ".wav")

    sound = AudioSegment.from_file(webm_file, format="webm")
    sound.export(wav_file, format="wav")

    with sr.AudioFile(wav_file) as source:
        audio_data = recognizer.record(source)

    try:
        return recognizer.recognize_google(audio_data)
    except:
        return None

# -------------------------
# Handle Voice Input (FIXED)
# -------------------------
if audio and audio["bytes"] != st.session_state.last_audio:

    st.session_state.last_audio = audio["bytes"]

    text = speech_to_text(audio["bytes"])

    if text:
        prompt = text
        st.success(f"Recognized: {text}")

# -------------------------
# Process Message
# -------------------------
if prompt:

    # Save user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    # Build conversation context (IMPORTANT FIX)
    # Save user input to memory
    st.session_state.memory.chat_memory.add_user_message(prompt)

    # Get full memory
    chat_history = st.session_state.memory.chat_memory.messages

    conversation = ""
    for msg in chat_history:
        role = "User" if msg.type == "human" else "Assistant"
        conversation += f"{role}: {msg.content}\n"

    conversation += "Assistant:"

    # Streaming response
    response_stream = llm.stream(conversation)

    response_text = ""

    with st.chat_message("assistant"):
        placeholder = st.empty()

        for chunk in response_stream:
            response_text += chunk
            placeholder.write(response_text)

   # Save response (UI)
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )

    # ✅ ADD THIS (IMPORTANT)
    st.session_state.memory.chat_memory.add_ai_message(response_text)

    # Store last response
    st.session_state.last_response = response_text

    # Speak
    threading.Thread(target=speak, args=(response_text,)).start()

# -------------------------
# Speech Controls
# -------------------------
col1, col2 = st.columns([1,1])

with col1:
    if st.button("⏹ Stop"):
        engine.stop()

with col2:
    if st.button("▶ Resume"):
        if st.session_state.last_response:
            threading.Thread(
                target=speak,
                args=(st.session_state.last_response,)
            ).start()