import streamlit as st
import pandas as pd
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_google_genai import ChatGoogleGenerativeAI # <-- CHANGED IMPORT
from retailers import check_stock_disctree, check_stock_newdisc

# --- CONFIGURATION ---
st.set_page_config(page_title="FindMinDisc", page_icon="🥏")

# --- API KEY HANDLING ---
# We now look for "GOOGLE_API_KEY" instead of "OPENAI_API_KEY"
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("Missing Google API Key. Please add it to Streamlit Secrets.")
    st.stop()

# --- DATA LOADING (Dummy Data Fallback) ---
@st.cache_data
def load_discs():
    return pd.DataFrame({
        'Name': ['Destroyer', 'Buzzz', 'River', 'P2', 'Zone'],
        'Brand': ['Innova', 'Discraft', 'Latitude 64', 'Discmania', 'Discraft'],
        'Speed': [12, 5, 7, 2, 4],
        'Turn': [-1, -1, -1, 0, 0],
        'Fade': [3, 1, 1, 2, 3]
    })

df = load_discs()

# --- AI SETUP ---
# We use Gemini 2.0 Flash (Free & Fast)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", 
    google_api_key=api_key,
    temperature=0.7
)
search = DuckDuckGoSearchRun()

# --- SIDEBAR ---
with st.sidebar:
    st.title("FindMinDisc 🥏")
    skill_level = st.selectbox("Niveau", ["Begynder", "Øvet", "Erfaren"])
    max_dist = st.slider("Maks distance (m)", 30, 150, 80)
    st.info("Drevet af Google Gemini")

# --- CHAT INTERFACE ---
st.header("Find Din Næste Disc")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hej! Hvad skal discen kunne? 🥏"}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Beskriv hvad du leder efter..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Leder efter den rette disc..."):
            
            # 1. Search Web
            search_query = f"best disc golf disc for {skill_level} {prompt} site:reddit.com"
            search_results = search.run(search_query)
            
            # 2. Ask Gemini
            ai_prompt = f"""
            Brugerprofil: {skill_level}, kaster ca. {max_dist}m.
            Bruger søger: "{prompt}"
            
            Reddit-anbefalinger:
            {search_results}
            
            Giv et kort, venligt svar på dansk:
            1. Anbefal ÉN disc der passer.
            2. Forklar kort hvorfor (nævn flight numbers).
            3. Skriv discens navn ALENE på første linje.
            
            Hold tonen afslappet som en ven der hjælper.
            """
            
            try:
                ai_response = llm.invoke(ai_prompt).content
                
                # Parse the response
                lines = ai_response.split('\n')
                suggested_disc = lines[0].replace("*", "").replace(":", "").strip()
                explanation = "\n".join(lines[1:])
                
                # 3. Check Stock
                stock_dt = check_stock_disctree(suggested_disc)
                stock_nd = check_stock_newdisc(suggested_disc)
                
                final_reply = f"""
### Prøv en **{suggested_disc}**
                
{explanation}
                
---
**🇩🇰 På lager i DK:**
* {stock_dt}
* {stock_nd}
"""
            except Exception as e:
                final_reply = f"⚠️ Ups, noget gik galt: {e}"
            
            st.markdown(final_reply)
            st.session_state.messages.append({"role": "assistant", "content": final_reply})