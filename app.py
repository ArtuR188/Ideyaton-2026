import streamlit as st
import fitz
import os
import re
from groq import Groq
from dotenv import load_dotenv
from streamlit_mic_recorder import mic_recorder

# 1. Налаштування
load_dotenv()
st.set_page_config(page_title="MockIT", page_icon="🎯", layout="wide")

# 2. Стан сесії (пам'ять додатка)
if "results" not in st.session_state: st.session_state.results = {}
if "questions" not in st.session_state: st.session_state.questions = []
if "role" not in st.session_state: st.session_state.role = "Developer"
if "interview_finished" not in st.session_state: st.session_state.interview_finished = False
if "transcript_log" not in st.session_state: st.session_state.transcript_log = []

st.title("🎯 MockIT")
st.subheader("AI-помічник для проведення технічних співбесід")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("Налаштування")
    st.success("✅ Groq підключено")
    available_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    model = st.selectbox("Модель AI", available_models, index=0)
    
    if st.session_state.results:
        st.divider()
        st.metric("Оцінено питань", len(st.session_state.results))
    
    if st.button("🗑️ Очистити все"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# 3. Керування табами - Результати показуються, якщо є результати АБО якщо закінчено
tabs = st.tabs(["📄 Підготовка", "🎤 Проведення", "📊 Результати", "🛰️ Live Co-pilot"])

# ==================== ТАБ 1: ПІДГОТОВКА ====================
with tabs[0]:
    st.header("Підготовка співбесіди")
    col1, col2 = st.columns([2, 1])
    with col1:
        role = st.text_input("Позиція", value="Middle Python Backend Developer")
        level = st.selectbox("Рівень", ["Junior", "Middle", "Senior", "Lead"])
    with col2:
        uploaded_file = st.file_uploader("Завантажте резюме (PDF)", type="pdf")
    
    if st.button("🔥 Проаналізувати CV", type="primary", use_container_width=True):
        if uploaded_file:
            with st.spinner("AI генерує питання..."):
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                cv_text = "".join([p.get_text() for p in doc])
                prompt = f"Ти техлід. Створи 7 питань для {role} ({level}) по резюме: {cv_text[:8000]}. Відповідай нумерованим списком."
                res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
                st.session_state.questions = [q.strip() for q in res.choices[0].message.content.split("\n") if len(q) > 10]
                st.session_state.role, st.session_state.level = role, level
                st.session_state.results = {}
                st.session_state.interview_finished = False
                st.rerun()

# ==================== ТАБ 2: ПРОВЕДЕННЯ ====================
with tabs[1]:
    if not st.session_state.questions:
        st.warning("Завантажте резюме спочатку.")
    else:
        for i, q in enumerate(st.session_state.questions):
            with st.expander(f"Питання {i+1}", expanded=True):
                st.info(q)
                ans = st.text_area("Відповідь", key=f"ans_{i}", value=st.session_state.results.get(i, {}).get("answer", ""))
                
                if st.button("Оцінити відповідь", key=f"btn_{i}"):
                    if ans:
                        with st.spinner("Оцінюю..."):
                            prompt = f"Питання: {q}\nВідповідь: {ans}. Оціни технічну точність українською X/10, вкажи помилки."
                            res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
                            st.session_state.results[i] = {"question": q, "answer": ans, "feedback": res.choices[0].message.content}
                            st.rerun()
                
                if i in st.session_state.results:
                    st.success(st.session_state.results[i]["feedback"])
        
        st.divider()
        if st.button("🏁 ЗАВЕРШИТИ ІНТЕРВ'Ю", type="primary", use_container_width=True):
            st.session_state.interview_finished = True
            st.balloons()
            st.rerun()

# ==================== ТАБ 3: РЕЗУЛЬТАТИ ====================
with tabs[2]:
    st.header("📊 Результати аналітики")
    
    # Показуємо результати, якщо є хоча б один результат АБО натиснута кнопка завершення
    if st.session_state.results or st.session_state.interview_finished:
        if st.session_state.results:
            scores = []
            for res in st.session_state.results.values():
                m = re.search(r'(\d+)/10', res['feedback'])
                scores.append(int(m.group(1)) if m else 5)
            st.bar_chart(scores)
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🤖 Сформувати розгорнутий звіт"):
                ctx = f"Питання та відповіді: {str(st.session_state.results)}. Лог розмови: {str(st.session_state.transcript_log)}"
                res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": f"Напиши фінальний технічний фідбек про кандидата на {st.session_state.role}: {ctx}"}])
                st.info(res.choices[0].message.content)
        with col_b:
            if st.button("⚖️ Фінальний вердикт"):
                res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": f"Чи рекомендуєш ти наймати людину на {st.session_state.role}?"}])
                st.warning(res.choices[0].message.content)
    else:
        st.info("Аналітика з'явиться після оцінки першої відповіді або завершення інтерв'ю.")

# ==================== ТАБ 4: LIVE CO-PILOT ====================
with tabs[3]:
    st.header("🛰️ AI Live Co-pilot")
    audio = mic_recorder(start_prompt="🔴 Слухати", stop_prompt="⬛ Стоп", key='live_rec')
    if audio:
        with st.spinner("Обробка..."):
            with open("t.wav", "wb") as f: f.write(audio['bytes'])
            with open("t.wav", "rb") as f:
                tr = client.audio.transcriptions.create(file=("t.wav", f.read()), model="whisper-large-v3-turbo", response_format="text")
            st.session_state.transcript_log.append(tr)
            st.info(f"Транскрипт: {tr}")
            hint = client.chat.completions.create(model=model, messages=[{"role": "user", "content": f"Кандидат сказав: {tr}. Що запитати далі?"}])
            st.success(hint.choices[0].message.content)
            
    st.divider()
    if st.button("🏁 ЗАВЕРШИТИ ІНТЕРВ'Ю", key="lp_finish", type="primary", use_container_width=True):
        st.session_state.interview_finished = True
        st.balloons()
        st.rerun()

st.divider()
st.caption("MockIT — Проєкт для ідеатону 2026")