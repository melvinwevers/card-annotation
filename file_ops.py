import os
import json
import streamlit as st
import portalocker
from gcs_utils import get_gcs_client, get_bucket
from config import LOCK_DIR, IMAGE_EXTENSIONS

@st.cache_data(ttl=60)
def get_gcs_file_lists() -> tuple[list[str], set]:
    try:
        client = get_gcs_client()
        bucket = get_bucket()
        raw = [os.path.basename(b.name) for b in client.list_blobs(bucket, prefix="jsons/") if b.name.endswith(".json")]
        corr = {os.path.basename(b.name) for b in client.list_blobs(bucket, prefix="corrected/") if b.name.endswith(".json")}
        return raw, corr
    except Exception as e:
        st.error(f"Error listing JSON files: {e}")
        return [], set()


def list_available_jsons() -> list[str]:
    raw, corr = get_gcs_file_lists()
    available = []
    for f in sorted(raw):
        # skip anything that is already in the corrected folder
        if f in corr:
            continue
        # skip anything that is currently locked
        if os.path.exists(os.path.join(LOCK_DIR, f + ".lock")):
            continue
        available.append(f)
    return available


@st.cache_data(ttl=300)
def load_json_from_gcs(filename: str):
    try:
        bucket = get_bucket()
        raw = bucket.blob(f"jsons/{filename}").download_as_text()
        from utils import clean_json_text
        data = json.loads(clean_json_text(raw))
        return data, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=600)
def load_image_from_gcs(base: str):
    bucket = get_bucket()
    for ext in IMAGE_EXTENSIONS:
        blob = bucket.blob(f"images/{base}{ext}")
        if blob.exists():
            return blob.download_as_bytes(), f"{base}{ext}"
    return None, None


def save_corrected_json(filename: str, data: dict):
    try:
        bucket = get_bucket()
        blob = bucket.blob(f"corrected/{filename}")
        json_string = json.dumps(data, ensure_ascii=False, indent=2)
        blob.upload_from_string(json_string, content_type='application/json')
    except Exception as e:
        raise Exception(f"Failed to save corrected JSON to GCS: {str(e)}")
