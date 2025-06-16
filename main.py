import os
import json
import getpass
import streamlit as st
import portalocker
from typing import Any
from datetime import datetime

from config import PAGE_CONFIG, LOCK_DIR, apply_custom_css
from file_ops import load_json_from_gcs, save_corrected_json, list_available_jsons
from gcs_utils import get_gcs_file_lists
from ui_components import (
    render_navigation,
    render_image_sidebar,
    render_edit_form,
)

st.set_page_config(**PAGE_CONFIG)


def create_lock_with_user_info(lock_path: str, filename: str, user: str = None) -> portalocker.Lock:
    """Create a lock file with user information"""
    if user is None:
        user = st.session_state.get("username", getpass.getuser())
    
    lock_data = {
        "user": user,
        "filename": filename,
        "locked_at": datetime.now().isoformat(),
        "session_id": st.session_state.get("session_id", "unknown")
    }
    
    # Create the lock file with user info
    lock = portalocker.Lock(lock_path, "w", timeout=0)
    lock.acquire()
    
    # Write user info to the lock file
    with open(lock_path, 'w') as f:
        json.dump(lock_data, f, indent=2)
    
    return lock


def release_lock():
    """Release lock file on shutdown or rerun."""
    lock = st.session_state.get("lock")
    locked_file = st.session_state.get("locked_file")
    if lock and locked_file:
        try:
            lock.release()
            os.remove(os.path.join(LOCK_DIR, locked_file + ".lock"))
        except Exception:
            pass
        st.session_state.pop("lock", None)
        st.session_state.pop("locked_file", None)


# Register shutdown cleanup if supported (Streamlit >= 1.28)
if hasattr(st, "on_event"):
    st.on_event("shutdown", release_lock)


def main() -> None:
    apply_custom_css()
    os.makedirs(LOCK_DIR, exist_ok=True)
    
    # Initialize session ID for user tracking
    if "session_id" not in st.session_state:
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + getpass.getuser()

    # ─── Page Navigation ─────────────────────────────────────────────────
    # Initialize page state
    if "page" not in st.session_state:
        st.session_state.page = "dashboard"
    
    # Compact navigation in sidebar
    with st.sidebar:
        # Username in a single line with change button
        if "username" not in st.session_state:
            username = st.text_input("👤 Username", value=getpass.getuser(), label_visibility="collapsed")
            if username:
                st.session_state.username = username
                st.rerun()
        else:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"👤 **{st.session_state.username}**")
            with col2:
                if st.button("Change", use_container_width=True):
                    st.session_state.pop("username")
                    st.rerun()
        
        # Navigation buttons in a single row
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Dashboard", use_container_width=True, 
                        type="primary" if st.session_state.page == "dashboard" else "secondary"):
                st.session_state.page = "dashboard"
                st.rerun()
        with col2:
            if st.button("📝 Editor", use_container_width=True,
                        type="primary" if st.session_state.page == "editor" else "secondary"):
                st.session_state.page = "editor"
                st.rerun()
        
        st.markdown("---")
    
    # Route to appropriate page
    if st.session_state.page == "dashboard":
        from dashboard import render_dashboard
        render_dashboard()
        return
    
    # Continue with editor logic (existing functionality)
    
    # ─── Defensive lock cleanup ─────────────────────────────────────────
    locked_file = st.session_state.get("locked_file")
    if locked_file and not os.path.exists(os.path.join(LOCK_DIR, locked_file + ".lock")):
        st.session_state.pop("locked_file", None)
        st.session_state.pop("lock", None)

    # ─── Initialise session state ──────────────────────────────────────
    st.session_state.setdefault("idx", 0)
    st.session_state.setdefault("validation_errors", {})
    st.session_state.setdefault("finalized_files", set())

    # ─── Navigation (release old lock first if changed) ────────────────
    prev_locked: str | None = st.session_state.get("locked_file")
    prev_lock_obj: Any | None = st.session_state.get("lock")

    current = render_navigation()
    st.session_state.current_file = current

    if prev_locked and prev_locked != current:
        try:
            if prev_lock_obj:
                prev_lock_obj.release()
            os.remove(os.path.join(LOCK_DIR, prev_locked + ".lock"))
        except Exception:
            pass
        st.session_state.pop("lock", None)
        st.session_state.pop("locked_file", None)

    # ─── Acquire lock for current file ─────────────────────────────────
    lock_path = os.path.join(LOCK_DIR, current + ".lock")
    if "lock" not in st.session_state or st.session_state.get("locked_file") != current:
        try:
            lock = create_lock_with_user_info(lock_path, current)
            st.session_state["lock"] = lock
            st.session_state["locked_file"] = current
        except portalocker.exceptions.LockException:
            st.warning("⚠️ This record is being edited by someone else.")
            st.stop()
    else:
        lock = st.session_state["lock"]

    # ─── Load JSON and show UI ─────────────────────────────────────────
    data, error = load_json_from_gcs(current)
    if error:
        st.error(f"Error loading JSON: {error}")
        st.stop()

    # ─── Main layout ──────────────────────────────────────────────────
    # Image in sidebar
    render_image_sidebar(data)
    
    # Main content area
    validated = data.get("validated_json") or {}
    if not validated:
        st.info(f"⏭️ Skipping '{current}' - No validated_json section to edit.")
        release_lock()
        
        # Auto-skip to next available record
        remaining = list_available_jsons()
        if remaining:
            try:
                # Find current position and move to next
                current_idx = remaining.index(current) if current in remaining else st.session_state.idx
                st.session_state.idx = min(current_idx + 1, len(remaining) - 1)
                st.session_state.just_navigated = True
            except:
                st.session_state.idx = min(st.session_state.idx + 1, len(remaining) - 1) if remaining else 0
            st.session_state.pop("current_file", None)
            st.rerun()
        else:
            st.success("🎉 All processable records completed!")
            st.stop()

    updated = render_edit_form(validated)

    # ─── Save & Finalise ───────────────────────────────────────────────
    if updated:
        save_corrected_json(data, updated)
        st.success("✅ Changes saved!")
        st.rerun()


if __name__ == "__main__":
    main()
