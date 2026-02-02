"""
INTEGRATION GUIDE: Adding Knowledge Base to FindMinDisc
========================================================

This guide shows how to integrate the Reddit knowledge base into your app.py
"""

# ============================================================================
# STEP 1: Add imports at the top of app.py
# ============================================================================
"""
from knowledge_base import DiscGolfKnowledgeBase
import os

# Initialize knowledge base (add this after your other initializations)
kb = None
try:
    if os.path.exists('./faiss_db/index.faiss'):
        kb = DiscGolfKnowledgeBase(openai_api_key=st.secrets.get("OPENAI_API_KEY"))
        st.session_state['kb_enabled'] = True
    else:
        st.session_state['kb_enabled'] = False
except Exception as e:
    st.session_state['kb_enabled'] = False
    print(f"Knowledge base not available: {e}")
"""


# ============================================================================
# STEP 2: Modify handle_free_form_question function
# ============================================================================
"""
Replace the existing handle_free_form_question with this enhanced version:
"""

def handle_free_form_question_enhanced(prompt, user_prefs=None):
    """
    Enhanced version with knowledge base integration.
    """
    if user_prefs is None:
        user_prefs = {}
    
    # Extract useful info from the prompt
    prompt_lower = prompt.lower()
    
    # Try to detect disc type from question
    disc_type = None
    if 'putter' in prompt_lower:
        disc_type = "Putter"
    elif 'approach' in prompt_lower:
        disc_type = "Putter"
    elif 'midrange' in prompt_lower or 'mid-range' in prompt_lower:
        disc_type = "Midrange"
    elif 'fairway' in prompt_lower:
        disc_type = "Fairway driver"
    elif 'distance' in prompt_lower or 'driver' in prompt_lower:
        disc_type = "Distance driver"
    
    # Try to detect skill level
    skill_level = None
    if 'nybegynder' in prompt_lower or 'begynder' in prompt_lower or 'ny ' in prompt_lower or 'starter' in prompt_lower:
        skill_level = "beginner"
    elif 'øvet' in prompt_lower or 'intermediate' in prompt_lower:
        skill_level = "intermediate"
    elif 'erfaren' in prompt_lower or 'pro' in prompt_lower or 'avanceret' in prompt_lower:
        skill_level = "advanced"
    
    # Set defaults
    max_dist = user_prefs.get('max_dist', None)
    if max_dist is None:
        max_dist = 70 if skill_level == "beginner" else 80
    if skill_level is None:
        skill_level = "intermediate"
    
    # ==== NEW: Get context from knowledge base ====
    kb_context = ""
    if st.session_state.get('kb_enabled', False) and kb:
        try:
            kb_context = kb.get_context_for_query(prompt, max_results=3)
            kb_context = f"\n\nRELEVANT REDDIT DISCUSSIONS:\n{kb_context}"
        except Exception as e:
            print(f"Error accessing knowledge base: {e}")
            kb_context = ""
    
    # Build search query
    search_terms = prompt.replace('?', '').replace('!', '')
    if skill_level == "beginner":
        search_query = f"best disc golf discs for beginners {search_terms}"
    else:
        search_query = f"disc golf recommendation {search_terms}"
    
    # Web search
    try:
        search_results = search.run(search_query)[:4000]
    except Exception:
        search_results = ""
    
    # Get sample discs from database
    sample_discs = []
    for name, data in list(DISC_DATABASE.items())[:100]:
        speed = data.get('speed', 0)
        if skill_level == "beginner" and speed > 9:
            continue
        if disc_type:
            speed_ranges = {"Putter": (1, 3), "Midrange": (4, 6), "Fairway driver": (7, 9), "Distance driver": (10, 14)}
            min_s, max_s = speed_ranges.get(disc_type, (1, 14))
            if not (min_s <= speed <= max_s):
                continue
        sample_discs.append(f"{name} ({data.get('manufacturer', '?')}): {speed}/{data.get('glide', 4)}/{data.get('turn', 0)}/{data.get('fade', 2)}")
        if len(sample_discs) >= 30:
            break
    
    disc_context = "\n".join(sample_discs) if sample_discs else "Ingen relevante discs fundet"
    
    # ==== UPDATED: Enhanced AI prompt with KB context ====
    ai_prompt = f"""Du er en venlig disc golf ekspert der hjælper brugere med at finde de rigtige discs.

Brugerens spørgsmål: "{prompt}"

Brugerens niveau: {"Nybegynder" if skill_level == "beginner" else "Øvet" if skill_level == "intermediate" else "Erfaren"}
Estimeret kastelængde: ca. {max_dist}m

Søgeresultater fra nettet:
{search_results}

{kb_context}

Discs fra vores database:
{disc_context}

REGLER:
1. Svar på dansk, venligt og hjælpsomt
2. Hvis brugeren spørger om specifikke anbefalinger, giv 2-4 konkrete disc-forslag
3. Brug flight numbers format: Speed/Glide/Turn/Fade
4. For nybegyndere: anbefal understabile discs (turn -2 eller lavere) og lavere speed
5. Nævn vægt (begyndere: 150-165g, erfarne: 170-175g)
6. Brug Reddit-diskussioner når de er relevante
7. Vær ærlig om hvad der passer til brugerens niveau

Hvis du anbefaler discs, brug dette format:

### **[DiscNavn]** af [Mærke]
- Flight: X/X/X/X
- ✅ Hvorfor: ...

Afslut med at spørge om brugeren vil vide mere, sammenligne discs, eller se hvordan de flyver (flight chart)."""

    try:
        response = llm.invoke(ai_prompt).content
        return response
    except Exception as e:
        return f"Fejl: Kunne ikke behandle din forespørgsel. {str(e)}"


# ============================================================================
# STEP 3: Add knowledge base info to sidebar (optional)
# ============================================================================
"""
Add this to your Streamlit sidebar to show KB status:

with st.sidebar:
    if st.session_state.get('kb_enabled', False):
        st.success("🧠 Knowledge Base: Active")
        if kb:
            stats = kb.get_stats()
            st.caption(f"📚 {stats['total_documents']} documents loaded")
    else:
        st.warning("Knowledge Base: Not loaded")
        st.caption("Run setup to enable enhanced recommendations")
"""


# ============================================================================
# USAGE INSTRUCTIONS
# ============================================================================
"""
TO SET UP THE KNOWLEDGE BASE:

1. Install new dependencies:
   pip install -r requirements.txt

2. Set up Reddit API credentials:
   - Go to https://www.reddit.com/prefs/apps
   - Create an app (script type)
   - Edit reddit_scraper.py with your credentials

3. Run the scraper to collect data:
   python reddit_scraper.py
   (This will create reddit_discgolf_data.json and discgolf_knowledge.txt)

4. Build the knowledge base:
   python knowledge_base.py
   (This will create the faiss_db folder with embeddings)

5. Integrate into app.py:
   - Add the imports from STEP 1
   - Replace handle_free_form_question with the enhanced version from STEP 2
   - Optionally add KB status to sidebar from STEP 3

6. Run your app:
   streamlit run app.py

The bot will now use Reddit discussions to give better recommendations!

NOTES:
- The knowledge base uses OpenAI embeddings (requires API key)
- You can re-run the scraper periodically to update with new content
- The faiss_db folder can get large - add it to .gitignore
- Uses FAISS (Facebook AI Similarity Search) - no C++ compiler needed!
"""


# ============================================================================
# ALTERNATIVE: Simple Integration Without Embeddings
# ============================================================================
"""
If you want a simpler solution without embeddings/ChromaDB:

from knowledge_base import SimpleTextKnowledgeBase

# Initialize
simple_kb = SimpleTextKnowledgeBase('discgolf_knowledge.txt')

# Use in your function
def get_simple_context(query):
    results = simple_kb.search(query, context_window=500)
    if results:
        return "\\n\\n---\\n\\n".join(results[:3])
    return ""

# Add to prompt
kb_context = get_simple_context(prompt)

This is faster but less intelligent than semantic search.
"""
