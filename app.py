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
    st.info("Drevet af Google Gemini")

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
        with st.spinner("Søger anmeldelser fra hele nettet..."):
            
            # 1. Search multiple disc golf sites
            search_sites = [
                "site:reddit.com/r/discgolf",
                "site:infinitediscs.com",
                "site:flightcharts.dgputtheads.com",
                "site:discgolfmentor.com",
            ]
            
            all_search_results = []
            base_query = f"best {disc_type} disc golf {flight_pref} {prompt}"
            
            for site in search_sites:
                try:
                    result = search.run(f"{base_query} {site}")
                    all_search_results.append(result)
                except:
                    pass
            
            combined_results = "\n\n---\n\n".join(all_search_results)
            
            # 2. Ask Gemini
            ai_prompt = f"""
            Brugerprofil:
            - Niveau: {skill_level}
            - Kaster ca. {max_dist}m
            - Søger: {disc_type}
            - Ønsket flyvning: {flight_pref}
            - Ekstra info: "{prompt}"
            
            Anmeldelser og anbefalinger fra nettet:
            {combined_results}
            
            Giv et kort, venligt svar på dansk:
            1. Anbefal ÉN {disc_type.lower()} der passer perfekt.
            2. Forklar kort hvorfor (nævn flight numbers: speed/glide/turn/fade).
            3. Skriv discens navn ALENE på første linje (kun navnet, ingen ekstra tekst).
            
            Hold tonen afslappet som en ven der hjælper i en disc golf butik.
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