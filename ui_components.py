import os
import base64
import streamlit.components.v1 as components
from typing import Any, Dict, List, Optional

import streamlit as st
import portalocker  # lock reference still needed elsewhere

from config import LOCK_DIR
from schemas import FIELD_SCHEMAS, FieldType
from utils import type_convert, validate_field
from file_ops import (
    list_available_jsons,
    load_json_from_gcs,
    load_image_from_gcs,
)

__all__ = [
    "create_field_input",
    "render_navigation",
    "render_image_sidebar",
    "render_edit_form",
]

# ──────────────────────────────────────────────────────────────────────────────
# Field‑level helpers
# ──────────────────────────────────────────────────────────────────────────────

def create_field_input(
    section: str,
    key: str,
    value: Any,
    col,
    schema: Optional[Dict] = None,
    unsure: bool = False,
) -> Any:
    """Render a single text input with inline validation and return the
    type‑converted value."""
    field_key = f"{section}.{key}"
    #field_key = key

    inp = col.text_input(
        field_key,
        value=str(value),
        key=field_key,
        placeholder=schema.get("placeholder", "") if schema else None,
        help=schema.get("description", "") if schema else None,
    )

    # Live value - regardless of original type
    val_now = st.session_state.get(field_key, inp)

    # Placeholder for an eventual error message
    error_container = col.empty()

    if schema:
        valid, err = validate_field(val_now, schema)
        if not valid:
            error_container.error(err)
            if not unsure:
                # only count as blocking if not marked "unsure"
                st.session_state.validation_errors[field_key] = err
            else:
                st.session_state.validation_errors.pop(field_key, None)
        else:
            # Remove any existing validation error and clear the container
            st.session_state.validation_errors.pop(field_key, None)
            error_container.empty()

    return type_convert(val_now, value)


# ──────────────────────────────────────────────────────────────────────────────
# Navigation + sidebar helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_current_record_visible(files: List[str]) -> List[str]:
    """Guarantee that the file currently being edited is present in *files*.

    This prevents the UI from "jumping" to a different record when the current
    JSON is locked by *this* session (and therefore filtered‑out by
    `list_available_jsons`)."""
    current = st.session_state.get("current_file")
    if current and current not in files:
        # Prepend so we keep ordering deterministic (doesn't matter much – we
        # immediately align the index below).
        files = [current] + files
    return files


def render_navigation() -> str:
    """Render Previous / Next buttons and return the *currently selected* file
    name. Ensures we never "lose" the record we're working on even while it's
    locked by the current user."""

    files = _ensure_current_record_visible(list_available_jsons())

    if not files:
        st.warning("No unprocessed records available.")
        st.stop()

    # Ensure idx exists and is within range
    if "idx" not in st.session_state or st.session_state.idx >= len(files):
        st.session_state.idx = 0

    # After inserting the current file, realign idx so it points at it
    current_locked = st.session_state.get("current_file")
    if current_locked and current_locked in files:
        st.session_state.idx = files.index(current_locked)

    # ─── Navigation buttons ────────────────────────────────────────────────
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("Previous", key="prev_button") and st.session_state.idx > 0:
            st.session_state.idx -= 1
            st.session_state.validation_errors.clear()
    with col_next:
        if (
            st.button("Next", key="next_button")
            and st.session_state.idx < len(files) - 1
        ):
            st.session_state.idx += 1
            st.session_state.validation_errors.clear()

    current = files[st.session_state.idx]
    st.session_state.current_file = current  # keep in sync for the next run

    st.title(f"Record {st.session_state.idx + 1}/{len(files)}: {current}")
    return current


def render_image_sidebar(data: Dict) -> None:
    with st.sidebar:
        st.header("Image Reference")
        img_base = data.get("image_filename") or os.path.splitext(
            st.session_state.current_file
        )[0]
        img_bytes, img_name = load_image_from_gcs(img_base)
        if img_bytes:
            st.image(img_bytes, caption=img_name, use_container_width=True)
        else:
            st.warning(f"Image not found for {img_base}")


# ──────────────────────────────────────────────────────────────────────────────
# Main edit form
# ──────────────────────────────────────────────────────────────────────────────

def render_edit_form(validated_data: Dict) -> Optional[Dict]:
    """Render the editable form and return a corrected payload only when the
    user presses **Save corrections** *and* no validation errors remain. On
    validation failure the function returns None and the user stays on the same
    record."""

    # Clear any stale errors from previous record / rerun
    st.session_state.validation_errors.clear()

    with st.form("edit_form", clear_on_submit=False):
        updated: Dict = {}

        # ─── Dynamic field generation ────────────────────────────────────
        for section, content in validated_data.items():
            st.subheader(section.replace("_", " ").title())
            section_schema = FIELD_SCHEMAS.get(section, {})

            # Dict‑like subsection
            if isinstance(content, dict):
                updated[section] = {}
                for key, orig in content.items():
                    if key.endswith("_needs review"):
                        continue
                    cols = st.columns((3, 1))
                    needs_review = cols[1].checkbox(
                        "needs review",
                        key=f"{section}.{key}_needs review",
                        value=content.get(f"{key}_needs review", False),
                    )
                    val = create_field_input(
                        section, key, orig, cols[0], section_schema.get(key), unsure=needs_review
                    )
                    updated[section][key] = val
                    updated[section][f"{key}_needs review"] = needs_review

            # List‑like subsection
            elif isinstance(content, list):
                updated[section] = []
                for idx, entry in enumerate(content, start=1):
                    st.markdown(f"**{section.title()} #{idx}**")
                    temp: Dict = {}
                    for key, orig in entry.items():
                        if key.endswith("_needs review"):
                            continue
                        cols = st.columns((3, 1))
                        needs_review = cols[1].checkbox(
                            "needs review",
                            key=f"{section}[{idx}].{key}_needs review",
                            value=entry.get(f"{key}_needs review", False),
                        )
                        val = create_field_input(
                            f"{section}[{idx}]",
                            key,
                            orig,
                            cols[0],
                            section_schema.get(key),
                            unsure=needs_review
                        )
                        temp[key] = val
                        temp[f"{key}_needs review"] = needs_review
                    updated[section].append(temp)

            # Scalar subsection
            else:
                cols = st.columns((3, 1))
                needs_review = cols[1].checkbox("needs review", key=f"{section}_needs review")
                inp = cols[0].text_input(section, value=str(content), key=section)
                updated[section] = type_convert(inp, content)
                updated[f"{section}_needs review"] = needs_review

        # ─── Check if any fields are under review ─────────────────────────
        has_fields_under_review = _check_if_has_fields_under_review(updated)

        # ─── Validation summary & save button ────────────────────────────
        if st.session_state.validation_errors:
            if has_fields_under_review:
                st.warning(
                    f"⚠️ {len(st.session_state.validation_errors)} validation error"
                    f"{'s' if len(st.session_state.validation_errors) != 1 else ''} found, "
                    "but allowing save because some fields are marked for review."
                )
            else:
                st.error(
                    f"⚠️ {len(st.session_state.validation_errors)} validation error"
                    f"{'s' if len(st.session_state.validation_errors) != 1 else ''} – "
                    "please fix before saving or mark fields as 'needs review'."
                )

        # Single submit button – clicking triggers a form rerun
        save_clicked = st.form_submit_button("💾 Save corrections")

    # After the *with* block so we can safely return a value or abort
    if save_clicked:
        # Allow saving if no validation errors OR if there are fields under review
        if st.session_state.validation_errors and not has_fields_under_review:
            # Validation failed and no fields marked for review → stay on the same record
            return None
        # All clear OR has fields under review → return finalised payload
        return updated
    
    # Scroll to top and focus first input only after navigating
    if st.session_state.get("just_navigated", False):
        st.markdown("""
            <script>
            window.onload = function() {
                window.scrollTo(0, 0);
                const firstInput = document.querySelector('input[type="text"], textarea, select');
                if (firstInput) {
                    firstInput.focus();
                }
            }
            </script>
        """, unsafe_allow_html=True)
        st.session_state.just_navigated = False

    # Nothing to persist this turn
    return None


def _check_if_has_fields_under_review(updated_data: Dict) -> bool:
    """Check if any fields in the updated data are marked as needing review"""
    for section_key, section_value in updated_data.items():
        if section_key.endswith("_needs review") and section_value:
            return True
        
        if isinstance(section_value, dict):
            for key, value in section_value.items():
                if key.endswith("_needs review") and value:
                    return True
        
        elif isinstance(section_value, list):
            for entry in section_value:
                if isinstance(entry, dict):
                    for key, value in entry.items():
                        if key.endswith("_needs review") and value:
                            return True
    
    return False
