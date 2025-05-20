import os
import re
import json
import streamlit as st
import portalocker
from google.oauth2 import service_account
from google.cloud import storage

# Load GCS credentials from Streamlit secrets or fallback to local key
try:
    gcs_conf = dict(st.secrets["connections"]["gcs"])
    gcs_conf["private_key"] = gcs_conf["private_key"].replace("\\n", "\n")
except Exception:
    with open("key.json") as f:
        gcs_conf = json.load(f)

GCS_BUCKET = gcs_conf.get("GCS_BUCKET", "card_annotation")

# Initialize Google Cloud Storage client
def get_gcs_client(conf):
    creds = service_account.Credentials.from_service_account_info(conf)
    return storage.Client(credentials=creds, project=conf.get("project_id"))

client = get_gcs_client(gcs_conf)
bucket = client.bucket(GCS_BUCKET)

# Page configuration
st.set_page_config(page_title="JSON Validator", layout="wide")

# Local lock directory
LOCK_DIR = 'data/locks'
os.makedirs(LOCK_DIR, exist_ok=True)

# Utility: clean raw JSON
def clean_json_text(raw: str) -> str:
    t = re.sub(r'(:\s*)-(\s*[,\}])', r'\1null\2', raw)
    t = re.sub(r'(:\s*)(0\d+)(\s*[,\}])', r'\1"\2"\3', t)
    return t

# List available JSONs not yet corrected and not locked
def list_jsons():
    try:
        # list raw JSON blobs
        raw_blobs = client.list_blobs(bucket, prefix="jsons/")
        raw_paths = [os.path.basename(b.name) for b in raw_blobs if b.name.endswith(".json")]

        # list corrected JSON blobs
        corr_blobs = client.list_blobs(bucket, prefix="corrected/")
        corr_files = {os.path.basename(b.name) for b in corr_blobs if b.name.endswith(".json")}

        avail = []
        for fname in sorted(raw_paths):
            if fname in corr_files:
                continue
            lock_file = os.path.join(LOCK_DIR, fname + '.lock')
            if os.path.exists(lock_file):
                continue
            avail.append(fname)
        return avail
    except Exception as e:
        st.error(f"Error listing JSON files: {e}")
        return []

# Select JSON file
if 'idx' not in st.session_state:
    st.session_state.idx = 0

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

# Load and clean JSON
try:
    blob = bucket.blob(f"jsons/{current}")
    raw = blob.download_as_text()
    data = json.loads(clean_json_text(raw))
except Exception as e:
    st.error(f'Error loading JSON: {e}')
    lock.release()
    os.remove(lock_path)
    st.stop()

# Sidebar: load and show image
with st.sidebar:
    st.header('Image Reference')
    img_base = data.get('image_filename') or os.path.splitext(current)[0]
    found = False
    for ext in ['.jpg', '.jpeg', '.png', '.tif']:
        path = f"images/{img_base}{ext}"
        blob = bucket.blob(path)
        if blob.exists():
            img_bytes = blob.download_as_bytes()
            st.image(img_bytes, caption=f'{img_base}{ext}', use_container_width=True)
            found = True
            break
    if not found:
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
            blob = bucket.blob(f"corrected/{current}")
            blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2), content_type='application/json')
            st.success('Saved corrected record to GCS.')
            lock.release()
            os.remove(lock_path)
            st.experimental_rerun()
        except Exception as e:
            st.error(f'Error saving corrected JSON: {e}')
            lock.release()
            os.remove(lock_path)
