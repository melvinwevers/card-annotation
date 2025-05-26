import os
import streamlit as st
import portalocker
from typing import Any

from config import PAGE_CONFIG, LOCK_DIR, apply_custom_css
from file_ops import load_json_from_gcs, save_corrected_json, list_available_jsons
from gcs_utils import get_gcs_file_lists
from ui_components import (
    render_navigation,
    render_image_sidebar,
    render_edit_form,
)

st.set_page_config(**PAGE_CONFIG)


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
            lock = portalocker.Lock(lock_path, "w", timeout=0)
            lock.acquire()
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
        release_lock()
        st.stop()

    render_image_sidebar(data)

    validated = data.get("validated_json") or {}
    if not validated:
        st.warning("No validated_json section to edit.")
        release_lock()
        st.stop()

    updated = render_edit_form(validated)

    # ─── Save & Finalise ───────────────────────────────────────────────
    if updated is not None:
        if st.session_state.validation_errors:
            st.error("⚠️ Please fix validation errors before saving.")
        else:
            # proceed to save and finalize
            data["validated_json"] = updated
        try:
            save_corrected_json(current, data)
            st.success("✅ Record finalised and moved to corrected/")

            st.session_state.finalized_files.add(current)
            
            # clear file list cache so the finalized file disappears
            get_gcs_file_lists.clear()
            st.session_state.validation_errors.clear()

            # release lock
            release_lock()

            remaining = list_available_jsons()
            if remaining:
                try:
                    st.session_state.idx = min(st.session_state.idx + 1, len(remaining) - 1)
                    st.session_state.just_navigated = True
                except:
                    st.session_state.idx = 0
                st.session_state.pop("current_file", None)
                st.rerun()
            else:
                st.success("🎉 All records validated — great job!")
                st.stop()
        except Exception as e:
            st.error(f"Error saving corrected JSON: {e}")
            release_lock()
            st.stop()


if __name__ == "__main__":
    main()
