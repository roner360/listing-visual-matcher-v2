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
            hits = sum(
                (".jpg" in val.lower() or ".png" in val.lower() or ".jpeg" in val.lower())
                for val in sample
            )
            if hits / len(sample) >= 0.7:
                return c
    return None


# ---------- upload ----------
uploaded = st.file_uploader("Upload CSV", type=["csv"])
if not uploaded:
    st.info("Upload a CSV to start.")
    st.stop()

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

# ---------- session state ----------
if "match_map" not in st.session_state:
    st.session_state.match_map = {}

if "note_map" not in st.session_state:
    st.session_state.note_map = {}

if "current_page" not in st.session_state:
    st.session_state.current_page = 1

if "page_top" not in st.session_state:
    st.session_state.page_top = 1

if "page_bottom" not in st.session_state:
    st.session_state.page_bottom = 1


# ---------- state helpers ----------
def get_match(i: int) -> bool:
    return bool(st.session_state.match_map.get(i, False))

def set_match(i: int, v: bool):
    st.session_state.match_map[i] = bool(v)

def toggle_match(i: int):
    st.session_state.match_map[i] = not bool(st.session_state.match_map.get(i, False))

def update_note(i: int):
    st.session_state.note_map[i] = st.session_state.get(f"note_input_{i}", "")

def sync_page_from_top():
    new_page = int(st.session_state.page_top)
    st.session_state.current_page = new_page
    st.session_state.page_bottom = new_page

def sync_page_from_bottom():
    new_page = int(st.session_state.page_bottom)
    st.session_state.current_page = new_page
    st.session_state.page_top = new_page

def reset_all_match():
    st.session_state.match_map = {}


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

    excluded = set()
    if amazon_url_col:
        excluded.add(amazon_url_col)
    if asin_col:
        excluded.add(asin_col)
    excluded.add(gross_img_col)
    if amazon_img_col != "(none)":
        excluded.add(amazon_img_col)

    show_cols = st.multiselect(
        "Other columns to show",
        [c for c in cols if c not in excluded],
        default=[]
    )

    st.divider()
    page_size = st.selectbox("Rows per page", [10, 20, 50, 100], index=1)

amazon_img_col = None if amazon_img_col == "(none)" else amazon_img_col


# ---------- pagination setup ----------
total_pages = max(1, (len(df) + page_size - 1) // page_size)

if st.session_state.current_page < 1:
    st.session_state.current_page = 1
if st.session_state.current_page > total_pages:
    st.session_state.current_page = total_pages

# keep both pagers aligned
st.session_state.page_top = st.session_state.current_page
st.session_state.page_bottom = st.session_state.current_page


# ---------- top pagination ----------
c1, c2, c3 = st.columns([1, 2, 2])
with c1:
    st.number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        step=1,
        key="page_top",
        on_change=sync_page_from_top,
    )
with c2:
    st.write(f"Total pages: **{total_pages}**")
with c3:
    st.button("Reset all MATCH", on_click=reset_all_match)

page = st.session_state.current_page
start = (page - 1) * page_size
end = min(len(df), start + page_size)
page_df = df.iloc[start:end]

st.divider()


# ---------- global css ----------
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


# ---------- render ----------
for i, row in page_df.iterrows():
    with st.container(border=True):
        left, mid, right = st.columns([1.2, 3, 3])

        # --- LEFT: match button + amazon link + notes ---
        with left:
            current = get_match(i)
            btn_label = "✅ MATCH" if not current else "❌ UNMATCH"

            st.button(
                btn_label,
                key=f"btn_match_{i}",
                use_container_width=True,
                on_click=toggle_match,
                args=(i,),
            )

            amazon_url = ""
            if amazon_mode == "From CSV column":
                amazon_url = safe_str(row.get(amazon_url_col, "")) if amazon_url_col else ""
            else:
                asin_val = safe_str(row.get(asin_col, "")) if asin_col else ""
                amazon_url = build_amazon_url_from_asin_marketplace(asin_val, marketplace_suffix)

            if is_nonempty(amazon_url):
                st.link_button("Open Amazon", amazon_url, use_container_width=True)

            st.text_input(
                "Notes",
                value=st.session_state.note_map.get(i, ""),
                key=f"note_input_{i}",
                on_change=update_note,
                args=(i,),
            )

        # --- MID: Amazon image ---
        with mid:
            st.caption("Amazon image")

            img_url = ""
            if amazon_img_col:
                img_url = safe_str(row.get(amazon_img_col, ""))
            else:
                candidates = []
                for c in row.index:
                    val = safe_str(row.get(c, ""))
                    if "m.media" in val:
                        candidates.append(val)
                if candidates:
                    img_url = min(candidates, key=len)

            if is_nonempty(img_url):
                st.image(img_url, width=img_width)
            else:
                st.warning("Amazon image not found.")

        # --- RIGHT: Wholesale image ---
        with right:
            st.caption("Wholesale image")
            w_url = safe_str(row.get(gross_img_col, ""))
            if is_nonempty(w_url):
                st.image(w_url, width=img_width)
            else:
                st.warning("Wholesale image URL is empty.")

        # --- Extra columns ---
        if show_cols:
            st.markdown("**Details**")
            details = []
            for c in show_cols:
                v = row.get(c, "")
                v = "" if pd.isna(v) else v
                details.append((c, str(v)))
            st.table(pd.DataFrame(details, columns=["Column", "Value"]))

st.divider()


# ---------- bottom pagination ----------
c1_b, c2_b, c3_b = st.columns([1, 2, 2])
with c1_b:
    st.number_input(
        "Page (bottom)",
        min_value=1,
        max_value=total_pages,
        step=1,
        key="page_bottom",
        on_change=sync_page_from_bottom,
    )
with c2_b:
    st.write(f"Total pages: **{total_pages}**")
with c3_b:
    st.write(f"Current page: **{st.session_state.current_page}**")

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
