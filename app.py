import os
import re
import json
import streamlit as st
import portalocker
from google.oauth2 import service_account
from google.cloud import storage
from datetime import datetime, timedelta
import hashlib

# Page configuration - MUST BE FIRST
st.set_page_config(page_title="JSON Validator", layout="wide")

# Ensure Streamlit version supports rerun (>=1.27.0)
# If deploying on Streamlit Cloud, add `streamlit>=1.27.0` to requirements.txt

# Load GCS credentials from Streamlit secrets or fallback to local key
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_gcs_config():
    try:
        gcs_conf = dict(st.secrets["connections"]["gcs"])
        gcs_conf["private_key"] = gcs_conf["private_key"].replace("\\n", "\n")
    except Exception:
        with open("key.json") as f:
            gcs_conf = json.load(f)
    return gcs_conf

# Initialize Google Cloud Storage client with caching
@st.cache_resource
def get_gcs_client():
    """Cache the GCS client connection"""
    conf = load_gcs_config()
    creds = service_account.Credentials.from_service_account_info(conf)
    return storage.Client(credentials=creds, project=conf.get("project_id"))

# Get cached client and bucket
def get_bucket():
    client = get_gcs_client()
    conf = load_gcs_config()
    bucket_name = conf.get("GCS_BUCKET", "card_annotation")
    return client.bucket(bucket_name)

# Local lock directory
LOCK_DIR = 'data/locks'
os.makedirs(LOCK_DIR, exist_ok=True)

# Utility: clean raw JSON
@st.cache_data
def clean_json_text(raw: str) -> str:
    """Cache JSON cleaning results"""
    t = re.sub(r'(:\s*)-(\s*[,\}])', r'\1null\2', raw)
    t = re.sub(r'(:\s*)(0\d+)(\s*[,\}])', r'\1"\2"\3', t)
    return t

# Cache the list of blobs from GCS
@st.cache_data(ttl=60)  # Cache for 1 minute
def get_gcs_file_lists():
    """Fetch and cache the list of files from GCS"""
    try:
        client = get_gcs_client()
        bucket = get_bucket()
        
        raw_blobs = list(client.list_blobs(bucket, prefix="jsons/"))
        raw_paths = [os.path.basename(b.name) for b in raw_blobs if b.name.endswith(".json")]
        
        corr_blobs = list(client.list_blobs(bucket, prefix="corrected/"))
        corr_files = {os.path.basename(b.name) for b in corr_blobs if b.name.endswith(".json")}
        
        return raw_paths, corr_files
    except Exception as e:
        st.error(f"Error listing JSON files: {e}")
        return [], set()

# List available JSONs not yet corrected and not locked
def list_jsons():
    raw_paths, corr_files = get_gcs_file_lists()
    
    avail = []
    for fname in sorted(raw_paths):
        if fname in corr_files:
            continue
        lock_file = os.path.join(LOCK_DIR, fname + '.lock')
        if os.path.exists(lock_file):
            continue
        avail.append(fname)
    return avail

# Cache JSON file content
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_json_from_gcs(filename):
    """Load and cache JSON content from GCS"""
    try:
        bucket = get_bucket()
        blob = bucket.blob(f"jsons/{filename}")
        raw = blob.download_as_text()
        cleaned = clean_json_text(raw)
        data = json.loads(cleaned)
        return data, None
    except Exception as e:
        return None, str(e)

# Cache image data
@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_image_from_gcs(img_base):
    """Load and cache image from GCS"""
    bucket = get_bucket()
    for ext in ['.jpg', '.jpeg', '.png', '.tif']:
        path = f"images/{img_base}{ext}"
        blob = bucket.blob(path)
        if blob.exists():
            img_bytes = blob.download_as_bytes()
            return img_bytes, f'{img_base}{ext}'
    return None, None

# Select JSON file
if 'idx' not in st.session_state:
    st.session_state.idx = 0

# Add a refresh button to clear cache if needed
col1, col2, col3 = st.columns([1, 1, 2])
with col3:
    if st.button('🔄 Refresh File List'):
        get_gcs_file_lists.clear()
        st.rerun()

files = list_jsons()
if not files:
    st.warning('No unprocessed records available.')
    st.stop()

col_prev, col_next = st.columns(2)
if col_prev.button('Previous') and st.session_state.idx > 0:
    st.session_state.idx -= 1
if col_next.button('Next') and st.session_state.idx < len(files) - 1:
    st.session_state.idx += 1

current = files[st.session_state.idx]
st.title(f"Record {st.session_state.idx + 1}/{len(files)}: {current}")

# Lock current file
lock_path = os.path.join(LOCK_DIR, current + '.lock')
try:
    lock = portalocker.Lock(lock_path, 'w', timeout=0)
    lock.acquire()
    st.session_state['lock'] = lock
except portalocker.exceptions.LockException:
    st.warning('This record is being edited by someone else.')
    st.stop()

# Load JSON using cache
data, error = load_json_from_gcs(current)
if error:
    st.error(f'Error loading JSON: {error}')
    lock.release()
    os.remove(lock_path)
    st.stop()

# Sidebar: load and show image using cache
with st.sidebar:
    st.header('Image Reference')
    img_base = data.get('image_filename') or os.path.splitext(current)[0]
    
    img_bytes, img_name = load_image_from_gcs(img_base)
    if img_bytes:
        st.image(img_bytes, caption=img_name, use_container_width=True)
    else:
        st.warning(f'Image not found for {img_base}')

# Edit form for validated_json
validated = data.get('validated_json') if isinstance(data.get('validated_json'), dict) else {}
if not validated:
    st.warning('No validated_json section; nothing to edit.')

def type_convert(val: str, orig):
    if isinstance(orig, bool): return val.lower() in ('true', '1', 'yes')
    if isinstance(orig, int):
        try: return int(val)
        except: return None
    if isinstance(orig, float):
        try: return float(val)
        except: return val
    if orig is None:
        low = val.strip().lower()
        return None if low in ('', 'null', 'none') else val
    return val

with st.form('edit_form'):
    updated = {}
    for section, content in validated.items():
        st.subheader(section.replace('_', ' ').title())
        if isinstance(content, dict):
            for key, orig in content.items():
                cols = st.columns((3, 1))
                inp = cols[0].text_input(f'{section}.{key}', value=str(orig))
                unsure = cols[1].checkbox('Unsure', key=f'{section}.{key}_unsure')
                updated.setdefault(section, {})[key] = type_convert(inp, orig)
                updated[section][f'{key}_unsure'] = unsure
        elif isinstance(content, list):
            updated.setdefault(section, [])
            for idx, entry in enumerate(content, start=1):
                st.markdown(f"**{section.title()} #{idx}**")
                temp = {}
                for key, orig in entry.items():
                    cols = st.columns((3, 1))
                    inp = cols[0].text_input(f'{section}[{idx}].{key}', value=str(orig))
                    unsure = cols[1].checkbox('Unsure', key=f'{section}[{idx}].{key}_unsure')
                    temp[key] = type_convert(inp, orig)
                    temp[f'{key}_unsure'] = unsure
                updated[section].append(temp)
        else:
            cols = st.columns((3, 1))
            inp = cols[0].text_input(section, value=str(content))
            unsure = cols[1].checkbox('Unsure', key=f'{section}_unsure')
            updated[section] = type_convert(inp, content)
            updated[f'{section}_unsure'] = unsure

    if st.form_submit_button('Save corrections'):
        data['validated_json'] = updated
        try:
            bucket = get_bucket()
            blob = bucket.blob(f"corrected/{current}")
            blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2), content_type='application/json')
            st.success('Saved corrected record to GCS.')
            
            # Clear relevant caches after saving
            get_gcs_file_lists.clear()
            load_json_from_gcs.clear()
            
            lock.release()
            os.remove(lock_path)
            
            # Rerun the app to refresh file list
            if hasattr(st, 'rerun'):
                st.rerun()
            elif hasattr(st, 'experimental_rerun'):
                st.experimental_rerun()
            else:
                st.warning('Upgrade Streamlit to >=1.27.0 to enable rerun functionality.')
        except Exception as e:
            st.error(f'Error saving corrected JSON: {e}')
            lock.release()
            os.remove(lock_path)

# Performance monitoring in development
if st.secrets.get("debug", False):
    with st.expander("Cache Statistics"):
        st.write("Cache hits can significantly improve performance.")
        st.write("- File list cache: 1 minute TTL")
        st.write("- JSON content cache: 5 minutes TTL")
        st.write("- Image cache: 10 minutes TTL")
        st.write("- GCS client: Persistent resource cache")