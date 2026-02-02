import streamlit as st
import pandas as pd
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_groq import ChatGroq
from retailers import check_stock_disctree, check_stock_newdisc

# --- CONFIGURATION ---
st.set_page_config(page_title="FindMinDisc", page_icon="🥏")

# --- API KEY HANDLING ---
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    st.error("Mangler GROQ_API_KEY. Tilføj den til Streamlit Secrets.")
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
# Groq with Llama 3.3 (Free & Fast)
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=api_key,
    temperature=0.7
)
search = DuckDuckGoSearchRun()

# --- SIDEBAR ---
with st.sidebar:
    st.title("FindMinDisc 🥏")
    
    st.subheader("Om dig")
    skill_level = st.selectbox("Niveau", ["Begynder", "Øvet", "Erfaren"])
    max_dist = st.slider("Maks distance (m)", 30, 150, 80)
    
    st.subheader("Hvad leder du efter?")
    disc_type = st.selectbox("Disc type", ["Putter", "Midrange", "Fairway driver", "Distance driver"])
    
    flight_pref = st.selectbox("Flyvning", [
        "Lige/stabil",
        "Understabil (drejer højre for RHBH)", 
        "Overstabil (drejer venstre for RHBH)",
        "Ved ikke endnu"
    ])
    
    st.divider()
    st.info("Drevet af Llama 3.3 via Groq")

# --- CHAT INTERFACE ---
st.header("Find Din Næste Disc")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hej! Brug menuen til venstre og fortæl mig mere om hvad du søger 🥏"}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Beskriv hvad du leder efter..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Søger anmeldelser..."):
            
            # 1. Single optimized search query
            search_query = f"best {disc_type} disc golf {flight_pref} {prompt} review recommendation"
            
            try:
                search_results = search.run(search_query)
                # Truncate to avoid token limits
                search_results = search_results[:3000]
            except:
                search_results = "Ingen søgeresultater fundet."
            
            # 2. Ask Gemini
            ai_prompt = f"""Brugerprofil: {skill_level}, kaster {max_dist}m, søger {disc_type}, ønsker {flight_pref}.
Ekstra: "{prompt}"

Anbefalinger fra nettet:
{search_results}

Anbefal ÉN {disc_type.lower()} på dansk. Nævn flight numbers. Skriv KUN discens navn på første linje.
Kort og venligt svar."""
            
            try:
                ai_response = llm.invoke(ai_prompt).content
                
                # Parse the response
                lines = ai_response.split('\n')
                suggested_disc = lines[0].replace("*", "").replace(":", "").replace("#", "").strip()
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
                error_msg = str(e)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    final_reply = "⏳ Gemini har brug for en pause. Vent 1 minut og prøv igen."
                else:
                    final_reply = f"⚠️ Ups, noget gik galt: {e}"
            
            st.markdown(final_reply)
            st.session_state.messages.append({"role": "assistant", "content": final_reply})