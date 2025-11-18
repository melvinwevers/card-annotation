import os
import json
import getpass
import streamlit as st
import portalocker
from typing import Any
from datetime import datetime

from config import PAGE_CONFIG, LOCK_DIR, apply_custom_css
from file_ops import load_json_from_gcs, save_corrected_json, list_available_jsons
from utils import clean_none_values
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
        "session_id": st.session_state.get("session_id", "unknown"),
        "pid": os.getpid()  # Add process ID for stale lock detection
    }
    
    # Create and acquire the lock first
    lock = portalocker.Lock(lock_path, "w", timeout=0)
    try:
        lock.acquire()
        
        # Write user info to the lock file using the file handle
        with open(lock_path, 'w') as f:
            json.dump(lock_data, f, indent=2)
        
        return lock
    except Exception as e:
        # If anything fails, clean up
        try:
            lock.release()
        except:
            pass
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except:
                pass
        raise e


def release_lock():
    """Release lock file on shutdown or rerun."""
    lock = st.session_state.get("lock")
    locked_file = st.session_state.get("locked_file")
    if lock and locked_file:
        lock_path = os.path.join(LOCK_DIR, locked_file + ".lock")
        
        # Try to release the lock object first
        lock_released = False
        try:
            lock.release()
            lock_released = True
        except Exception as e:
            st.warning(f"Failed to release lock object: {e}")
        
        # Always try to remove the lock file, even if lock.release() failed
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception as e:
            st.error(f"Failed to remove lock file {lock_path}: {e}")
        
        # Always clear session state
        st.session_state.pop("lock", None)
        st.session_state.pop("locked_file", None)
        
        # Only show messages for problems, not routine operations
        if not lock_released:
            st.warning("⚠️ Lock file removed but lock object may not have been properly released")


def cleanup_stale_locks():
    """Clean up stale locks from crashed or timed-out sessions"""
    if not os.path.exists(LOCK_DIR):
        return []
    
    stale_locks = []
    current_time = datetime.now()
    
    for lock_file in os.listdir(LOCK_DIR):
        if not lock_file.endswith(".lock"):
            continue
            
        lock_path = os.path.join(LOCK_DIR, lock_file)
        try:
            # Try to read lock info
            with open(lock_path, 'r') as f:
                lock_data = json.load(f)
            
            # Check if lock is stale (older than 30 minutes)
            locked_at = datetime.fromisoformat(lock_data.get('locked_at', ''))
            if (current_time - locked_at).total_seconds() > 1800:  # 30 minutes
                os.remove(lock_path)
                stale_locks.append({
                    'file': lock_file.replace('.lock', ''),
                    'user': lock_data.get('user', 'unknown'),
                    'locked_at': locked_at
                })
                
        except Exception as e:
            # If we can't read the lock file, it's probably corrupted - remove it
            try:
                os.remove(lock_path)
                stale_locks.append({
                    'file': lock_file.replace('.lock', ''),
                    'user': 'unknown',
                    'locked_at': 'corrupted',
                    'error': str(e)
                })
            except:
                pass
    
    return stale_locks


# Register shutdown cleanup if supported (Streamlit >= 1.28)
if hasattr(st, "on_event"):
    st.on_event("shutdown", release_lock)


def main() -> None:
    apply_custom_css()
    os.makedirs(LOCK_DIR, exist_ok=True)
    
    # Clean up stale locks on startup
    try:
        stale_locks = cleanup_stale_locks()
        if stale_locks:
            st.info(f"🧹 Cleaned up {len(stale_locks)} stale lock(s)")
    except Exception as e:
        st.warning(f"Failed to cleanup stale locks: {e}")
    
    # Initialize session ID for user tracking
    if "session_id" not in st.session_state:
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + getpass.getuser()

    # ─── Page Navigation ─────────────────────────────────────────────────
    # Initialize page state
    if "page" not in st.session_state:
        st.session_state.page = "dashboard"
    
    # Compact navigation in sidebar
    with st.sidebar:
        # Username handling with proper state management
        if "username" not in st.session_state:
            st.session_state.username = getpass.getuser()
        
        # Username input/display with change functionality
        if st.session_state.get("changing_username", False):
            # Show input field for changing username
            new_username = st.text_input("👤 Enter new username", value=st.session_state.username, key="new_username_input")
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("✅ Save", use_container_width=True):
                    if new_username and new_username.strip():
                        st.session_state.username = new_username.strip()
                        st.session_state.changing_username = False
                        st.rerun()
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.changing_username = False
                    st.rerun()
        else:
            # Show current username with change button
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"👤 **{st.session_state.username}**")
            with col2:
                if st.button("Change", use_container_width=True):
                    st.session_state.changing_username = True
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
        # Release old lock more carefully
        old_lock_path = os.path.join(LOCK_DIR, prev_locked + ".lock")
        
        # Try to release lock object
        if prev_lock_obj:
            try:
                prev_lock_obj.release()
            except Exception as e:
                st.warning(f"Failed to release lock object for {prev_locked}: {e}")
        
        # Always try to remove lock file
        try:
            if os.path.exists(old_lock_path):
                os.remove(old_lock_path)
        except Exception as e:
            st.error(f"Failed to remove lock file for {prev_locked}: {e}")
        
        # Clear session state
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
            # Check if it's our own stale lock
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, 'r') as f:
                        lock_data = json.load(f)
                    current_session = st.session_state.get("session_id", "unknown")
                    lock_session = lock_data.get("session_id", "unknown")
                    
                    if lock_session == current_session:
                        # It's our own stale lock - remove it and retry
                        os.remove(lock_path)
                        lock = create_lock_with_user_info(lock_path, current)
                        st.session_state["lock"] = lock
                        st.session_state["locked_file"] = current
                        st.info(f"🔄 Recovered from stale lock for {current}")
                    else:
                        # Show who has the lock
                        st.warning(f"⚠️ This record is being edited by {lock_data.get('user', 'someone else')} since {lock_data.get('locked_at', 'unknown time')}")
                        st.stop()
                except Exception as e:
                    st.error(f"Failed to read lock information: {e}")
                    st.stop()
            else:
                st.warning("⚠️ This record is being edited by someone else.")
                st.stop()
        except Exception as e:
            st.error(f"Failed to acquire lock for {current}: {e}")
            st.stop()
    else:
        lock = st.session_state["lock"]
        
        # Verify we still have the lock
        if not os.path.exists(lock_path):
            st.warning("🔓 Lock file was removed externally - reacquiring lock")
            try:
                lock = create_lock_with_user_info(lock_path, current)
                st.session_state["lock"] = lock
                st.session_state["locked_file"] = current
            except Exception as e:
                st.error(f"Failed to reacquire lock: {e}")
                st.stop()

    # ─── Load JSON and show UI ─────────────────────────────────────────
    data, error = load_json_from_gcs(current)
    if error:
        st.error(f"Error loading JSON: {error}")
        st.stop()

    # ─── Main layout ──────────────────────────────────────────────────
    # Image in sidebar
    render_image_sidebar(data)
    
    # Main content area
    validated = data.get("validated_json") or data.get("extracted_json") or {}
    # Clean up "none" values that the model may have entered
    validated = clean_none_values(validated)
    if not validated:
        st.info(f"⏭️ Skipping '{current}' - No validated_json or extracted_json section to edit.")
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
        try:
            # Update the data with the corrected validated_json (standardize field name)
            data["validated_json"] = updated
            # Remove extracted_json if it exists to avoid confusion
            if "extracted_json" in data:
                del data["extracted_json"]
            save_corrected_json(current, data)
            st.success("✅ Changes saved!")
            
            # Clear cache to ensure file lists are updated
            get_gcs_file_lists.clear()
            
            # Add to finalized files and move to next record
            st.session_state.finalized_files.add(current)
            release_lock()
            
            # Auto-skip to next available record
            remaining = list_available_jsons()
            if remaining:
                # Clear current_file first to prevent it from being re-added to the list
                st.session_state.pop("current_file", None)
                
                # Find the next file alphabetically after the current one
                current_idx = -1
                for i, fname in enumerate(sorted(remaining)):
                    if fname > current:
                        current_idx = i
                        break
                
                # If no file found after current, go to first file
                if current_idx == -1:
                    current_idx = 0
                    
                st.session_state.idx = current_idx
                st.session_state.just_navigated = True
                st.rerun()
            else:
                st.success("🎉 All processable records completed!")
                st.stop()
                
        except Exception as e:
            st.error(f"❌ Error saving changes: {str(e)}")
            st.error("Please try again or contact support if the problem persists.")


if __name__ == "__main__":
    main()
