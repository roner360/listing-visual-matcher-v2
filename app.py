import streamlit as st
import pandas as pd

st.set_page_config(page_title="Visual Matcher", layout="wide")
st.title("Visual Matcher (CSV)")

# ---------- helpers ----------
def safe_str(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    s = str(x).strip()
    return "" if s.lower() == "nan" else s

def build_amazon_url_from_asin_marketplace(asin: str, marketplace_suffix: str) -> str:
    asin = safe_str(asin)
    mp = safe_str(marketplace_suffix).lower()
    if not asin or not mp:
        return ""
    return f"https://www.amazon.{mp}/dp/{asin}"

def is_nonempty(s: str) -> bool:
    return bool(s and s.strip())

def guess_amazon_col(df, cols):
    for c in cols:
        sample = df[c].dropna().astype(str).head(30)
        if any("m.media-amazon.com" in val for val in sample):
            return c
    return None

def guess_supplier_col(df, cols, amz_col):
    for c in cols:
        if c == amz_col: 
            continue
        sample = df[c].dropna().astype(str).head(30)
        if not sample.empty:
            # Check if strings contain typical image extensions
            hits = sum(('.jpg' in val.lower() or '.png' in val.lower() or '.jpeg' in val.lower()) for val in sample)
            if hits / len(sample) >= 0.7:  # 70% threshold is safe
                return c
    return None

# ---------- upload ----------
uploaded = st.file_uploader("Upload CSV", type=["csv"])
if not uploaded:
    st.info("Upload a CSV to start.")
    st.stop()

# Robust read: try comma, then semicolon
try:
    df = pd.read_csv(uploaded)
except Exception:
    uploaded.seek(0)
    df = pd.read_csv(uploaded, sep=";")

df = df.reset_index(drop=True)
st.caption(f"Rows: {len(df):,} | Columns: {len(df.columns)}")

cols = list(df.columns)

# Auto-guess image columns
amz_guess = guess_amazon_col(df, cols)
sup_guess = guess_supplier_col(df, cols, amz_guess)

# ---------- sidebar ----------
with st.sidebar:
    st.header("Amazon URL source")

    amazon_mode = st.radio(
        "How to get Amazon URL?",
        ["From CSV column", "Build from ASIN"],
        index=0
    )

    amazon_url_col = None
    asin_col = None
    marketplace_suffix = ""

    if amazon_mode == "From CSV column":
        amazon_url_col = st.selectbox("Amazon URL column", cols)
    else:
        asin_col = st.selectbox("ASIN column", cols)
        marketplace_suffix = st.text_input(
            "Marketplace suffix (manual)",
            placeholder="it, com, co.uk, de, fr, es …"
        )
        st.caption("URL format: https://www.amazon.<suffix>/dp/<ASIN>")

    st.divider()
    st.header("Images")

    # Set up indexes based on guesses
    amz_options = ["(none)"] + cols
    amz_index = amz_options.index(amz_guess) if amz_guess in amz_options else 0
    amazon_img_col = st.selectbox("Amazon IMAGE URL column", amz_options, index=amz_index)

    sup_options = cols
    sup_index = sup_options.index(sup_guess) if sup_guess in sup_options else 0
    gross_img_col = st.selectbox("Wholesale IMAGE URL column", sup_options, index=sup_index)

    img_width = st.slider("Image width (px)", 180, 650, 360, 10)
    img_max_height = st.slider("Max image height (px)", 160, 900, 380, 10)

    st.divider()
    st.header("Extra columns")
    show_cols = st.multiselect(
        "Other columns to show",
        [c for c in cols if c not in {
            *( [amazon_url_col] if amazon_url_col else [] ),
            *( [asin_col] if asin_col else [] ),
            gross_img_col,
            (amazon_img_col if amazon_img_col != "(none)" else "")
        }],
        default=[]
    )

    st.divider()
    page_size = st.selectbox("Rows per page", [10, 20, 50, 100], index=1)

amazon_img_col = None if amazon_img_col == "(none)" else amazon_img_col

# ---------- state ----------
if "match_map" not in st.session_state:
    st.session_state.match_map = {}
if "note_map" not in st.session_state:
    st.session_state.note_map = {}
if "current_page" not in st.session_state:
    st.session_state.current_page = 1

def get_match(i: int) -> bool:
    return bool(st.session_state.match_map.get(i, False))

def set_match(i: int, v: bool):
    st.session_state.match_map[i] = bool(v)

def update_note(i: int):
    st.session_state.note_map[i] = st.session_state[f"note_input_{i}"]

# ---------- pagination setup ----------
total_pages = max(1, (len(df) + page_size - 1) // page_size)
if st.session_state.current_page > total_pages:
    st.session_state.current_page = total_pages

def sync_page(key: str):
    st.session_state.current_page = st.session_state[key]

# --- Top Pagination Controls ---
c1, c2, c3 = st.columns([1, 2, 2])
with c1:
    st.number_input("Page", min_value=1, max_value=total_pages, value=st.session_state.current_page, step=1, key="page_top", on_change=sync_page, args=("page_top",))
with c2:
    st.write(f"Total pages: **{total_pages}**")
with c3:
    if st.button("Reset all MATCH"):
        st.session_state.match_map = {}
        st.rerun()

page = st.session_state.current_page
start = (page - 1) * page_size
end = min(len(df), start + page_size)
page_df = df.iloc[start:end]

st.divider()

# ---------- CSS: hide the checkbox visually (but keep it for state) ----------
st.markdown(
    """
    <style>
    /* Hide checkbox control but keep it in DOM to preserve state */
    div[data-testid="stCheckbox"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- render ----------
for i, row in page_df.iterrows():
    with st.container(border=True):
        left, mid, right = st.columns([1.2, 3, 3])

        # --- LEFT: Big MATCH button + Amazon link + Notes ---
        with left:
            current = get_match(i)

            # Hidden checkbox to store state (key remains stable)
            _ = st.checkbox("MATCH", value=current, key=f"match_{i}")

            # Big toggle button (same style/size as link_button)
            btn_label = "✅ MATCH" if not current else "❌ UNMATCH"
            if st.button(btn_label, key=f"btn_match_{i}", use_container_width=True):
                set_match(i, not current)
                st.rerun()

            amazon_url = ""
            if amazon_mode == "From CSV column":
                amazon_url = safe_str(row.get(amazon_url_col, "")) if amazon_url_col else ""
            else:
                asin_val = safe_str(row.get(asin_col, "")) if asin_col else ""
                amazon_url = build_amazon_url_from_asin_marketplace(asin_val, marketplace_suffix)

            if is_nonempty(amazon_url):
                st.link_button("Open Amazon", amazon_url, use_container_width=True)
            
            # Notes Input Field
            st.text_input(
                "Notes", 
                value=st.session_state.note_map.get(i, ""), 
                key=f"note_input_{i}", 
                on_change=update_note, 
                args=(i,)
            )

        # --- MID: Amazon image ---
        with mid:
            st.caption("Amazon image")
            if amazon_img_col:
                img_url = safe_str(row.get(amazon_img_col, ""))
                if is_nonempty(img_url):
                    st.image(img_url, width=img_width)
                else:
                    st.warning("Amazon image URL is empty.")
            else:
                st.info("No Amazon image column selected.")

        # --- RIGHT: Wholesale image ---
        with right:
            st.caption("Wholesale image")
            w_url = safe_str(row.get(gross_img_col, ""))
            if is_nonempty(w_url):
                st.image(w_url, width=img_width)
            else:
                st.warning("Wholesale image URL is empty.")

        # --- Extra columns (always visible, under images) ---
        if show_cols:
            st.markdown("**Details**")
            details = []
            for c in show_cols:
                v = row.get(c, "")
                v = "" if pd.isna(v) else v
                details.append((c, str(v)))
            st.table(pd.DataFrame(details, columns=["Column", "Value"]))

        # Limit image height (zoom control)
        st.markdown(
            f"""
            <style>
            div[data-testid="stImage"] img {{
                max-height: {img_max_height}px;
                object-fit: contain;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

st.divider()

# --- Bottom Pagination Controls ---
c1_b, c2_b, c3_b = st.columns([1, 2, 2])
with c1_b:
    st.number_input("Page (bottom)", min_value=1, max_value=total_pages, value=st.session_state.current_page, step=1, key="page_bottom", on_change=sync_page, args=("page_bottom",))
with c2_b:
    st.write(f"Total pages: **{total_pages}**")

st.divider()

# ---------- export ----------
out = df.copy()
out["MATCH"] = [bool(st.session_state.match_map.get(i, False)) for i in range(len(out))]
out["Notes"] = [str(st.session_state.note_map.get(i, "")) for i in range(len(out))]

csv_bytes = out.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download CSV with MATCH & Notes",
    data=csv_bytes,
    file_name="output_with_match.csv",
    mime="text/csv",
)
st.caption("Rows not checked stay MATCH = False. Empty notes stay blank.")
