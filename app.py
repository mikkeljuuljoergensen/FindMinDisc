import streamlit as st
import pandas as pd
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_groq import ChatGroq
from retailers import check_stock_disctree, check_stock_newdisc, check_stock_discimport

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
                search_results = search_results[:4000]
            except:
                search_results = "Ingen søgeresultater fundet."
            
            # Map disc types to speed ranges
            speed_ranges = {
                "Putter": "speed 1-3",
                "Midrange": "speed 4-6",
                "Fairway driver": "speed 7-9",
                "Distance driver": "speed 10-14"
            }
            speed_hint = speed_ranges.get(disc_type, "")
            
            # Calculate recommended max speed based on distance
            # Rule of thumb: you need ~10m per speed point
            recommended_max_speed = max(6, min(14, max_dist // 10))
            
            # Build warning based on distance vs disc choice
            skill_warning = ""
            if max_dist < 70 and disc_type == "Distance driver":
                skill_warning = f"""
⚠️ VIGTIGT:
Med en kastelængde på {max_dist}m anbefales det IKKE at bruge distance drivers (speed 10+).
Distance drivers kræver typisk 80+ meter armhastighed for at flyve korrekt.
For {max_dist}m anbefales max speed {recommended_max_speed} disc.
FORESLÅ i stedet understabile fairway drivers (speed 7-9) eller midranges i LETVÆGT (150-160g).
Hvis brugeren insisterer på distance drivers, anbefal KUN letvægts understabile modeller (under 160g).
"""
            elif max_dist < 50 and disc_type == "Fairway driver":
                skill_warning = f"""
⚠️ TIP: Med {max_dist}m kastelængde kan en midrange måske være bedre end en fairway driver.
Hvis du anbefaler fairway drivers, vælg understabile letvægts-modeller.
"""
            
            # 2. Ask LLM for recommendations
            ai_prompt = f"""Brugerprofil: kaster {max_dist}m, ønsker {flight_pref}.
{skill_warning}

Brugeren har valgt: **{disc_type}** ({speed_hint}).

REGLER:
- Anbefal KUN {disc_type}s
- For kastere under 70m: anbefal ALTID letvægt (150-165g) og understabile discs
- Nævn specifik vægt i gram når relevant
- Hvis valget er dårligt for brugeren, SIG DET TYDELIGT i starten

Disc-typer reference:
- Putter = speed 1-3 (Aviar, P2, Luna, Envy)
- Midrange = speed 4-6 (Buzzz, Roc, Mako3, Fuse)
- Fairway driver = speed 7-9 (Leopard, Diamond, River, Maul)
- Distance driver = speed 10+ (Destroyer, Wraith, Tern, Shryke)

Ekstra info fra bruger: "{prompt}"

Søgeresultater:
{search_results}

Giv 3 anbefalinger på dansk.

VIGTIG FORMATERING - skriv disc-navnet ALENE i bold sådan (uden mærke):
**Destroyer**
**Buzzz**
**Leopard**

For hver disc:
1. **[DiscNavn]** af [Mærke]
2. Flight numbers og anbefalet vægt
3. Fordele
4. Ulemper
5. Plastik-anbefaling

Sammenlign til sidst."""
            
            try:
                ai_response = llm.invoke(ai_prompt).content
                
                # Extract disc names for stock check
                import re
                # Find bold text like **Destroyer** or **Innova Destroyer** or **Mako3**
                bold_matches = re.findall(r'\*\*([A-Za-z0-9\s]+)\*\*', ai_response)
                
                # Extract just the disc name (last word if multiple, or the whole thing)
                disc_names = []
                skip_words = {'flight', 'numbers', 'fordele', 'ulemper', 'plastik', 'sammenligning', 
                              'disc', 'discs', 'found', 'check', 'view', 'speed', 'glide', 'turn', 
                              'fade', 'premium', 'base', 'distance', 'driver', 'putter', 'midrange',
                              'fairway', 'innova', 'discraft', 'discmania', 'latitude', 'mvp', 'axiom',
                              'kastaplast', 'westside', 'dynamic', 'navn', 'mærke', 'af'}
                
                for match in bold_matches:
                    words = match.strip().split()
                    # Get the last word (usually the disc name) or check each word
                    for word in reversed(words):
                        word_clean = word.strip()
                        if word_clean.lower() not in skip_words and len(word_clean) > 2:
                            if word_clean not in disc_names:
                                disc_names.append(word_clean)
                            break
                
                disc_names = disc_names[:3]
                
                # Build stock info with links to Danish retailers
                stock_info = ""
                for disc in disc_names:
                    if disc and len(disc) > 2:
                        stock_info += f"**{disc}:**\n"
                        stock_info += f"  * {check_stock_disctree(disc)}\n"
                        stock_info += f"  * {check_stock_newdisc(disc)}\n"
                        stock_info += f"  * {check_stock_discimport(disc)}\n\n"
                
                final_reply = f"""{ai_response}

---
## 🇩🇰 Find dem i Danmark:
{stock_info if stock_info else "Kunne ikke finde disc-navne."}
"""
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "rate" in error_msg.lower():
                    final_reply = "⏳ API'en har brug for en pause. Vent lidt og prøv igen."
                else:
                    final_reply = f"⚠️ Ups, noget gik galt: {e}"
            
            st.markdown(final_reply)
            st.session_state.messages.append({"role": "assistant", "content": final_reply})