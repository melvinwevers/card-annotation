import os
import json
import streamlit as st
from google.oauth2 import service_account
from google.cloud import storage
from typing import Dict, List, Any, Optional, Union, Tuple


@st.cache_data(ttl=3600)
def load_gcs_config() -> dict:
    try:
        conf = dict(st.secrets["connections"]["gcs"])
        conf["private_key"] = conf["private_key"].replace("\\n", "\n")
    except Exception:
        try:
            with open("key.json") as f:
                conf = json.load(f)
        except Exception as e:
            st.error(f"Failed to load GCS credentials: {e}")
            return {}
    return conf

@st.cache_resource
def get_gcs_client() -> storage.Client:
    conf = load_gcs_config()
    if not conf:
        raise ValueError("No GCS credentials available")
    
    try:
        creds = service_account.Credentials.from_service_account_info(conf)
        return storage.Client(credentials=creds, project=conf.get("project_id"))
    except Exception as e:
        st.error(f"Failed to initialize GCS client: {e}")
        raise

def get_bucket() -> storage.Bucket:
    client = get_gcs_client()
    conf = load_gcs_config()
    name = conf.get("GCS_BUCKET", "card_annotation")
    return client.bucket(name)

@st.cache_data(ttl=60)
def get_gcs_file_lists() -> Tuple[List[str], set]:
    """Get lists of raw and corrected files from GCS"""
    try:
        client = get_gcs_client()
        bucket = get_bucket()
        
        # Get raw JSON files
        raw_blobs = list(client.list_blobs(bucket, prefix="jsons/"))
        raw_paths = [os.path.basename(b.name) for b in raw_blobs if b.name.endswith(".json")]
        
        # Get corrected files
        corr_blobs = list(client.list_blobs(bucket, prefix="corrected/"))
        corr_files = {os.path.basename(b.name) for b in corr_blobs if b.name.endswith(".json")}
        
        return raw_paths, corr_files
    except Exception as e:
        st.error(f"Error listing JSON files: {e}")
        return [], set()