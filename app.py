import os

import openai
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gpt-6.1-sol"
MAX_CHARS = 5000

# 언어를 추가하려면 여기에 한 줄만 추가하면 됩니다.
LANGUAGES = {
    "영어": "English",
    "일본어": "Japanese",
    "베트남어": "Vietnamese",
}

SYSTEM_PROMPT = (
    "You are a professional translator. Detect the source language automatically "
    "and translate the user's text into {target_language}. "
    "Output only the translated text without explanations."
)


def get_setting(name: str, default: str | None = None) -> str | None:
    """환경변수(.env) → st.secrets 순서로 설정값을 찾는다."""
    value = os.getenv(name)
    if not value:
        try:
            value = st.secrets.get(name)
        except Exception:  # secrets.toml이 없으면 예외가 발생한다.
            value = None
    value = value.strip() if isinstance(value, str) else None
    return value or default


def translate(text: str, target_language: str) -> str:
    """text를 target_language(영어 이름)로 번역한다."""
    client = get_client()
    response = client.chat.completions.create(
        model=get_setting("OPENAI_MODEL", DEFAULT_MODEL),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(target_language=target_language)},
            {"role": "user", "content": text},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def get_client() -> openai.OpenAI:
    return openai.OpenAI(api_key=get_setting("OPENAI_API_KEY"), timeout=60)


def error_message(e: Exception) -> str:
    """OpenAI 예외를 사용자용 한국어 메시지로 바꾼다. (키·상세 응답은 노출하지 않음)"""
    if isinstance(e, openai.AuthenticationError):
        return "API 키가 올바르지 않습니다. OPENAI_API_KEY 값을 확인해 주세요."
    if isinstance(e, openai.NotFoundError):
        return "번역 모델을 찾을 수 없습니다. OPENAI_MODEL 값을 확인해 주세요."
    if isinstance(e, openai.RateLimitError):
        return "요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."
    if isinstance(e, (openai.APIConnectionError, openai.APITimeoutError)):
        return "AI 서버에 연결할 수 없습니다. 인터넷 연결을 확인하고 다시 시도해 주세요."
    return "번역 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


# ---------------- 화면 ----------------
def start_translation() -> None:
    """번역하기 클릭 시 호출. 번역이 끝날 때까지 버튼을 잠가 중복 요청을 막는다."""
    st.session_state["busy"] = True
    st.session_state.pop("result", None)
    st.session_state.pop("notice", None)


def run_translation(text: str, language: str) -> None:
    """입력을 검사하고 번역한다. 결과나 안내 메시지는 session_state에 저장한다."""
    if not text.strip():
        st.session_state["notice"] = ("warning", "번역할 글을 입력해 주세요.")
    elif len(text) > MAX_CHARS:
        st.session_state["notice"] = (
            "warning",
            f"글이 너무 깁니다. {MAX_CHARS:,}자 이하로 줄여 주세요. (현재 {len(text):,}자)",
        )
    elif not get_setting("OPENAI_API_KEY"):
        st.session_state["notice"] = (
            "error",
            "OPENAI_API_KEY가 설정되지 않았습니다. .env 파일 또는 Secrets를 확인해 주세요.",
        )
    else:
        try:
            with st.spinner("번역 중..."):
                translated = translate(text, LANGUAGES[language])
        except openai.OpenAIError as e:
            st.session_state["notice"] = ("error", error_message(e))
        except Exception:
            st.session_state["notice"] = ("error", "번역 중 알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
        else:
            if translated:
                st.session_state["result"] = {"language": language, "text": translated}
            else:
                st.session_state["notice"] = ("warning", "번역 결과가 비어 있습니다. 다시 시도해 주세요.")


st.set_page_config(page_title="AI 번역기", page_icon="🌐", layout="wide")

st.title("🌐 AI 번역기")
st.caption("글을 입력하고 언어를 고르면 번역해 드려요 · 원문 언어는 자동으로 감지합니다")

busy = st.session_state.get("busy", False)
left, right = st.columns(2, gap="large")

with left:
    with st.container(border=True):
        # max_chars를 쓰면 5,000자를 넘는 글을 붙여넣을 때 글 전체가 조용히 무시되므로,
        # 길이 검사는 번역 버튼을 눌렀을 때 직접 한다.
        text = st.text_area(
            "번역할 글",
            height=260,
            placeholder=f"여기에 번역할 글을 입력하세요. (최대 {MAX_CHARS:,}자)",
        )
        count_color = "red" if len(text) > MAX_CHARS else "gray"
        st.caption(f":{count_color}[{len(text):,} / {MAX_CHARS:,}자]")
        language = st.radio("번역할 언어", list(LANGUAGES), horizontal=True)
        st.button(
            "번역 중..." if busy else "번역하기",
            type="primary",
            use_container_width=True,
            disabled=busy,
            on_click=start_translation,
            key="translate_button",
        )

with right:
    with st.container(border=True):
        st.markdown("**번역 결과**")

        if busy:
            try:
                run_translation(text, language)
            finally:
                st.session_state["busy"] = False
            st.rerun()  # 버튼 잠금을 풀고 결과를 표시한다.

        notice = st.session_state.get("notice")
        if notice:
            kind, message = notice
            (st.warning if kind == "warning" else st.error)(message)

        # 다시 그려져도 마지막 번역 결과를 유지한다.
        result = st.session_state.get("result")
        if result:
            st.caption(f"🌐 {result['language']}로 번역 · 오른쪽 위 버튼으로 복사")
            st.code(result["text"], language=None, wrap_lines=True)
            if result["language"] != language:
                st.info(f"언어를 {language}로 바꾸셨어요. **번역하기**를 누르면 다시 번역합니다.")
        elif not notice:
            st.caption("번역 결과가 여기에 표시됩니다.")
