import streamlit as st
import re
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

# --- AI SETUP ---
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=api_key,
    temperature=0.7
)
search = DuckDuckGoSearchRun()

# --- INITIALIZE SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "step" not in st.session_state:
    st.session_state.step = "start"
if "user_prefs" not in st.session_state:
    st.session_state.user_prefs = {}

# --- HEADER ---
st.header("FindMinDisc 🥏")

# --- HELPER FUNCTIONS ---
def add_bot_message(content):
    st.session_state.messages.append({"role": "assistant", "content": content})

def add_user_message(content):
    st.session_state.messages.append({"role": "user", "content": content})

def reset_conversation():
    st.session_state.messages = []
    st.session_state.step = "start"
    st.session_state.user_prefs = {}

# --- START CONVERSATION ---
if st.session_state.step == "start":
    add_bot_message("Hej! Jeg hjælper dig med at finde den perfekte disc 🥏\n\nHvad leder du efter?\n\n1️⃣ Putter\n2️⃣ Midrange\n3️⃣ Fairway driver\n4️⃣ Distance driver")
    st.session_state.step = "ask_type"

# --- DISPLAY MESSAGES ---
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# --- CHAT INPUT ---
if prompt := st.chat_input("Skriv dit svar..."):
    add_user_message(prompt)
    st.chat_message("user").write(prompt)
    
    with st.chat_message("assistant"):
        
        # --- STEP: ASK DISC TYPE ---
        if st.session_state.step == "ask_type":
            prompt_lower = prompt.lower()
            if "1" in prompt or "putter" in prompt_lower:
                st.session_state.user_prefs["disc_type"] = "Putter"
            elif "2" in prompt or "midrange" in prompt_lower or "mid" in prompt_lower:
                st.session_state.user_prefs["disc_type"] = "Midrange"
            elif "3" in prompt or "fairway" in prompt_lower:
                st.session_state.user_prefs["disc_type"] = "Fairway driver"
            elif "4" in prompt or "distance" in prompt_lower or "driver" in prompt_lower:
                st.session_state.user_prefs["disc_type"] = "Distance driver"
            else:
                reply = "Hmm, jeg forstod ikke helt. Skriv 1, 2, 3 eller 4 - eller skriv disc-typen (f.eks. 'putter' eller 'midrange')"
                st.write(reply)
                add_bot_message(reply)
                st.rerun()
            
            reply = f"Fedt, du leder efter en **{st.session_state.user_prefs['disc_type']}**!\n\nHvor langt kaster du cirka? (i meter)"
            st.write(reply)
            add_bot_message(reply)
            st.session_state.step = "ask_distance"
        
        # --- STEP: ASK DISTANCE ---
        elif st.session_state.step == "ask_distance":
            numbers = re.findall(r'\d+', prompt)
            if numbers:
                dist = int(numbers[0])
                if dist > 200:
                    dist = int(dist * 0.3)
                st.session_state.user_prefs["max_dist"] = dist
                
                reply = f"Okay, du kaster ca. **{dist}m**.\n\nHvilken flyvning ønsker du?\n\n1️⃣ Lige/stabil\n2️⃣ Understabil (drejer til højre for højrehåndede)\n3️⃣ Overstabil (drejer til venstre for højrehåndede)\n4️⃣ Ved ikke"
                st.write(reply)
                add_bot_message(reply)
                st.session_state.step = "ask_flight"
            else:
                reply = "Jeg fangede ikke et tal. Hvor mange meter kaster du cirka? (f.eks. '60' eller '80 meter')"
                st.write(reply)
                add_bot_message(reply)
        
        # --- STEP: ASK FLIGHT ---
        elif st.session_state.step == "ask_flight":
            prompt_lower = prompt.lower()
            if "1" in prompt or "lige" in prompt_lower or "stabil" in prompt_lower:
                st.session_state.user_prefs["flight"] = "Lige/stabil"
            elif "2" in prompt or "understabil" in prompt_lower or "højre" in prompt_lower:
                st.session_state.user_prefs["flight"] = "Understabil"
            elif "3" in prompt or "overstabil" in prompt_lower or "venstre" in prompt_lower:
                st.session_state.user_prefs["flight"] = "Overstabil"
            elif "4" in prompt or "ved ikke" in prompt_lower:
                st.session_state.user_prefs["flight"] = "Ved ikke"
            else:
                reply = "Skriv 1, 2, 3 eller 4 - eller beskriv flyvningen (f.eks. 'lige' eller 'understabil')"
                st.write(reply)
                add_bot_message(reply)
                st.rerun()
            
            reply = "Godt! Er der andet jeg skal vide? (f.eks. 'god i vind', 'til putting', 'til skov', eller bare skriv 'nej')"
            st.write(reply)
            add_bot_message(reply)
            st.session_state.step = "ask_extra"
        
        # --- STEP: ASK EXTRA INFO ---
        elif st.session_state.step == "ask_extra":
            extra = prompt if prompt.lower() not in ["nej", "nej tak", "ingen", "-"] else ""
            st.session_state.user_prefs["extra"] = extra
            
            prefs = st.session_state.user_prefs
            disc_type = prefs["disc_type"]
            max_dist = prefs["max_dist"]
            flight = prefs["flight"]
            extra_info = prefs.get("extra", "")
            
            with st.spinner("Søger efter de bedste discs til dig..."):
                search_query = f"best {disc_type} disc golf {flight} {extra_info} review recommendation"
                try:
                    search_results = search.run(search_query)[:4000]
                except:
                    search_results = ""
                
                speed_ranges = {
                    "Putter": "speed 1-3",
                    "Midrange": "speed 4-6",
                    "Fairway driver": "speed 7-9",
                    "Distance driver": "speed 10-14"
                }
                speed_hint = speed_ranges.get(disc_type, "")
                recommended_max_speed = max(6, min(14, max_dist // 10))
                
                warning = ""
                if max_dist < 70 and disc_type == "Distance driver":
                    warning = f"⚠️ Med {max_dist}m kastelængde anbefales distance drivers normalt ikke. Anbefal letvægts understabile modeller (150-160g) eller foreslå fairway drivers."
                elif max_dist < 50 and disc_type == "Fairway driver":
                    warning = f"⚠️ Med {max_dist}m kan en midrange være bedre. Vælg letvægts understabile modeller."
                
                ai_prompt = f"""Brugerprofil: kaster {max_dist}m, ønsker {flight} flyvning.
{warning}

Disc-type: **{disc_type}** ({speed_hint})
Ekstra ønsker: {extra_info if extra_info else "Ingen"}

Søgeresultater:
{search_results}

Giv 3 {disc_type.lower()}-anbefalinger på dansk.

REGLER:
- Anbefal KUN {disc_type}s
- For kastere under 70m: anbefal letvægt (150-165g) og understabile discs
- Nævn vægt i gram
- Hvis valget er dårligt, sig det tydeligt

FORMATERING - skriv disc-navnet ALENE i bold:
**Destroyer**
**Buzzz**

For hver disc:
1. **[DiscNavn]** af [Mærke]
2. Flight numbers og vægt
3. Fordele
4. Ulemper
5. Plastik-anbefaling

Sammenlign til sidst."""

                try:
                    ai_response = llm.invoke(ai_prompt).content
                    
                    bold_matches = re.findall(r'\*\*([A-Za-z0-9\s]+)\*\*', ai_response)
                    disc_names = []
                    skip_words = {'flight', 'numbers', 'fordele', 'ulemper', 'plastik', 'sammenligning', 
                                  'disc', 'discs', 'speed', 'glide', 'turn', 'fade', 'premium', 'base', 
                                  'distance', 'driver', 'putter', 'midrange', 'fairway', 'innova', 
                                  'discraft', 'discmania', 'latitude', 'mvp', 'axiom', 'kastaplast', 
                                  'westside', 'dynamic', 'navn', 'mærke', 'af', 'anbefaling'}
                    
                    for match in bold_matches:
                        words = match.strip().split()
                        for word in reversed(words):
                            word_clean = word.strip()
                            if word_clean.lower() not in skip_words and len(word_clean) > 2:
                                if word_clean not in disc_names:
                                    disc_names.append(word_clean)
                                break
                    
                    disc_names = disc_names[:3]
                    
                    stock_info = ""
                    for disc in disc_names:
                        if disc and len(disc) > 2:
                            stock_info += f"**{disc}:** {check_stock_disctree(disc)} · {check_stock_newdisc(disc)} · {check_stock_discimport(disc)}\n\n"
                    
                    final_reply = f"""{ai_response}

---
## 🇩🇰 Find dem i Danmark:
{stock_info if stock_info else "Kunne ikke finde disc-navne."}

---
*Spørg mig om mere, eller skriv 'forfra' for at starte helt forfra.*"""

                except Exception as e:
                    if "429" in str(e) or "rate" in str(e).lower():
                        final_reply = "⏳ API'en har brug for en pause. Vent lidt og prøv igen."
                    else:
                        final_reply = f"⚠️ Noget gik galt: {e}"
                
                st.markdown(final_reply)
                add_bot_message(final_reply)
                st.session_state.step = "done"
        
        # --- STEP: DONE - CONTINUE CONVERSATION ---
        elif st.session_state.step == "done":
            if "forfra" in prompt.lower():
                reset_conversation()
                st.rerun()
            else:
                with st.spinner("Søger nye anbefalinger..."):
                    prefs = st.session_state.user_prefs
                    
                    # Check if user is updating their distance
                    numbers = re.findall(r'\d+', prompt)
                    if numbers:
                        new_dist = int(numbers[0])
                        if new_dist > 200:
                            new_dist = int(new_dist * 0.3)
                        if new_dist < 200:  # Likely a distance update
                            prefs["max_dist"] = new_dist
                    
                    # Check if user is changing disc type
                    prompt_lower = prompt.lower()
                    if "putter" in prompt_lower:
                        prefs["disc_type"] = "Putter"
                    elif "midrange" in prompt_lower or "mid-range" in prompt_lower or "mid range" in prompt_lower:
                        prefs["disc_type"] = "Midrange"
                    elif "fairway" in prompt_lower:
                        prefs["disc_type"] = "Fairway driver"
                    elif "distance" in prompt_lower:
                        prefs["disc_type"] = "Distance driver"
                    
                    # Build context from conversation
                    conversation_context = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in st.session_state.messages[-6:]])
                    
                    # Search again
                    disc_type = prefs.get("disc_type", "disc")
                    max_dist = prefs.get("max_dist", 80)
                    flight = prefs.get("flight", "")
                    
                    search_query = f"best {disc_type} disc golf {flight} {prompt} review"
                    try:
                        search_results = search.run(search_query)[:3000]
                    except:
                        search_results = ""
                    
                    speed_ranges = {
                        "Putter": "speed 1-3",
                        "Midrange": "speed 4-6",
                        "Fairway driver": "speed 7-9",
                        "Distance driver": "speed 10-14"
                    }
                    speed_hint = speed_ranges.get(disc_type, "")
                    
                    warning = ""
                    if max_dist < 70 and disc_type == "Distance driver":
                        warning = f"⚠️ Med {max_dist}m kastelængde anbefales distance drivers IKKE. Foreslå i stedet fairway drivers eller midranges."
                    elif max_dist < 50 and disc_type == "Fairway driver":
                        warning = f"⚠️ Med {max_dist}m kan en midrange være bedre."
                    
                    follow_up_prompt = f"""Tidligere samtale:
{conversation_context}

Brugerens nuværende profil: kaster {max_dist}m, søger {disc_type}, ønsker {flight} flyvning.
{warning}

Brugerens nye besked: "{prompt}"

REGLER:
- Hvis brugeren ændrer distance eller disc-type, giv NYE anbefalinger
- Hvis brugeren har spørgsmål, svar på dansk
- For kastere under 70m: anbefal letvægt (150-165g) og understabile discs
- Hvis disc-typen ikke passer til distancen, SIG DET og foreslå en bedre type

Søgeresultater:
{search_results}

Hvis du giver nye anbefalinger, brug dette format:
**[DiscNavn]** af [Mærke]
- Flight numbers og vægt
- Fordele/ulemper
- Plastik"""

                    try:
                        reply = llm.invoke(follow_up_prompt).content
                        
                        # Extract disc names for stock links
                        bold_matches = re.findall(r'\*\*([A-Za-z0-9\s]+)\*\*', reply)
                        disc_names = []
                        skip_words = {'flight', 'numbers', 'fordele', 'ulemper', 'plastik', 'sammenligning', 
                                      'disc', 'discs', 'speed', 'glide', 'turn', 'fade', 'premium', 'base', 
                                      'distance', 'driver', 'putter', 'midrange', 'fairway', 'innova', 
                                      'discraft', 'discmania', 'latitude', 'mvp', 'axiom', 'kastaplast', 
                                      'westside', 'dynamic', 'navn', 'mærke', 'af', 'anbefaling'}
                        
                        for match in bold_matches:
                            words = match.strip().split()
                            for word in reversed(words):
                                word_clean = word.strip()
                                if word_clean.lower() not in skip_words and len(word_clean) > 2:
                                    if word_clean not in disc_names:
                                        disc_names.append(word_clean)
                                    break
                        
                        disc_names = disc_names[:3]
                        
                        # Add stock links if we found disc names
                        if disc_names:
                            stock_info = "\n\n---\n## 🇩🇰 Find dem i Danmark:\n"
                            for disc in disc_names:
                                if disc and len(disc) > 2:
                                    stock_info += f"**{disc}:** {check_stock_disctree(disc)} · {check_stock_newdisc(disc)} · {check_stock_discimport(disc)}\n\n"
                            reply += stock_info
                        
                    except Exception as e:
                        reply = f"Beklager, noget gik galt: {e}"
                    
                    st.markdown(reply)
                    add_bot_message(reply)
                    st.session_state.user_prefs = prefs  # Save updated prefs

# --- SIDEBAR INFO ---
with st.sidebar:
    st.markdown("### Om FindMinDisc")
    st.markdown("Denne bot hjælper dig med at finde den perfekte disc til din spillestil.")
    st.divider()
    if st.button("🔄 Start forfra"):
        reset_conversation()
        st.rerun()
    st.divider()
    st.caption("Drevet af Llama 3.3 via Groq")
