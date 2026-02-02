import os
from typing import Dict, List

import pandas as pd
import streamlit as st

# Keepa client
import keepa


# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Listing Visual Matcher", layout="wide")
st.title("Listing Visual Matcher (Keepa)")

# -----------------------------
# Optional: simple password gate
# -----------------------------
def require_password():
    app_pwd = os.getenv("APP_PASSWORD", "").strip()
    if not app_pwd:
        return  # no password required

    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False

    if st.session_state.auth_ok:
        return

    st.subheader("Login")
    pwd = st.text_input("Password", type="password")
    if st.button("Enter"):
        if pwd == app_pwd:
            st.session_state.auth_ok = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()


require_password()


# -----------------------------
# Marketplace mapping
# -----------------------------
MARKETPLACE_DOMAIN = {
    "it": "amazon.it",
    "de": "amazon.de",
    "fr": "amazon.fr",
    "es": "amazon.es",
    "uk": "amazon.co.uk",
    "us": "amazon.com",
    "nl": "amazon.nl",
    "se": "amazon.se",
    "pl": "amazon.pl",
}

def build_amazon_dp_url(asin: str, marketplace: str) -> str:
    asin = (asin or "").strip()
    mp = (marketplace or "").strip().lower()
    domain = MARKETPLACE_DOMAIN.get(mp, "")
    if not asin or not domain:
        return ""
    return f"https://www.{domain}/dp/{asin}"

def keepa_domain_code(marketplace: str) -> str:
    # Keepa expects 'IT', 'DE', 'UK', ...
    return (marketplace or "").strip().upper()

def keepa_image_to_cdn_url(image_id: str) -> str:
    """
    Keepa product['imagesCSV'] contains image identifiers.
    Usually they already include .jpg; if not, append .jpg.
    """
    img = (image_id or "").strip()
    if not img:
        return ""
    if "." not in img:
        img += ".jpg"
    # Amazon image CDN
    return f"https://m.media-amazon.com/images/I/{img}"


# -----------------------------
# Keepa helpers (cached)
# -----------------------------
def get_keepa_key() -> str:
    # Streamlit secrets become env vars automatically on Streamlit Cloud
    return os.getenv("KEEPA_KEY", "").strip()

@st.cache_resource
def get_keepa_client():
    key = get_keepa_key()
    if not key:
        return None
    try:
        return keepa.Keepa(key)
    except Exception:
        return None

@st.cache_data(show_spinner=False, ttl=24 * 60 * 60)
def keepa_fetch_first_images(asins: List[str], marketplace: str) -> Dict[str, str]:
    """
    Batch query for the ASINs on the current page.
    Returns dict: asin -> first_image_url (or "")
    Cached 24h for speed.
    """
    asins = [a.strip() for a in asins if a and str(a).strip()]
    if not asins:
        return {}

    api = get_keepa_client()
    if api is None:
        return {a: "" for a in asins}

    domain = keepa_domain_code(marketplace)
    try:
        products = api.query(asins, domain=domain, stats=False)
    except Exception:
        # In case of temporary errors / token limits
        return {a: "" for a in asins}

    out: Dict[str, str] = {a: "" for a in asins}
    for p in products or []:
        asin = (p.get("asin") or "").strip()
        if not asin:
            continue
        images_csv = (p.get("imagesCSV") or "").strip()
        if images_csv:
            first = images_csv.split(",")[0].strip()
            out[asin] = keepa_image_to_cdn_url(first)
    return out


# -----------------------------
# CSV upload
# -----------------------------
uploaded = st.file_uploader("Upload CSV", type=["csv"])
if not uploaded:
    st.info("Upload a CSV to start.")
    st.stop()

# robust read: comma then semicolon
try:
    df = pd.read_csv(uploaded)
except Exception:
    uploaded.seek(0)
    df = pd.read_csv(uploaded, sep=";")

df = df.reset_index(drop=True)
cols = list(df.columns)
st.caption(f"Rows: {len(df):,} | Columns: {len(cols)}")


# -----------------------------
# Sidebar mapping + settings
# -----------------------------
with st.sidebar:
    st.header("Settings")

    # Marketplace is same for the entire CSV
    marketplace = st.selectbox(
        "Marketplace (for this CSV)",
        options=list(MARKETPLACE_DOMAIN.keys()),
        index=list(MARKETPLACE_DOMAIN.keys()).index("it") if "it" in MARKETPLACE_DOMAIN else 0,
    )

    st.divider()
    st.header("Column mapping")

    asin_col = st.selectbox("ASIN column", cols)

    gross_img_col = st.selectbox("Wholesale IMAGE URL column", cols)

    show_cols = st.multiselect(
        "Other columns to show",
        [c for c in cols if c not in {asin_col, gross_img_col}],
        default=[],
    )

    st.divider()
    page_size = st.selectbox("Rows per page", [10, 20, 50, 100], index=1)

    st.divider()
    show_amazon_images = st.checkbox("Show Amazon images (Keepa)", value=True)
    show_wholesale_images = st.checkbox("Show Wholesale images", value=True)


# Validate Keepa key
if show_amazon_images and not get_keepa_key():
    st.warning("KEEPA_KEY not found. Add it to Streamlit Secrets to show Amazon images.")


# -----------------------------
# Match state
# -----------------------------
if "match_map" not in st.session_state:
    st.session_state.match_map = {}  # row_index -> True/False

def get_match(i: int) -> bool:
    return bool(st.session_state.match_map.get(i, False))

def set_match(i: int, v: bool):
    st.session_state.match_map[i] = bool(v)


# -----------------------------
# Pagination
# -----------------------------
total_pages = max(1, (len(df) + page_size - 1) // page_size)

c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
with c1:
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
with c2:
    st.write("")
    st.write(f"Total pages: **{total_pages}**")
with c3:
    st.write("")
    if st.button("Reset MATCH"):
        st.session_state.match_map = {}
        st.rerun()
with c4:
    st.write("")
    st.write(f"Marketplace: **{marketplace}**")

start = (page - 1) * page_size
end = min(len(df), start + page_size)
page_df = df.iloc[start:end]

st.divider()


# -----------------------------
# Keepa batch fetch (for this page only)
# -----------------------------
page_asins = [str(row.get(asin_col, "") or "").strip() for _, row in page_df.iterrows()]
img_map: Dict[str, str] = {}

if show_amazon_images and page_asins:
    with st.spinner("Fetching Amazon images from Keepa (this page)..."):
        img_map = keepa_fetch_first_images(page_asins, marketplace)


# -----------------------------
# Render rows
# -----------------------------
for i, row in page_df.iterrows():
    asin = str(row.get(asin_col, "") or "").strip()
    amazon_url = build_amazon_dp_url(asin, marketplace) if asin else ""

    with st.container(border=True):
        left, mid, right = st.columns([1.2, 3, 3])

        # Left: match + link
        with left:
            current = get_match(i)
            new_val = st.checkbox("MATCH", value=current, key=f"match_{i}")
            if new_val != current:
                set_match(i, new_val)

            st.caption("ASIN")
            st.code(asin or "-", language=None)

            if amazon_url:
                st.link_button("Open Amazon", amazon_url)

        # Mid: Amazon image
        with mid:
            st.caption("Amazon image (Keepa)")
            if show_amazon_images:
                img_url = img_map.get(asin, "") if asin else ""
                if img_url:
                    st.image(img_url, use_container_width=True)
                else:
                    st.warning("No image from Keepa for this ASIN.")
            else:
                st.info("Amazon images disabled.")

        # Right: Wholesale image
        with right:
            st.caption("Wholesale image")
            if show_wholesale_images:
                w_url = str(row.get(gross_img_col, "") or "").strip()
                if w_url:
                    st.image(w_url, use_container_width=True)
                else:
                    st.warning("Wholesale image URL is empty.")
            else:
                st.info("Wholesale images disabled.")

        # Details
        if show_cols:
            details = {c: ("" if pd.isna(row.get(c)) else row.get(c)) for c in show_cols}
            st.json(details, expanded=False)

st.divider()


# -----------------------------
# Export
# -----------------------------
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
