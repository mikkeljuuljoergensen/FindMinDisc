import streamlit as st
import re
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_openai import ChatOpenAI
from retailers import get_product_links

# --- CONFIGURATION ---
st.set_page_config(page_title="FindMinDisc", page_icon="🥏")

# --- API KEY HANDLING ---
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    st.error("Mangler OPENAI_API_KEY. Tilføj den til Streamlit Secrets.")
    st.stop()

# --- AI SETUP ---
llm = ChatOpenAI(
    model="gpt-4o-mini",
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
            
            # Check for mismatch and warn user BEFORE searching
            mismatch_warning = ""
            if max_dist < 60 and disc_type == "Distance driver":
                mismatch_warning = f"""⚠️ **Vent lige lidt!**

Du kaster {max_dist}m og leder efter en distance driver. Det er typisk ikke det bedste valg:
- Distance drivers (speed 10+) kræver **80+ meter armhastighed** for at flyve korrekt
- Med {max_dist}m vil en distance driver sandsynligvis bare dykke ned eller fade hårdt til venstre

**Jeg anbefaler i stedet:**
- **Putter** (speed 1-3) til præcision
- **Midrange** (speed 4-6) til allround brug
- **Fairway driver** (speed 7-9) til lidt mere distance

Men okay, du bad om distance drivers, så her er nogle **letvægts understabile** modeller der kan virke:

---

"""
            elif max_dist < 50 and disc_type == "Fairway driver":
                mismatch_warning = f"""⚠️ **Bemærk:** Med {max_dist}m kastelængde kan en midrange (speed 4-6) måske passe bedre end en fairway driver. Men her er mine anbefalinger:

---

"""
            
            with st.spinner("Søger efter de bedste discs til dig..."):
                search_query = f"best {disc_type} disc golf {flight} {extra_info} review recommendation lightweight beginner"
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
                
                # Warning for AI
                ai_warning = ""
                if max_dist < 60 and disc_type == "Distance driver":
                    ai_warning = f"""KRITISK: Brugeren kaster kun {max_dist}m men vil have distance drivers.
Anbefal KUN letvægts (150-160g) understabile distance drivers.
Forklar at de bør overveje midranges eller fairway drivers i stedet."""
                elif max_dist < 50 and disc_type == "Fairway driver":
                    ai_warning = f"Brugeren kaster {max_dist}m. Anbefal letvægts understabile fairways."
                
                # Handle brand preferences
                brand_instruction = ""
                extra_lower = extra_info.lower() if extra_info else ""
                if "mvp" in extra_lower or "axiom" in extra_lower or "streamline" in extra_lower:
                    brand_instruction = f"VIGTIGT: Brugeren ønsker specifikt discs fra MVP/Axiom/Streamline. Anbefal KUN discs fra disse mærker!"
                elif "innova" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Innova discs. Anbefal KUN Innova discs!"
                elif "discraft" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Discraft discs. Anbefal KUN Discraft discs!"
                elif "latitude" in extra_lower or "lat64" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Latitude 64 discs. Anbefal KUN Latitude 64 discs!"
                elif "discmania" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Discmania discs. Anbefal KUN Discmania discs!"
                elif "kastaplast" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Kastaplast discs. Anbefal KUN Kastaplast discs!"
                
                ai_prompt = f"""Brugerprofil: kaster {max_dist}m, ønsker {flight} flyvning.
{ai_warning}
{brand_instruction}

Disc-type: **{disc_type}** ({speed_hint})
Ekstra ønsker: {extra_info if extra_info else "Ingen"}

Søgeresultater:
{search_results}

Giv 3 FORSKELLIGE {disc_type.lower()}-anbefalinger på dansk.
Vær kreativ - anbefal ikke altid de samme discs!

REGLER:
- Anbefal KUN {disc_type}s
- Følg brugerens mærke-præference hvis angivet
- For kastere under 70m: anbefal letvægt (150-165g) og understabile discs
- Nævn vægt i gram
- Hvis valget er dårligt, sig det tydeligt
- VARIER dine anbefalinger - der findes mange gode discs!

FORMAT FOR HVER DISC:

### 1. **[DiscNavn]** af [Mærke]
- Flight: X/X/X/X, Vægt: XXXg
- ✅ Fordele: ...
- ❌ Ulemper: ...
- 🥏 Plastik: ...

Afslut med en kort sammenligning."""

                try:
                    ai_response = llm.invoke(ai_prompt).content
                    
                    # Find disc names - look for **Name** pattern
                    bold_matches = re.findall(r'\*\*([A-Za-z0-9\s\-]+)\*\*', ai_response)
                    disc_names = []
                    skip_words = {'flight', 'numbers', 'fordele', 'ulemper', 'plastik', 'sammenligning', 
                                  'disc', 'discs', 'speed', 'glide', 'turn', 'fade', 'premium', 'base', 
                                  'distance', 'driver', 'putter', 'midrange', 'fairway', 'innova', 
                                  'discraft', 'discmania', 'latitude', 'mvp', 'axiom', 'kastaplast', 
                                  'westside', 'dynamic', 'navn', 'mærke', 'af', 'anbefaling', 'vent',
                                  'bemærk', 'lige', 'lidt', 'prodigy', 'lone', 'star', 'streamline',
                                  'thought', 'space', 'clash', 'dga', 'viking', 'yikun', 'gateway'}
                    
                    for match in bold_matches:
                        words = match.strip().split()
                        for word in reversed(words):
                            word_clean = word.strip()
                            if word_clean.lower() not in skip_words and len(word_clean) > 2:
                                if word_clean not in disc_names:
                                    disc_names.append(word_clean)
                                break
                    
                    disc_names = disc_names[:3]
                    
                    # Build buy links for each disc and inject into response
                    modified_response = ai_response
                    for disc in disc_names:
                        if disc and len(disc) > 2:
                            # Get direct product links from stores
                            links = get_product_links(disc)
                            dt_url = links.get('Disc Tree', f"https://disctree.dk/search?q={disc}")
                            nd_url = links.get('NewDisc', f"https://newdisc.dk/search?q={disc}")
                            
                            # Create buy links section
                            buy_links = f"\n   🛒 **Køb:** [Disc Tree]({dt_url}) | [NewDisc]({nd_url})"
                            
                            # Find the plastic line for this disc and add links after it
                            # Look for pattern like "🥏 Plastik:" after the disc name
                            pattern = rf'(\*\*{re.escape(disc)}\*\*.*?🥏 Plastik:[^\n]*)'
                            match = re.search(pattern, modified_response, re.DOTALL | re.IGNORECASE)
                            if match:
                                modified_response = modified_response.replace(
                                    match.group(1), 
                                    match.group(1) + buy_links
                                )
                    
                    # Add warning to response if mismatch
                    final_reply = f"""{mismatch_warning}{modified_response}

---
*Spørg mig om mere, eller skriv 'forfra' for at starte helt forfra.*"""

                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in str(e) or "rate" in error_str:
                        final_reply = "⏳ API'en har brug for en pause. Vent lidt og prøv igen."
                    elif "insufficient_quota" in error_str or "billing" in error_str:
                        final_reply = "💳 Din OpenAI konto mangler credits. Tilføj betalingsmetode på platform.openai.com"
                    elif "invalid_api_key" in error_str or "unauthorized" in error_str:
                        final_reply = "🔑 Ugyldig API-nøgle. Tjek at OPENAI_API_KEY er korrekt i Streamlit Secrets."
                    else:
                        final_reply = f"⚠️ Fejl: {e}"
                
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
                                    dt_result = check_stock_disctree(disc)
                                    nd_result = check_stock_newdisc(disc)
                                    
                                    disc_links = []
                                    if dt_result:
                                        disc_links.append(f"Disc Tree: {dt_result}")
                                    if nd_result:
                                        disc_links.append(f"NewDisc: {nd_result}")
                                    
                                    if disc_links:
                                        stock_info += f"**{disc}:**\n"
                                        for link in disc_links:
                                            stock_info += f"  * {link}\n"
                                        stock_info += "\n"
                            
                            if stock_info.strip().endswith("Danmark:"):
                                stock_info = ""  # No products found
                            else:
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
    st.caption("Drevet af den bedste AI Mikkel har råd til")
