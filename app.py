# app.py

'''
Streamlit app to validate and correct JSON extracted data using Streamlit FilesConnection for GCS and local file locking.

Raw JSON files in GCS under 'jsons/' prefix;
Corrected JSONs written to GCS under 'corrected/' prefix;
Images in GCS under 'images/' prefix.
Locks stored locally in data/locks/ to prevent concurrent edits in one instance.

Run:
    pip install streamlit st-files-connection portalocker
    streamlit run app.py
'''

import os
import re
import json
import streamlit as st
import portalocker
from st_files_connection import FilesConnection

# Page configuration
st.set_page_config(page_title="JSON Validator", layout="wide")

# Local lock directory
LOCK_DIR = 'data/locks'
os.makedirs(LOCK_DIR, exist_ok=True)

# Initialize GCS connection via Streamlit FilesConnection
# Requires .streamlit/secrets.toml:
# GCS_BUCKET = "my-annotation-data"
conn = st.connection("gcs", type=FilesConnection)
GCS_BUCKET = st.secrets["GCS_BUCKET"]

# Utility to clean raw JSON (replace '-' with null, quote leading zeros)
def clean_json_text(raw: str) -> str:
    t = re.sub(r'(:\s*)-(\s*[,\}])', r'\1null\2', raw)
    t = re.sub(r'(:\s*)(0\d+)(\s*[,\}])', r'\1"\2"\3', t)
    return t

# List JSON filenames from GCS (unprocessed + unlocked)
def list_jsons():
    prefix = f"{GCS_BUCKET}/jsons/"
    all_paths = conn.list(prefix)
    raw_files = [p.split(f"{prefix}",1)[1] for p in all_paths]
    # filter out those already corrected
    corr_prefix = f"{GCS_BUCKET}/corrected/"
    corr_paths = conn.list(corr_prefix)
    corr_files = {p.split(f"{corr_prefix}",1)[1] for p in corr_paths}
    avail = []
    for fname in sorted(raw_files):
        if fname in corr_files:
            continue
        lock_file = os.path.join(LOCK_DIR, fname + '.lock')
        if os.path.exists(lock_file):
            continue
        avail.append(fname)
    return avail

# Session state index
if 'idx' not in st.session_state:
    st.session_state.idx = 0
files = list_jsons()
if not files:
    st.warning('No unprocessed records available.')
    st.stop()

# Navigation buttons
col_prev, col_next = st.columns(2)
if col_prev.button('Previous') and st.session_state.idx > 0:
    st.session_state.idx -= 1
if col_next.button('Next') and st.session_state.idx < len(files)-1:
    st.session_state.idx += 1

current = files[st.session_state.idx]
st.title(f"Record {st.session_state.idx+1}/{len(files)}: {current}")

# Acquire a non-blocking lock
lock_path = os.path.join(LOCK_DIR, current + '.lock')
try:
    lock = portalocker.Lock(lock_path, 'w', timeout=0)
    lock.acquire()
    st.session_state['lock'] = lock
except portalocker.exceptions.LockException:
    st.warning('This record is being edited by someone else.')
    st.stop()

# Load JSON from GCS
try:
    raw = conn.read(f"{GCS_BUCKET}/jsons/{current}", input_format="text", ttl=600)
    data = json.loads(clean_json_text(raw))
except Exception as e:
    st.error(f'Error loading JSON: {e}')
    lock.release()
    st.stop()

# Sidebar: display image from GCS
with st.sidebar:
    st.header('Image Reference')
    img_base = data.get('image_filename') or os.path.splitext(current)[0]
    found = False
    for ext in ['.jpg', '.jpeg', '.png', '.tif']:
        path = f"{GCS_BUCKET}/images/{img_base}{ext}"
        try:
            img_bytes = conn.read(path, input_format="bytes", ttl=600)
            st.image(img_bytes, caption=f'{img_base}{ext}', use_column_width=True)
            found = True
            break
        except Exception:
            continue
    if not found:
        st.warning(f'Image not found for {img_base}')

# Extract 'validated_json' section or empty
to_edit = data.get('validated_json') if isinstance(data.get('validated_json'), dict) else {}
if not to_edit:
    st.warning('No validated_json section; nothing to edit.')

# Helper to convert strings back to original types
def type_convert(val: str, orig):
    if isinstance(orig, bool): return val.lower() in ('true','1','yes')
    if isinstance(orig, int):
        try: return int(val)
        except: return val
    if isinstance(orig, float):
        try: return float(val)
        except: return val
    if orig is None:
        low = val.strip().lower()
        return None if low in ('','null','none') else val
    return val

# Main form for editing
with st.form('edit_form'):
    updated = {}
    for section, content in to_edit.items():
        st.subheader(section.replace('_',' ').title())
        if isinstance(content, dict):
            for key, orig in content.items():
                cols = st.columns((3,1))
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
                    cols = st.columns((3,1))
                    inp = cols[0].text_input(f'{section}[{idx}].{key}', value=str(orig))
                    unsure = cols[1].checkbox('Unsure', key=f'{section}[{idx}].{key}_unsure')
                    temp[key] = type_convert(inp, orig)
                    temp[f'{key}_unsure'] = unsure
                updated[section].append(temp)
        else:
            cols = st.columns((3,1))
            inp = cols[0].text_input(section, value=str(content))
            unsure = cols[1].checkbox('Unsure', key=f'{section}_unsure')
            updated[section] = type_convert(inp, content)
            updated[f'{section}_unsure'] = unsure
    if st.form_submit_button('Save corrections'):
        data['validated_json'] = updated
        try:
            conn.write(f"{GCS_BUCKET}/corrected/{current}", json.dumps(data, ensure_ascii=False, indent=2), output_format="text")
            st.success('Saved corrected record to GCS.')
            lock.release()
            os.remove(lock_path)
        except Exception as e:
            st.error(f'Error saving corrected JSON: {e}')
