import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import io
import requests

# 1. የአፑ መለያ ስም እና ምልክት
st.set_page_config(page_title="Meftehe AI App", page_icon="📖", layout="centered")

# 2. የ AI እና የ GitHub ቅንብር (Configuration)
# ማሳሰቢያ፡ GEMINI_API_KEY ኮምፒውተርህ ወይም ሰርቨርህ ላይ መመዝገብ አለበት
API_KEY = os.getenv('GEMINI_API_KEY')
GITHUB_URL = "https://github.com/israelamare2-cell/meftehe-bot/releases/download/v1/"

if API_KEY:
    genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')
# 3. መጽሐፍ ከ GitHub የሚያወርድ ተግባር (Function)
def get_book(grade, subject):
    folder = "downloaded_books"
    if not os.path.exists(folder): os.makedirs(folder)
    
    file_name = f"grade{grade}_{subject.lower().replace(' ', '_')}.pdf"
    path = os.path.join(folder, file_name)
    
    if os.path.exists(path): return path
    
    try:
        r = requests.get(f"{GITHUB_URL}{file_name}", stream=True)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                for chunk in r.iter_content(8192): f.write(chunk)
            return path
    except: return None
    return None

# 4. የአፑ ፊት (User Interface)
st.title("🌟 መፍትሔ (Meftehe) AI")
st.subheader("የመምህራን ረዳት ሞባይል አፕ")

menu = st.sidebar.selectbox("ምን መስራት ይፈልጋሉ?", ["ፈተና አዘጋጅ", "ኖት አውጣ", "መጽሐፍ ገምግም"])

subj = st.selectbox("ትምህርት", ["Mathematics", "Physics", "Chemistry", "Biology", "English"])
grd = st.number_input("ክፍል", 1, 12, 7)
chp = st.text_input("ምዕራፍ (ለምሳሌ: Chapter 2)")

if st.button(f"🚀 {menu} ይጀምሩ"):
    if not chp:
        st.warning("እባክዎ የምዕራፍ ስም ያስገቡ")
    else:
        with st.spinner("AIው መጽሐፉን እያነበበ ነው..."):
            book_path = get_book(grd, subj)
            if book_path:
                # ለ AI የሚሰጥ ትዕዛዝ (Prompt)
                instruction = f"Role: Expert Teacher. Task: {menu}. Grade: {grd}, Subject: {subj}, Topic: {chp}. Language: Amharic."
                
                with open(book_path, "rb") as f:
                    response = model.generate_content([{"mime_type": "application/pdf", "data": f.read()}, instruction])
                
                st.success("ተጠናቋል!")
                result_text = st.text_area("የተዘጋጀው ውጤት፦", value=response.text, height=300)
                
                # ወደ Word መለወጫ
                doc = Document()
                doc.add_heading(f"Meftehe AI - {menu}", 0)
                doc.add_paragraph(result_text)
                target = io.BytesIO()
                doc.save(target)
                st.download_button("📥 በ Word ፋይል አውርድ", target.getvalue(), f"{menu}.docx")
            else:
                st.error("ይቅርታ፣ ይህ መጽሐፍ አልተገኘም። እባክዎ GitHub ላይ መኖሩን ያረጋግጡ።")

st.divider()
st.caption("© 2026 Meftehe AI - Built for Ethiopian Teachers")
