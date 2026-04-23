import streamlit as st
import os
import google.generativeai as genai
import pypandoc
import io
import requests
import sqlite3
import hashlib
import time

# --- 1. የገጽ ቅንብር ---
st.set_page_config(page_title="Meftehe AI App", page_icon="📖", layout="wide")

# --- 2. ኮንፊገሬሽን እና API Keys ---
GITHUB_USER = "israelamare2-cell"
GITHUB_REPO = "meftehe-bot"
RELEASE_TAG = "v1" 
GITHUB_BASE_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/{RELEASE_TAG}/"

GEMINI_API_KEYS_STR = os.getenv('GEMINI_API_KEYS', os.getenv('GEMINI_API_KEY', ''))
API_KEY_LIST = [k.strip() for k in GEMINI_API_KEYS_STR.split(',')] if GEMINI_API_KEYS_STR else []

# --- 3. ዳታቤዝ እና SMART CACHE ---
def init_db():
    conn = sqlite3.connect('meftehe_national_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS gemini_cache 
                 (prompt_hash TEXT PRIMARY KEY, response_text TEXT)''')
    conn.commit()
    conn.close()

def get_cached_response(prompt_text, file_bytes):
    file_hash = hashlib.md5(file_bytes).hexdigest()
    combined = prompt_text + file_hash
    hash_val = hashlib.md5(combined.encode()).hexdigest()
    conn = sqlite3.connect('meftehe_national_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT response_text FROM gemini_cache WHERE prompt_hash=?", (hash_val,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None, hash_val

def save_to_cache(hash_val, response_text):
    conn = sqlite3.connect('meftehe_national_data.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("INSERT OR REPLACE INTO gemini_cache VALUES (?, ?)", (hash_val, response_text))
        conn.commit()
    except:
        pass
    conn.close()

init_db()

# --- 4. መጽሐፍ ከ GitHub የሚያወርድ ---
@st.cache_data
def get_book(grade, subject):
    folder = "books"
    if not os.path.exists(folder): os.makedirs(folder)
    
    file_name = f"grade{grade}_{subject.lower().replace(' ', '_')}.pdf"
    path = os.path.join(folder, file_name)
    
    if os.path.exists(path): return path
    
    url = f"{GITHUB_BASE_URL}{file_name}"
    try:
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                for chunk in r.iter_content(8192): f.write(chunk)
            return path
    except: return None
    return None

# --- 5. መሠረታዊ ዳታዎች ---
ALL_SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology", "General Science", "English", "Social Studies", "Citizenship", "Amharic", "Afaan Oromoo", "Environmental Science", "Moral Education", "PVA", "HPE", "CTE", "Agriculture", "Economics", "IT"]
ALL_ASSESSMENT_TYPES = ["Mid Exam", "Final Exam", "Worksheet", "Quiz", "National Prep", "Model Exam", "Test"]

# --- 6. የአፑ ፊት (User Interface) ---
st.sidebar.title("🌟 መፍትሔ (Meftehe)")
st.sidebar.caption("የመምህራን ረዳት ሞባይል አፕ")

app_lang = st.sidebar.selectbox("🌍 ቋንቋ / Language", ["am", "or", "ti", "so", "en"])
mode = st.sidebar.radio("🛠 ምን ማዘጋጀት ይፈልጋሉ?", ["exam", "note", "lesson", "review"], format_func=lambda x: {"exam": "📝 የፈተና ዝግጅት", "note": "📚 የማስተማሪያ ኖት", "lesson": "📅 ዕለታዊ የትምህርት ዕቅድ", "review": "🔍 የመፅሀፍ ግምገማ"}[x])

st.title({"exam": "📝 የፈተና ዝግጅት", "note": "📚 የማስተማሪያ ኖት", "lesson": "📅 ዕለታዊ የትምህርት ዕቅድ (SMASE)", "review": "🔍 የመፅሀፍ ግምገማ እና ኦዲት"}[mode])

col1, col2 = st.columns(2)
with col1:
    subj = st.selectbox("📚 ትምህርት ይምረጡ", ALL_SUBJECTS)
with col2:
    grd = st.number_input("📖 የክፍል ደረጃ", 1, 12, 7)

chp = st.text_input("📂 ምዕራፍ ይምረጡ (ለምሳሌ፦ Chapter 2 ወይም All)")

tos_config = "auto"
num_sets = 1
lang_output_option = None

if mode == "exam":
    col3, col4, col5 = st.columns(3)
    with col3: as_type = st.selectbox("📝 የፈተና አይነት", ALL_ASSESSMENT_TYPES)
    with col4: diff = st.selectbox("📊 የክብደት ደረጃ", ["Easy", "Medium", "Hard", "MixedFair"])
    with col5: bloom = st.selectbox("🧠 Bloom's Taxonomy", ["Knowledge", "Understanding", "Application", "Analysis", "Evaluation", "Creation", "Mixed"])
    
    is_language = subj.lower() in ["amharic", "english", "afaan oromoo"]
    if is_language:
        lang_output_option = st.radio("📖 ለቋንቋ ትምህርት ምን ይዘጋጅ?", ["PassageOnly", "QuestionOnly", "Both"], format_func=lambda x: {"PassageOnly": "📄 ምንባብ ብቻ", "QuestionOnly": "❓ ጥያቄ ብቻ", "Both": "📑 ምንባብ እና ጥያቄ"}[x])
    else:
        num_sets = st.selectbox("🛡️ የሴት ብዛት", [1, 2, 4])
    
    tos_config = st.text_input("🔢 የጥያቄ ብዛትና መዋቅር (ለምሳሌ፦ ምርጫ=10, እውነት/ሐሰት=5)", value="auto")

elif mode == "lesson":
    pg_type = st.radio("🔢 ገፅ እንዴት መምረጥ ይፈልጋሉ?", ["አንድ ገፅ ብቻ", "የገፅ ክልል (ከ-እስ)"])
    tos_config = st.text_input("🖋 የገፅ ቁጥሩን ይጻፉ", placeholder="ለምሳሌ: 12 ወይም 12-15")

elif mode == "review":
    review_type = st.selectbox("🧐 የግምገማ ዘርፍ ይምረጡ", ["FullAudit", "Pedagogy", "Assessment", "Indigenous", "21stCentury", "Inclusivity"])
    page_range = st.selectbox("📄 ለመገምገም የሚፈልጉትን የገፅ ክልል", ["1-20", "21-50", "51-100", "101-150", "151-200", "All Pages"])
    tos_config = st.text_input("🖋 ልዩ ትኩረት እንዲሰጥበት የሚፈልጉት ነጥብ (ወይም 'auto')")

elif mode == "note":
    note_style = st.selectbox("✨ የኖት አይነት ይምረጡ", ["Objectives", "Comprehensive", "Examples", "Summary", "ReviewQs", "FullPackage"])
    tos_config = st.text_input("📄 ማስታወሻው እንዲያካትት የሚፈልጉት ልዩ ነጥብ", value="auto")

# --- 7. የማመንጨት ሂደት (Generation) ---
if st.button("🚀 አዘጋጅ / Generate", use_container_width=True):
    if not chp or not tos_config:
        st.warning("እባክዎ የምዕራፍ ስም እና ሌሎች ባዶ ቦታዎችን ይሙሉ!")
    else:
        with st.spinner("🔍 መፅሀፉን እያወረድኩ እና AI እያዘጋጀ ነው (ይህ ጥቂት ደቂቃዎች ሊወስድ ይችላል)..."):
            book_path = get_book(grd, subj)
            
            if not book_path:
                st.error("❌ መፅሀፉ በ GitHub Release ላይ አልተገኘም!")
            else:
                lang_map = {
                    'am': "STRICTLY in AMHARIC language.",
                    'or': "STRICTLY in AFAAN OROMOO language using professional terms.",
                    'ti': "STRICTLY in TIGRIGNA language.",
                    'so': "STRICTLY in SOMALI language.",
                    'en': "STRICTLY in ENGLISH language."
                }
                
                target_subject = subj.lower()
                if target_subject == "afaan oromoo": lang_rule = lang_map['or']
                elif target_subject == "amharic": lang_rule = lang_map['am']
                elif target_subject == "english": lang_rule = lang_map['en']
                else: lang_rule = lang_map[app_lang]

                if mode == "lesson":
                    prompt = f"""You are a Professional Curriculum Developer specializing in SMASE (Active Learning).
                    TASK: Create a DAILY LESSON PLAN based on Chapter: {chp} and Page: {tos_config}.
                    STRICT REQUIREMENTS:
                    1. LANGUAGE: {lang_rule}
                    2. PEDAGOGY: Follow SMASE (Active Learning). Ensure it's learner-centered.
                    3. STYLE: Use VERY SHORT BULLET POINTS. NO long sentences.
                    4. FORMAT: Use a Markdown Table for the Teacher/Student activity sections.
                    """
                elif mode == "exam":
                    lang_output_instruction = ""
                    if lang_output_option == "PassageOnly": lang_output_instruction = "IMPORTANT: Provide ONLY the Reading Passage. Do NOT generate any questions."
                    elif lang_output_option == "QuestionOnly": lang_output_instruction = "IMPORTANT: Generate ONLY the questions. Do NOT include the reading passage."
                    elif lang_output_option == "Both": lang_output_instruction = "IMPORTANT: Provide the Reading Passage FIRST, followed by the related questions."

                    prompt = f"""You are an expert Ethiopian National Examiner.
                    STRICT COMPLIANCE:
                    1. SOURCE: Use ONLY the provided PDF. Focus on Chapter: {chp}, Bloom Level: {bloom}, Difficulty: {diff}.
                    2. USER COMMAND: Create exam structure: {tos_config}.
                    3. LANGUAGE: {lang_rule}
                    4. SYMBOLS: ALL math formulas MUST be in standard LaTeX using $inline$ or $$display$$.
                    5. LANGUAGE SUBJECT RULE: {lang_output_instruction}
                    6. OUTPUT: {num_sets} different sets. Include TOS, Exam, and Answer Key formatted cleanly in Markdown."""
                elif mode == "review":
                    prompt = f"""You are a Precise Curriculum Auditor.
                    TASK: Conduct a PAGE-BY-PAGE Audit of the PDF for Page Range: {page_range} / Chapter: {chp}.
                    REVIEW SCOPE: {review_type}
                    FORMATTING: LANGUAGE: {lang_rule}. USER SPECIAL NOTE: {tos_config}. Use Markdown Tables where appropriate."""
                else:
                    prompt = f"Professional Curriculum Expert Note Generation for Chapter {chp}... Style: {note_style}. Language: {lang_rule}. Use standard Markdown and LaTeX for math equations."

                with open(book_path, "rb") as f: file_data = f.read()
                
                cached_response, prompt_hash = get_cached_response(prompt, file_data)
                
                if cached_response:
                    st.success("🚀 መረጃው ከዚህ ቀደም ስለተጠየቀ ከዳታቤዝ (Cache) በፍጥነት ተገኝቷል!")
                    raw_content = cached_response
                else:
                    max_retries = len(API_KEY_LIST) if API_KEY_LIST else 1
                    success = False
                    current_key_index = 0
                    
                    for attempt in range(max_retries * 2):
                        try:
                            if API_KEY_LIST: genai.configure(api_key=API_KEY_LIST[current_key_index % len(API_KEY_LIST)])
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            response = model.generate_content([{"mime_type": "application/pdf", "data": file_data}, prompt])
                            raw_content = response.text.replace("###", "##")
                            save_to_cache(prompt_hash, raw_content)
                            success = True
                            st.success("✅ አዲስ መረጃ በተሳካ ሁኔታ ተዘጋጅቷል!")
                            break
                        except Exception as e:
                            current_key_index += 1
                            time.sleep(2)
                            continue
                    
                    if not success: st.error("⚠️ ይቅርታ፣ የ API መጨናነቅ አጋጥሟል።")

                # --- 8. ወደ Word መቀየር (በ PANDOC - እውነተኛ Word Equations) ---
                if 'raw_content' in locals():
                    with st.expander("👀 የተዘጋጀውን መረጃ እዚህ ይመልከቱ (Markdown & LaTeX)"):
                        st.markdown(raw_content)

                    # ጽሁፉን ከነ ርዕሱ እንደ ማርክዳውን (Markdown) እናዘጋጃለን
                    if mode == "lesson":
                        full_markdown = f"""
# ዕለታዊ የትምህርት ዕቅድ

**መምህር:** እስራኤል አማረ | **ትምህርት ቤት:** የካ ተራራ ቅድመ አንደኛ፣ አንደኛ እና መካከለኛ ደረጃ ትምህርት ቤት
**የትምህርት ዓይነት:** {subj} | **ምዕራፍ:** {chp} | **የክፍል ደረጃ:** {grd} | **የዕለቱ ገፅ:** {tos_config}

---

{raw_content}

---
*መምህር: እስራኤል አማረ _________ | የት/ክፍል ተጠሪ: አስመራወርቅ ሀይሌ _________ | ም/ር/መ/ር: ከበደ ተስፋዪ _________*
"""
                    else:
                        full_markdown = f"# {subj} - Grade {grd} {mode.upper()}\n\n{raw_content}"

                    output_file = f"{mode}_output.docx"
                    
                    # አዲሱ ሚስጥር! Pandoc AIው የጻፈውን ላቴክስ ወደ እውነተኛ Word Equation ይቀይረዋል
                    try:
                        pypandoc.convert_text(full_markdown, 'docx', format='md', outputfile=output_file)
                        
                        with open(output_file, "rb") as fp:
                            st.download_button(
                                label="📥 በ Word ፋይል አውርድ (ከነ እውነተኛ የሒሳብ ፎርሙላዎች)",
                                data=fp,
                                file_name=f"{subj}_{mode}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                type="primary",
                                use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"Pandoc በትክክል አልተጫነም! እባክዎ apt.txt ፈጥረው 'pandoc' መጻፍዎን ያረጋግጡ። ስህተት: {e}")

st.divider()
st.caption("© 2026 Meftehe AI - Built for Ethiopian Teachers")
