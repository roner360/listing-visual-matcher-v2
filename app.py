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

def build_amazon_url_from_asin_marketplace(asin: str, marketplace: str) -> str:
    asin = safe_str(asin)
    mp = safe_str(marketplace).lower()
    if not asin or not mp:
        return ""
    # supporta sia "it" che "IT"
    return f"https://www.amazon.{mp}/dp/{asin}"

def is_nonempty(s: str) -> bool:
    return bool(s and s.strip())

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

# ---------- sidebar ----------
with st.sidebar:
    st.header("Amazon URL source")

    amazon_mode = st.radio(
        "How to get Amazon URL?",
        ["From CSV column", "Build from ASIN + MARKETPLACE"],
        index=0
    )

    amazon_url_col = None
    asin_col = None
    marketplace_col = None

    if amazon_mode == "From CSV column":
        amazon_url_col = st.selectbox("Amazon URL column", cols)
    else:
        asin_col = st.selectbox("ASIN column", cols)
        marketplace_col = st.selectbox("MARKETPLACE column (it/us/de/...)", cols)
        st.caption("URL will be: https://www.amazon.<marketplace>/dp/<asin>")

    st.divider()
    st.header("Images")

    amazon_img_col = st.selectbox("Amazon IMAGE URL column", ["(none)"] + cols)
    gross_img_col = st.selectbox("Wholesale IMAGE URL column", cols)

    # Zoom / size controls (simple + effective)
    img_width = st.slider("Image width (px)", 180, 650, 360, 10)
    img_max_height = st.slider("Max image height (px)", 160, 900, 380, 10)

    st.divider()
    st.header("Extra columns")
    show_cols = st.multiselect(
        "Other columns to show",
        [c for c in cols if c not in {
            *( [amazon_url_col] if amazon_url_col else [] ),
            *( [asin_col] if asin_col else [] ),
            *( [marketplace_col] if marketplace_col else [] ),
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
    st.session_state.match_map = {}  # row_index -> True/False

def get_match(i: int) -> bool:
    return bool(st.session_state.match_map.get(i, False))

def set_match(i: int, v: bool):
    st.session_state.match_map[i] = bool(v)

# ---------- pagination ----------
total_pages = max(1, (len(df) + page_size - 1) // page_size)

c1, c2, c3 = st.columns([1, 2, 2])
with c1:
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
with c2:
    st.write("")
    st.write(f"Total pages: **{total_pages}**")
with c3:
    st.write("")
    if st.button("Reset all MATCH"):
        st.session_state.match_map = {}
        st.rerun()

start = (page - 1) * page_size
end = min(len(df), start + page_size)
page_df = df.iloc[start:end]

st.divider()

# ---------- render ----------
for i, row in page_df.iterrows():
    with st.container(border=True):
        left, mid, right = st.columns([1, 3, 3])

        # --- LEFT: match + link ---
        with left:
            current = get_match(i)
            new_val = st.checkbox("MATCH", value=current, key=f"match_{i}")
            if new_val != current:
                set_match(i, new_val)

            # Amazon URL depending on mode
            amazon_url = ""
            if amazon_mode == "From CSV column":
                amazon_url = safe_str(row.get(amazon_url_col, "")) if amazon_url_col else ""
            else:
                asin_val = safe_str(row.get(asin_col, "")) if asin_col else ""
                mp_val = safe_str(row.get(marketplace_col, "")) if marketplace_col else ""
                amazon_url = build_amazon_url_from_asin_marketplace(asin_val, mp_val)

            if is_nonempty(amazon_url):
                st.link_button("Open Amazon", amazon_url)

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

        # --- Extra columns: show right under images (expanded) ---
        if show_cols:
            st.markdown("**Details**")
            details = []
            for c in show_cols:
                v = row.get(c, "")
                v = "" if pd.isna(v) else v
                details.append((c, str(v)))
            # show as a simple table (always expanded)
            st.table(pd.DataFrame(details, columns=["Column", "Value"]))

        # Optional: enforce max height via small CSS (applies to images in this container)
        # Keeps changes minimal and avoids heavy UI code.
        st.markdown(
            f"""
            <style>
            /* Limit image height but keep aspect ratio */
            div[data-testid="stImage"] img {{
                max-height: {img_max_height}px;
                object-fit: contain;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

st.divider()

# ---------- export ----------
out = df.copy()
out["MATCH"] = [bool(st.session_state.match_map.get(i, False)) for i in range(len(out))]
csv_bytes = out.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download CSV with MATCH",
    data=csv_bytes,
    file_name="output_with_match.csv",
    mime="text/csv",
)
st.caption("Rows not checked stay MATCH = False.")
