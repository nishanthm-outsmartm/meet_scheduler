import io
import json
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import speech_recognition as sr
except ImportError:  # feature still works without mic
    sr = None

try:
    from streamlit_mic_recorder import mic_recorder
except ImportError:
    mic_recorder = None

from utils.groq_interface import extract_meeting_info
from utils.scheduler import schedule_meetings

st.set_page_config(page_title="AI Meeting Scheduler", layout="wide")

LOG_FILE = Path("logs/meeting_logs.json")
THEMES = {
    "Dark": {
        "bg": "#0d1117",
        "card": "#161b22",
        "text": "#F0F6FC",
        "accent": "#3fb950",
    },
    "Light": {
        "bg": "#f5f7fb",
        "card": "#ffffff",
        "text": "#0b1a33",
        "accent": "#2563eb",
    },
}

LANGUAGE_OPTIONS = {
    "English (US)": "en-US",
    "English (India)": "en-IN",
    "English (UK)": "en-GB",
    "Hindi": "hi-IN",
}


def init_state():
    defaults = {
        "prompt_text": "",
        "parsed_result": None,
        "schedule_status": None,
        "theme": "Dark",
        "voice_language": "English (India)",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def inject_theme(theme_name: str):
    colors = THEMES[theme_name]
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {colors['bg']};
            color: {colors['text']};
        }}
        .themed-card {{
            background: {colors['card']};
            padding: 1.5rem;
            border-radius: 1.2rem;
            box-shadow: 0 15px 35px rgba(0,0,0,0.15);
        }}
        .themed-card h3 {{
            color: {colors['text']};
            margin-bottom: 0.5rem;
        }}
        .accent-text {{
            color: {colors['accent']};
            font-weight: 600;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_meeting_logs():
    if not LOG_FILE.exists():
        return []
    try:
        return json.loads(LOG_FILE.read_text())
    except json.JSONDecodeError:
        return []


def build_rsvp_dataframe(logs):
    rows = []
    for entry in logs:
        for email in entry.get("emails", []):
            rsvp_entry = entry.get("rsvp", {}).get(email, "Pending")
            status = rsvp_entry
            reason = ""
            if isinstance(rsvp_entry, dict):
                status = rsvp_entry.get("status", "Declined")
                reason = rsvp_entry.get("reason", "")
            rows.append(
                {
                    "Email": email,
                    "Date": entry.get("date"),
                    "Time": entry.get("time"),
                    "RSVP": status,
                    "Reason": reason,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["Email", "Date", "Time", "RSVP", "Reason"])
    return pd.DataFrame(rows)


def transcribe_audio(payload):
    if not sr:
        raise RuntimeError("SpeechRecognition not installed")
    recognizer = sr.Recognizer()
    audio_bytes = payload.get("bytes")
    sample_rate = payload.get("sample_rate") or payload.get("sampleRate")
    sample_width = payload.get("sample_width") or payload.get("sampleWidth") or 2
    if not audio_bytes or not sample_rate:
        raise ValueError("Microphone payload missing audio data or sample rate")

    audio_data = sr.AudioData(audio_bytes, sample_rate=int(sample_rate), sample_width=int(sample_width))
    language_code = LANGUAGE_OPTIONS.get(st.session_state.get("voice_language"), "en-US")
    return recognizer.recognize_google(audio_data, language=language_code)


def render_sidebar():
    with st.sidebar:
        st.image(
            "https://img.icons8.com/?size=128&id=104700&format=png",
            width=64,
        )
        st.header("Controls")
        theme_choice = st.radio("Theme", list(THEMES.keys()), key="theme", horizontal=True)
        st.caption("Toggle between dark and light experiences.")
        st.selectbox("Voice recognition language", list(LANGUAGE_OPTIONS.keys()), key="voice_language")
        st.markdown("---")
        st.markdown(
            """**Tips**
            - Use the mic to dictate scheduling needs.
            - Keep the RSVP server (Flask) running so guests can respond.
            - Monitor responses in the *RSVP Dashboard* tab."""
        )


def render_prompt_section():
    col_input, col_voice = st.columns([2.2, 1])
    with col_input:
        st.text_area(
            "📝 Scheduling request",
            height=180,
            key="prompt_text",
        )
    with col_voice:
        st.markdown("#### 🎙️ Voice input")
        if mic_recorder and sr:
            st.caption("Record a quick request and we'll transcribe it for you.")
            audio_payload = mic_recorder(
                start_prompt="Start Recording",
                stop_prompt="Stop & Use",
                just_once=True,
                use_container_width=True,
                key="mic",
            )
            if audio_payload:
                try:
                    transcript = transcribe_audio(audio_payload)
                    st.session_state.prompt_text = transcript
                    st.success("Voice transcription captured. Feel free to edit before submitting.")
                    st.experimental_rerun()
                except sr.UnknownValueError:
                    st.warning("Couldn't understand the audio. Try speaking closer to the mic or switch the language setting.")
                except Exception as exc:
                    st.error(f"Voice transcription failed: {exc}")
        else:
            st.caption("Install SpeechRecognition and streamlit-mic-recorder to enable voice input.")


def handle_prompt_submission():
    prompt = st.session_state.prompt_text.strip()
    if not prompt:
        st.error("Please enter or dictate a scheduling prompt.")
        return

    with st.spinner("Parsing your request with Groq..."):
        result = extract_meeting_info(prompt)

    if result.get("error"):
        st.error(f"Parsing Error: {result['error']}")
        st.session_state.parsed_result = None
        return

    st.session_state.parsed_result = result
    st.success("Prompt parsed successfully. Review the details below before sending invites.")


def render_parsed_result():
    result = st.session_state.parsed_result
    if not result:
        return

    st.markdown("### Parsed Details")
    cols = st.columns(3)
    cols[0].metric("🗓 Date", result.get("date", "-"))
    cols[1].metric("⏰ Time", result.get("time", "-"))
    cols[2].metric("📅 Days", result.get("days", "-"))
    st.markdown(
        f"**Invites:** `{' , '.join(result.get('emails', [])) or 'None detected'}`"
    )


def send_invites():
    result = st.session_state.parsed_result
    if not result:
        st.error("Parse a prompt before sending invites.")
        return

    try:
        with st.spinner("Sending meeting invites with RSVP links..."):
            schedule_meetings(
                result.get("emails", []),
                result.get("date"),
                result.get("time"),
                int(result.get("days", 1)),
            )
        st.success("✅ Meeting invites sent successfully. Track RSVPs in the dashboard tab.")
        st.session_state.schedule_status = "success"
    except Exception as exc:
        st.error(f"Scheduling error: {exc}")
        st.session_state.schedule_status = "error"


def render_rsvp_dashboard():
    st.markdown("### RSVP Dashboard")
    logs = load_meeting_logs()
    if not logs:
        st.info("No meetings recorded yet. Send your first invite to populate this view.")
        return

    df = build_rsvp_dataframe(logs)
    status_counts = df["RSVP"].value_counts().to_dict()
    metrics = st.columns(3)
    metrics[0].metric("Total Invites", len(df))
    metrics[1].metric("Accepted", status_counts.get("Accepted", 0))
    metrics[2].metric("Pending", status_counts.get("Pending", 0))

    st.dataframe(df, use_container_width=True)


def main():
    init_state()
    render_sidebar()
    inject_theme(st.session_state.theme)

    tab_compose, tab_dashboard = st.tabs(["Compose Request", "RSVP Dashboard"])

    with tab_compose:
        st.title("🤖 AI Meeting Scheduler")
        st.caption("Use natural language or your voice to plan meetings, send RSVP-enabled invites, and monitor responses in real time.")
        render_prompt_section()
        st.markdown("---")
        col_actions = st.columns([1, 1])
        with col_actions[0]:
            if st.button("🔍 Parse with Groq", use_container_width=True):
                handle_prompt_submission()
        with col_actions[1]:
            if st.button("✉️ Send Invites", use_container_width=True):
                send_invites()

        render_parsed_result()

    with tab_dashboard:
        render_rsvp_dashboard()


if __name__ == "__main__":
    main()
