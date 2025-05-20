# app.py

'''
Streamlit app to validate and correct JSON extracted data with Google Cloud Storage backend and local file locking.

Unprocessed JSON files reside in GCS under 'jsons/' prefix;
Corrected outputs are written to GCS under 'corrected/' prefix;
Images live in GCS under 'images/' prefix.
Locks are stored locally in data/locks/ to prevent concurrent edits in a single container.

Run:
    pip install streamlit google-cloud-storage portalocker
    streamlit run app.py
'''

import os
import re
import json
import streamlit as st
import portalocker
from google.cloud import storage

# Page config
st.set_page_config(page_title="JSON Validator", layout="wide")

# Directories for local locks
dir_locks = 'data/locks'
os.makedirs(dir_locks, exist_ok=True)

# GCS configuration (set in Streamlit secrets)
GCS_BUCKET = st.secrets["GCS_BUCKET"]
# Prepare service account credentials for ADC
import tempfile, os
sa_json = st.secrets.get("GCP_SERVICE_ACCOUNT_KEY")
# secrets.toml can store JSON keys as a table or a string
if isinstance(sa_json, dict):
    sa_str = json.dumps(sa_json)
else:
    sa_str = sa_json
# Write key to a temp file and point SDK to it
tf = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".json")
 tf.write(sa_str)
 tf.flush()
 os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tf.name
# Initialize client using Application Default Credentials
client = storage.Client()
bucket = client.bucket(GCS_BUCKET)

# Utility: clean raw JSON text
def clean_json_text(raw: str) -> str:
    t = re.sub(r'(:\s*)-(\s*[,\}])', r'\1null\2', raw)
    t = re.sub(r'(:\s*)(0\d+)(\s*[,\}])', r'\1"\2"\3', t)
    return t

# List available JSON filenames in GCS (unprocessed + unlocked)
def list_jsons():
    # all raw keys
    blobs = client.list_blobs(GCS_BUCKET, prefix='jsons/')
    raw_files = [b.name.split('/',1)[1] for b in blobs if not b.name.endswith('/')]
    # filter out corrected
    corr_blobs = client.list_blobs(GCS_BUCKET, prefix='corrected/')
    corr_files = {b.name.split('/',1)[1] for b in corr_blobs if not b.name.endswith('/')}
    avail = []
    for fname in sorted(raw_files):
        if fname in corr_files:
            continue
        lock_path = os.path.join(dir_locks, fname + '.lock')
        if os.path.exists(lock_path):
            continue
        avail.append(fname)
    return avail

# Navigation state
if 'idx' not in st.session_state:
    st.session_state.idx = 0
files = list_jsons()
if not files:
    st.warning('No unprocessed records available in GCS.')
    st.stop()

# Navigation UI
col1, col2 = st.columns(2)
if col1.button('Previous') and st.session_state.idx > 0:
    st.session_state.idx -= 1
if col2.button('Next') and st.session_state.idx < len(files)-1:
    st.session_state.idx += 1

current = files[st.session_state.idx]
st.title(f"Record {st.session_state.idx+1}/{len(files)}: {current}")

# Acquire local lock
lock_file = os.path.join(dir_locks, current + '.lock')
try:
    lock = portalocker.Lock(lock_file, 'w', timeout=0)
    lock.acquire()
    st.session_state['lock'] = lock
except portalocker.exceptions.LockException:
    st.warning('This record is being edited by someone else.')
    st.stop()

# Load JSON from GCS
try:
    blob = bucket.blob(f'jsons/{current}')
    raw = blob.download_as_text()
    data = json.loads(clean_json_text(raw))
except Exception as e:
    st.error(f'Error loading JSON from GCS: {e}')
    lock.release()
    st.stop()

# Sidebar: display image from GCS
with st.sidebar:
    st.header('Image Reference')
    img_base = data.get('image_filename') or os.path.splitext(current)[0]
    found = False
    for ext in ['.jpg','.jpeg','.png','.tif']:
        name = img_base + ext
        blob = bucket.blob(f'images/{name}')
        if blob.exists():
            st.image(blob.download_as_bytes(), caption=name, use_column_width=True)
            found = True
            break
    if not found:
        st.warning(f'Image not found for {img_base}')

# Extract validated_json section
to_edit = data.get('validated_json') if isinstance(data.get('validated_json'), dict) else {}
if not to_edit:
    st.warning('No validated_json section; nothing to edit.')

# Type converter
def type_convert(val, orig):
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

# Editable form
with st.form('edit'):
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
            for i, entry in enumerate(content):
                st.markdown(f"**{section.title()} #{i+1}**")
                temp = {}
                for key, orig in entry.items():
                    cols = st.columns((3,1))
                    inp = cols[0].text_input(f'{section}[{i+1}].{key}', value=str(orig))
                    unsure = cols[1].checkbox('Unsure', key=f'{section}[{i+1}].{key}_unsure')
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
            out_blob = bucket.blob(f'corrected/{current}')
            out_blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2), content_type='application/json')
            st.success('Saved corrected record to GCS.')
            # release lock and cleanup
            lock.release()
            os.remove(lock_file)
        except Exception as e:
            st.error(f'Error saving to GCS: {e}')
