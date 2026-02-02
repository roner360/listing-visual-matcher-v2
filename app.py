import streamlit as st
import pandas as pd

st.set_page_config(page_title="Visual Matcher", layout="wide")
st.title("Visual Matcher (CSV)")

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

# ---- Column mapping (user chooses) ----
with st.sidebar:
    st.header("Column mapping")
    amazon_url_col = st.selectbox("Amazon URL column", cols)
    amazon_img_col = st.selectbox("Amazon IMAGE URL column", ["(none)"] + cols)

    gross_img_col = st.selectbox("Wholesale IMAGE URL column", cols)

    show_cols = st.multiselect(
        "Other columns to show",
        [c for c in cols if c not in {amazon_url_col, gross_img_col, amazon_img_col if amazon_img_col != "(none)" else ""}],
        default=[]
    )

    st.divider()
    page_size = st.selectbox("Rows per page", [10, 20, 50, 100], index=1)

# If user doesn't provide amazon image column, we won't fetch it.
amazon_img_col = None if amazon_img_col == "(none)" else amazon_img_col

# ---- State for matches ----
if "match_map" not in st.session_state:
    st.session_state.match_map = {}  # row_index -> True/False


def get_match(i: int) -> bool:
    return bool(st.session_state.match_map.get(i, False))


def set_match(i: int, v: bool):
    st.session_state.match_map[i] = bool(v)


# ---- Pagination ----
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

# ---- Render rows ----
for i, row in page_df.iterrows():
    with st.container(border=True):
        left, mid, right = st.columns([1, 3, 3])

        with left:
            current = get_match(i)
            new_val = st.checkbox("MATCH", value=current, key=f"match_{i}")
            if new_val != current:
                set_match(i, new_val)

            # show amazon link (always)
            amazon_url = str(row.get(amazon_url_col, "") or "")
            if amazon_url.strip():
                st.link_button("Open Amazon", amazon_url.strip())

        with mid:
            st.caption("Amazon image")
            if amazon_img_col:
                img_url = str(row.get(amazon_img_col, "") or "").strip()
                if img_url:
                    # Streamlit downloads & shows image itself
                    st.image(img_url, use_container_width=True)
                else:
                    st.warning("Amazon image URL is empty.")
            else:
                st.info("No Amazon image column selected.")

        with right:
            st.caption("Wholesale image")
            w_url = str(row.get(gross_img_col, "") or "").strip()
            if w_url:
                st.image(w_url, use_container_width=True)
            else:
                st.warning("Wholesale image URL is empty.")

        if show_cols:
            details = {c: ("" if pd.isna(row.get(c)) else row.get(c)) for c in show_cols}
            st.json(details, expanded=False)

st.divider()

# ---- Export ----
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
