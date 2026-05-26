"""
app.py — COTTAS Manager
Streamlit entry point with sidebar navigation.

Views live in views/ (not pages/) to use manual routing.
Streamlit reserves pages/ for native multi-page mode, which executes each file
directly and leaves blank pages when they only define render().
"""

import streamlit as st
from utils.file_manager import init_session_dir

# ─── Configuration ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="COTTAS Manager",
    page_icon=":material/database:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* Base typography */
html, body, [class*="css"], [data-testid="stAppViewContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
    font-size: 16px;
}
h1, h2, h3, h4 { font-family: 'Space Grotesk', 'Inter', sans-serif; letter-spacing: -0.02em; }
code, pre, kbd { font-family: 'JetBrains Mono', monospace; }

/* Hide Streamlit menu and footer */
#MainMenu, footer, header { visibility: hidden; }

/* App background */
[data-testid="stAppViewContainer"] {
    background: #0B0F1A;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0B0F1A;
    border-right: 1px solid #1F2937;
}
[data-testid="stSidebar"] * { color: #CBD5E1; }
[data-testid="stSidebar"] .stRadio label:hover p { color: #F1F5F9; }

/* Metric cards */
[data-testid="stMetric"] {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 10px;
    padding: 18px 20px;
}
[data-testid="stMetricLabel"] { color: #94A3B8 !important; font-weight: 500; }
[data-testid="stMetricValue"] { color: #F1F5F9 !important; font-weight: 600; }

/* Primary buttons */
.stButton > button[kind="primary"] {
    background: #3B82F6;
    border: 1px solid #3B82F6;
    border-radius: 8px;
    color: #fff;
    font-weight: 600;
    padding: 0.6rem 1.25rem;
    transition: all 0.15s ease;
}
.stButton > button[kind="primary"]:hover {
    background: #2563EB;
    border-color: #2563EB;
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.3);
}
.stButton > button[kind="secondary"] {
    background: transparent;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #CBD5E1;
    font-weight: 500;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #475569;
    color: #F1F5F9;
}

/* Inline code */
code {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 4px;
    padding: 1px 6px;
    color: #93C5FD;
    font-size: 0.88em;
}

/* DataFrames and expanders */
[data-testid="stDataFrame"] {
    border: 1px solid #1F2937;
    border-radius: 10px;
    overflow: hidden;
}
[data-testid="stExpander"] {
    border: 1px solid #1F2937;
    border-radius: 10px;
    background: #111827;
}
[data-testid="stExpander"] summary { color: #F1F5F9; font-weight: 500; }

/* File uploader */
[data-testid="stFileUploader"] {
    border: 1.5px dashed #334155;
    border-radius: 10px;
    background: #111827;
    padding: 8px 12px;
    transition: all 0.2s;
}
[data-testid="stFileUploader"]:hover {
    border-color: #3B82F6;
    background: #0F172A;
}
[data-testid="stFileUploader"] section {
    padding: 14px 18px;
}
[data-testid="stFileUploader"] small {
    color: #64748B !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 10px;
    gap: 6px;
    padding: 6px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    color: #94A3B8;
    font-weight: 500;
    padding: 10px 22px;
    min-height: unset;
}
.stTabs [data-baseweb="tab"]:hover { color: #F1F5F9; }
.stTabs [aria-selected="true"] {
    background: #1E293B !important;
    color: #F1F5F9 !important;
}

/* Dividers */
hr { border: none; border-top: 1px solid #1F2937; margin: 1.75rem 0; }

/* Reusable info box */
.info-box {
    background: #111827;
    border: 1px solid #1F2937;
    border-left: 3px solid #3B82F6;
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    margin: 10px 0;
    color: #CBD5E1;
    line-height: 1.6;
}
.info-box.muted { border-left-color: #334155; color: #64748B; }
.info-box b { color: #F1F5F9; font-weight: 600; }

/* Native alerts (st.success, st.error) */
[data-testid="stAlert"] {
    border-radius: 10px;
    border: 1px solid #1F2937;
}

/* All widget labels */
[data-testid="stWidgetLabel"] {
    padding: 0 2px 6px 2px;
    color: #CBD5E1 !important;
}

/* Inputs and selects: inner padding */
[data-baseweb="input"] input,
[data-baseweb="select"] > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    padding-left: 14px !important;
    padding-right: 14px !important;
}

/* Vertically align column content with charts */
[data-testid="stHorizontalBlock"] {
    align-items: center;
}


/* ─── Font sizes (readability) ────────────────────────────────────── */

/* Paragraphs and lists in the main area */
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
[data-testid="stMain"] [data-testid="stMarkdownContainer"] li {
    font-size: 1rem;
    line-height: 1.6;
}

/* Custom info-box */
.info-box {
    font-size: 0.98rem !important;
}
.info-box * {
    font-size: inherit !important;
}

/* Captions and secondary text (small grey under sliders, etc.) */
[data-testid="stCaptionContainer"] p,
[data-testid="stCaptionContainer"],
.stCaption,
[data-testid="stMarkdownContainer"] small {
    font-size: 0.9rem !important;
    color: #94A3B8 !important;
}

/* DataFrames */
[data-testid="stDataFrame"] { font-size: 0.96rem; }

/* Native alerts (success, error, warning, info) */
[data-testid="stAlert"] p {
    font-size: 1rem !important;
    line-height: 1.55 !important;
}

/* st.metric values and labels */
[data-testid="stMetricValue"] { font-size: 1.7rem !important; }
[data-testid="stMetricLabel"] p { font-size: 0.9rem !important; }

/* Buttons: comfortable font and padding */
.stButton > button {
    font-size: 1rem !important;
    font-weight: 500;
}

/* Widget labels */
[data-testid="stWidgetLabel"] p {
    font-size: 1rem !important;
    font-weight: 500 !important;
    margin-bottom: 6px !important;
}

/* Text inside inputs and selects */
[data-baseweb="input"] input,
[data-baseweb="select"] > div,
.stTextInput input,
.stNumberInput input,
textarea {
    font-size: 0.98rem !important;
}

/* Main tabs */
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] {
    font-size: 1rem !important;
}

/* Sidebar: navigation radio */
[data-testid="stSidebar"] .stRadio label p {
    font-size: 1rem !important;
    font-weight: 500;
    color: #94A3B8;
}

/* Sidebar: inner info-box */
[data-testid="stSidebar"] .info-box {
    font-size: 0.92rem !important;
}

/* Expander header */
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary {
    font-size: 1rem !important;
}

/* Text inside expanders */
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] li {
    font-size: 0.98rem;
    line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)

# ─── Session state ────────────────────────────────────────────────────────────
init_session_dir()
for k, v in {
    "active_cottas":   None,
    "active_name":     None,
    "last_search_df":  None,
    "last_sparql_df":  None,
    "history":         [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Sidebar ──────────────────────────────────────────────────────────────────
PAGES = {
    "Home":                    ("home",       ":material/home:"),
    "Compress":                ("compress",   ":material/compress:"),
    "Decompress":              ("decompress", ":material/unarchive:"),
    "Explore":                 ("explore",    ":material/travel_explore:"),
    "Triple Search":           ("search",     ":material/manage_search:"),
    "SPARQL Query":            ("sparql",     ":material/terminal:"),
    "Difference":              ("diff",       ":material/compare:"),
    "Merge":                   ("merge",      ":material/merge:"),
}

with st.sidebar:
    st.markdown("""
        <div style='padding:20px 4px 8px;'>
          <div style='font-family:"Space Grotesk",sans-serif;font-weight:700;
                      color:#F1F5F9;font-size:1.25rem;letter-spacing:-0.02em;'>
            COTTAS Manager
          </div>
          <div style='color:#64748B;font-size:0.75rem;margin-top:3px;
                      text-transform:uppercase;letter-spacing:0.08em;font-weight:500;'>
            Compression · Query · Analysis
          </div>
        </div>
    """, unsafe_allow_html=True)

    st.divider()

    labels = list(PAGES.keys())
    selected_label = st.radio(
        "Navigation",
        labels,
        format_func=lambda label: f"{PAGES[label][1]}  {label}",
        label_visibility="collapsed",
    )
    page = PAGES[selected_label][0]

    st.divider()

    if st.session_state["active_cottas"]:
        st.markdown(
            f"<div class='info-box'><b>Active file</b><br>"
            f"<code style='font-size:.78rem'>{st.session_state['active_name']}</code></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='info-box muted'>No COTTAS file loaded. "
            "Load one from <b>Compress</b> or <b>Decompress</b>.</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div style='position:fixed;bottom:16px;color:#475569;font-size:0.72rem;"
        "letter-spacing:0.05em;'>TFG · UPM · pycottas</div>",
        unsafe_allow_html=True,
    )

# ─── Routing ──────────────────────────────────────────────────────────────────
if   page == "home":       from views.home       import render
elif page == "compress":   from views.compress   import render
elif page == "decompress": from views.decompress import render
elif page == "explore":    from views.explore    import render
elif page == "search":     from views.search     import render
elif page == "sparql":     from views.sparql     import render
elif page == "diff":       from views.diff       import render
elif page == "merge":      from views.merge      import render
else:
    def render(): st.error("Page not found.")

render()
