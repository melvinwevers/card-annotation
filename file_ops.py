import os
import json
import streamlit as st
from gcs_utils import get_bucket, get_gcs_file_lists
from config import LOCK_DIR, IMAGE_EXTENSIONS, CACHE_TTL_SHORT, CACHE_TTL_MEDIUM


def list_available_jsons() -> list[str]:
    raw, corr = get_gcs_file_lists()
    available = []
    for f in sorted(raw):
        # skip anything that is currently locked
        if os.path.exists(os.path.join(LOCK_DIR, f + ".lock")):
            continue
        # skip anything that has been corrected
        if f in corr:
            continue
        available.append(f)
    return available


def is_file_corrected(filename: str) -> bool:
    """Check if a file has been corrected (exists in corrected folder)"""
    try:
        _, corr = get_gcs_file_lists()
        return filename in corr
    except Exception:
        return False


def get_file_status(filename: str) -> str:
    """Get the status of a file (uncorrected, corrected, or locked)"""
    if os.path.exists(os.path.join(LOCK_DIR, filename + ".lock")):
        return "locked"
    elif is_file_corrected(filename):
        return "corrected"
    else:
        return "uncorrected"


@st.cache_data(ttl=CACHE_TTL_SHORT)  # 5 min - frequently accessed/updated
def load_json_from_gcs(filename: str):
    try:
        bucket = get_bucket()
        raw = bucket.blob(f"jsons/{filename}").download_as_text()
        from utils import clean_json_text
        data = json.loads(clean_json_text(raw))
        return data, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=CACHE_TTL_MEDIUM)  # 10 min - images rarely change
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


def load_corrected_json(filename: str):
    """Load corrected version of a file from GCS"""
    try:
        bucket = get_bucket()
        blob = bucket.blob(f"corrected/{filename}")
        if blob.exists():
            raw = blob.download_as_text()
            from utils import clean_json_text
            return json.loads(clean_json_text(raw))
        return None
    except Exception as e:
        st.error(f"Error loading corrected JSON {filename}: {e}")
        return None


def compare_json_versions(filename: str):
    """Compare original and corrected versions of a file"""
    original, _ = load_json_from_gcs(filename)
    corrected = load_corrected_json(filename)

    if not original or not corrected:
        return None

    return {
        'filename': filename,
        'original': original,
        'corrected': corrected,
        'has_changes': original != corrected
    }
