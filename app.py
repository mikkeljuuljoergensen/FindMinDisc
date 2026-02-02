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
            
            # 2. Ask LLM for recommendations
            ai_prompt = f"""Brugerprofil: {skill_level}, kaster {max_dist}m, ønsker {flight_pref}.

VIGTIG: Brugeren søger specifikt en **{disc_type}** ({speed_hint}).
Anbefal KUN discs der er {disc_type}s - IKKE andre disc-typer!
- Putter = speed 1-3 (f.eks. Aviar, P2, Luna, Envy)
- Midrange = speed 4-6 (f.eks. Buzzz, Roc, Mako3)
- Fairway driver = speed 7-9 (f.eks. Leopard, Teebird, River)
- Distance driver = speed 10+ (f.eks. Destroyer, Wraith, Zeus)

Ekstra info fra bruger: "{prompt}"

Søgeresultater:
{search_results}

Giv 3 {disc_type.lower()}-anbefalinger på dansk. Formatér discnavn i bold: **DiscNavn**

For hver disc:
1. **[Disc navn]** af [Mærke]
2. Flight numbers (speed/glide/turn/fade)
3. Fordele
4. Ulemper
5. Anbefalet plastik og hvordan det påvirker stabiliteten:
   - Premium (ESP, Star, Champion, Neutron) = mere overstabil
   - Base (DX, Pro-D, Prime) = bliver understabil hurtigere
   - Gummi (Gstar, Glow) = bedre greb i koldt vejr
   - Base plastik (DX, Pro-D, Prime) = bliver understabil hurtigere, bedre greb
   - Gummiagtigt (Gstar, Glow) = bedre greb i koldt vejr

Sammenlign til sidst - hvem passer bedst til hvad?

Formatér pænt med ### overskrifter og bullet points."""
            
            try:
                ai_response = llm.invoke(ai_prompt).content
                
                # Extract disc names for stock check
                import re
                # Find bold disc names like **Buzzz** or **Mako3**
                bold_names = re.findall(r'\*\*([A-Za-z0-9]+)\*\*', ai_response)
                # Filter to likely disc names (not common words)
                skip_words = {'flight', 'numbers', 'fordele', 'ulemper', 'plastik', 'sammenligning', 'disc', 'discs', 'found', 'check', 'view', 'speed', 'glide', 'turn', 'fade', 'premium', 'base'}
                disc_names = [name for name in bold_names if name.lower() not in skip_words][:3]
                
                # Build stock info with links to Danish retailers
                stock_info = ""
                for disc in disc_names:
                    disc_clean = disc.strip()
                    if disc_clean and len(disc_clean) > 2:
                        stock_info += f"**{disc_clean}:**\n"
                        stock_info += f"  * {check_stock_disctree(disc_clean)}\n"
                        stock_info += f"  * {check_stock_newdisc(disc_clean)}\n"
                        stock_info += f"  * {check_stock_discimport(disc_clean)}\n"
                
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