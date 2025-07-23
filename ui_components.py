import os
import base64
import streamlit.components.v1 as components
from typing import Any, Dict, List, Optional

import streamlit as st
import portalocker  # lock reference still needed elsewhere

from config import LOCK_DIR
from schemas import FIELD_SCHEMAS, FieldType, PRIORITY_FIELDS
from utils import type_convert, validate_field
from file_ops import (
    list_available_jsons,
    load_json_from_gcs,
    load_image_from_gcs,
    get_file_status,
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
    # Include current file name in the key to prevent cross-record value persistence
    current_file = st.session_state.get("current_file", "unknown")
    field_key = f"{current_file}.{section}.{key}"
    #field_key = key

    # Use description as label if available, otherwise use the key
    base_label = schema.get("description", key) if schema else key
    
    # Add priority indicator for priority fields
    is_priority = key in PRIORITY_FIELDS.get(section, [])
    show_priority_marker = schema.get('priority_marker', False) if schema else False
    
    if is_priority and show_priority_marker:
        label = f"⭐ {base_label}"
    elif is_priority:
        label = f"🎯 {base_label}"
    else:
        label = base_label

    inp = col.text_input(
        label,
        value=str(value),
        key=field_key,
        placeholder=schema.get("placeholder", "") if schema else None,
    )

    # Live value - regardless of original type
    val_now = st.session_state.get(field_key, inp)

    # Placeholder for an eventual error message
    error_container = col.empty()

    if schema:
        valid, err = validate_field(val_now, schema, key, section)
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
        # Insert in correct alphabetical position to maintain ordering
        files_copy = files[:]
        files_copy.append(current)
        files = sorted(files_copy)
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

    # Only realign idx if we haven't just navigated (to prevent jumping back)
    current_locked = st.session_state.get("current_file")
    just_navigated = st.session_state.get("just_navigated", False)
    if current_locked and current_locked in files and not just_navigated:
        st.session_state.idx = files.index(current_locked)
    elif just_navigated:
        # Clear the navigation flag after handling it
        st.session_state.pop("just_navigated", None)

    # ─── Enhanced navigation buttons ───────────────────────────────────────
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        prev_disabled = st.session_state.idx == 0
        if st.button(
            "⬅️ Previous", 
            key="prev_button", 
            use_container_width=True,
            disabled=prev_disabled,
            help="Go to previous record (Ctrl+←)"
        ) and not prev_disabled:
            st.session_state.idx -= 1
            st.session_state.validation_errors.clear()
    
    with col_info:
        # Enhanced progress indicator with statistics
        progress = (st.session_state.idx + 1) / len(files)
        completed_files = st.session_state.get("finalized_files", set())
        completion_rate = len(completed_files) / max(1, len(files))
        
        st.progress(progress, text=f"Record {st.session_state.idx + 1} of {len(files)}")
        
        # Show completion statistics
        if completed_files:
            st.caption(f"✅ {len(completed_files)} completed ({completion_rate:.0%} done)")
        else:
            st.caption("📊 Session starting...")
    
    with col_next:
        next_disabled = st.session_state.idx >= len(files) - 1
        if st.button(
            "Next ➡️", 
            key="next_button", 
            use_container_width=True,
            disabled=next_disabled,
            help="Go to next record (Ctrl+→)"
        ) and not next_disabled:
            st.session_state.idx += 1
            st.session_state.validation_errors.clear()

    current = files[st.session_state.idx]
    st.session_state.current_file = current  # keep in sync for the next run

    # Show file status
    status = get_file_status(current)
    status_emoji = {"uncorrected": "📝", "corrected": "✅", "locked": "🔒"}
    status_color = {"uncorrected": "", "corrected": ":green", "locked": ":orange"}
    
    st.title(f"Record {st.session_state.idx + 1}/{len(files)}: {current}")
    st.markdown(f"{status_emoji.get(status, '')} **Status**: {status_color.get(status, '')}{status.title()}")
    
    if status == "corrected":
        st.info("ℹ️ This file has been corrected but can be re-edited if needed")
    
    return current


def render_image_sidebar(data: Dict) -> None:
    with st.sidebar:
        st.header("📸 Image Reference")
        img_base = data.get("image_filename") or os.path.splitext(
            st.session_state.current_file
        )[0]
        img_bytes, img_name = load_image_from_gcs(img_base)
        if img_bytes:
            # Add zoom controls with more options
            zoom_level = st.select_slider(
                "🔍 Zoom Level", 
                options=["50%", "75%", "100%", "125%", "150%", "200%", "250%"],
                value="100%",
                key="image_zoom",
                help="Adjust image size for better viewing"
            )
            
            # Display image with zoom - use container width for consistent sizing
            zoom_factor = int(zoom_level.rstrip("%")) / 100
            
            # Create a container with specific styling for image zoom
            if zoom_factor != 1.0:
                st.markdown(f"""
                <div style="
                    overflow: auto; 
                    max-height: 600px; 
                    border: 1px solid var(--border-color, #ddd); 
                    border-radius: 8px;
                    padding: 10px;
                    background: var(--background-color, white);
                    box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
                ">
                """, unsafe_allow_html=True)
                
                st.image(
                    img_bytes, 
                    caption=f"📄 {img_name} ({zoom_level})", 
                    use_container_width=False,
                    width=int(480 * zoom_factor)  # Fixed base width for sidebar
                )
                
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.image(
                    img_bytes, 
                    caption=f"📄 {img_name}", 
                    use_container_width=True
                )
            
            # Image info
            st.caption(f"File: {img_name}")
            
            # Quick image actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Refresh", help="Reload image", use_container_width=True):
                    st.cache_data.clear()
                    st.rerun()
            with col2:
                # Download button would go here if needed
                st.button("🔍 Enhance", help="Coming soon", disabled=True, use_container_width=True)
        else:
            st.error(f"📷 Image not found for {img_base}")
            st.info("Check if the image file exists in the GCS bucket")


# ──────────────────────────────────────────────────────────────────────────────
# Main edit form
# ──────────────────────────────────────────────────────────────────────────────

def _clear_form_state():
    """Clear form state when navigating to a new record to prevent value persistence"""
    current_file = st.session_state.get("current_file", "unknown")
    if current_file:
        # Clear any session state keys that start with the current file name
        keys_to_remove = []
        for key in st.session_state.keys():
            if isinstance(key, str) and key.startswith(f"{current_file}."):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            st.session_state.pop(key, None)


def render_edit_form(validated_data: Dict) -> Optional[Dict]:
    """Render the editable form and return a corrected payload only when the
    user presses **Save corrections** *and* no validation errors remain. On
    validation failure the function returns None and the user stays on the same
    record."""

    # Clear any stale errors from previous record / rerun
    st.session_state.validation_errors.clear()
    
    # Clear form state when navigating to a new record
    if st.session_state.get("just_navigated", False):
        _clear_form_state()

    # Enhanced header with stats and options
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        show_all_fields = st.checkbox("Show all fields", value=False, key="show_all_fields")
    
    with col2:
        # Toggleable keyboard shortcuts hint
        show_shortcuts = st.button("⌨️ Shortcuts", help="Toggle keyboard shortcuts help")
        
        # Toggle shortcuts visibility
        if show_shortcuts:
            if st.session_state.get("show_shortcuts_panel", False):
                st.session_state.show_shortcuts_panel = False
            else:
                st.session_state.show_shortcuts_panel = True
    
    with col3:
        # Quick validation status with more detail
        if st.session_state.validation_errors:
            error_count = len(st.session_state.validation_errors)
            st.error(f"❌ {error_count} error{'s' if error_count != 1 else ''}")
        else:
            st.success("✅ Valid")
    
    # Show shortcuts panel if toggled on
    if st.session_state.get("show_shortcuts_panel", False):
        st.info("""
        **⌨️ Keyboard Shortcuts:**
        - `Ctrl + S`: Save changes
        - `Ctrl + →`: Next record  
        - `Ctrl + ←`: Previous record
        - `Tab`: Move to next field
        """)
    
    # Better info styling with expandable tips
    info_col, tips_col = st.columns([3, 1])
    
    with info_col:
        if not show_all_fields:
            st.info("🎯 **Priority Fields Only**: Showing only the most important fields - focus on **Main Entries** (person name, registration/departure dates, year of birth) and basic header info. Toggle above to see all fields.")
        else:
            st.info("📋 **All Fields**: Showing all available fields. Priority fields are marked with ⭐")
    
    with tips_col:
        with st.expander("💡 Annotation Tips"):
            st.markdown("""
            **Quick Tips:**
            - Use `Tab` to move between fields
            - Mark unclear fields for review
            - Date format: DDMMYY (e.g., 160636)
            - Names: Last, First (e.g., Keijzer, Tonko)
            - Leave empty if illegible
            """)
            
            # Quick reference for common patterns
            st.markdown("""
            **Common Patterns:**
            - House numbers: 18, 18a, 18 II, 18 huis
            - Dates: 6 digits DDMMYY
            - Years: 2 digits YY (94 = 1894)
            """)
    
    with st.form("edit_form", clear_on_submit=False):
        updated: Dict = {}

        # ─── Dynamic field generation ────────────────────────────────────
        for section, content in validated_data.items():
            # Better section headers with visual separators and counts
            section_title = section.replace("_", " ").title()
            priority_fields = PRIORITY_FIELDS.get(section, [])
            
            # Count fields to show
            if isinstance(content, dict):
                total_fields = len([k for k in content.keys() if not k.endswith("_needs review")])
                priority_count = len([k for k in content.keys() if k in priority_fields])
            elif isinstance(content, list):
                total_fields = len(content) if content else 0
                priority_count = total_fields  # For lists, all entries are considered
            else:
                total_fields = 1
                priority_count = 1
            
            # Show field count info and person name for main entries
            if show_all_fields:
                field_info = f"({priority_count} priority, {total_fields} total)"
            else:
                field_info = f"({priority_count} priority fields)"
            
            # Add person name to main entries header
            header_text = f"### 📋 {section_title} {field_info}"
            if section == "main_entries" and isinstance(content, list) and content:
                # Try to get the name from the first entry
                first_entry = content[0]
                person_name = first_entry.get('gezinshoofd', '').strip()
                if person_name:
                    # Extract just the name part (before comma if present)
                    display_name = person_name.split(',')[0].strip() if ',' in person_name else person_name
                    header_text = f"### 👤 {section_title}: **{display_name}** {field_info}"
            
            st.markdown(header_text)
            st.markdown("---")
            
            section_schema = FIELD_SCHEMAS.get(section, {})

            # Dict‑like subsection
            if isinstance(content, dict):
                updated[section] = {}
                
                # Separate priority and non-priority fields
                priority_fields = PRIORITY_FIELDS.get(section, [])
                priority_items = []
                other_items = []
                
                for key, orig in content.items():
                    if key.endswith("_needs review"):
                        continue
                    if key in priority_fields:
                        priority_items.append((key, orig))
                    else:
                        other_items.append((key, orig))
                
                # Render priority fields first with better layout
                for key, orig in priority_items:
                    # Use container for better spacing
                    with st.container():
                        cols = st.columns((3, 1, 0.2))  # Added small space column
                        current_file = st.session_state.get("current_file", "unknown")
                        
                        # Add star for priority fields when showing all fields
                        field_schema = section_schema.get(key, {})
                        if show_all_fields:
                            field_schema = field_schema.copy() if field_schema else {}
                            field_schema['priority_marker'] = True
                        
                        needs_review = cols[1].checkbox(
                            "🔍 Review",
                            key=f"{current_file}.{section}.{key}_needs review",
                            value=content.get(f"{key}_needs review", False),
                            help="Mark this field if it needs manual review"
                        )
                        
                        val = create_field_input(
                            section, key, orig, cols[0], field_schema, unsure=needs_review
                        )
                        updated[section][key] = val
                        updated[section][f"{key}_needs review"] = needs_review
                        
                        # Add small vertical space
                        st.write("")
                
                # Render non-priority fields only if showing all fields
                if show_all_fields and other_items:
                    st.markdown("**📄 Additional Fields**")
                    for key, orig in other_items:
                        with st.container():
                            cols = st.columns((3, 1, 0.2))
                            current_file = st.session_state.get("current_file", "unknown")
                            needs_review = cols[1].checkbox(
                                "🔍 Review",
                                key=f"{current_file}.{section}.{key}_needs review",
                                value=content.get(f"{key}_needs review", False),
                                help="Mark this field if it needs manual review"
                            )
                            val = create_field_input(
                                section, key, orig, cols[0], section_schema.get(key), unsure=needs_review
                            )
                            updated[section][key] = val
                            updated[section][f"{key}_needs review"] = needs_review
                            st.write("")
                else:
                    # Still include non-priority fields in updated dict with original values
                    for key, orig in other_items:
                        updated[section][key] = orig
                        updated[section][f"{key}_needs review"] = content.get(f"{key}_needs review", False)

            # List‑like subsection
            elif isinstance(content, list):
                updated[section] = []
                for idx, entry in enumerate(content, start=1):
                    # Better entry headers with person names
                    entry_title = f"📝 {section.title().rstrip('s')} #{idx}"
                    
                    # Add person name to entry title if available
                    if section == "main_entries":
                        person_name = entry.get('gezinshoofd', '').strip()
                        if person_name:
                            # Show full name in entry header
                            entry_title = f"👤 **Main Entry #{idx}: {person_name}**"
                    elif section == "follow_up_entries":
                        person_name = entry.get('inwonenden', '').strip()
                        if person_name:
                            entry_title = f"👥 **Follow-up #{idx}: {person_name}**"
                    
                    with st.expander(entry_title, expanded=True):
                        temp: Dict = {}
                        
                        # Separate priority and non-priority fields
                        priority_fields = PRIORITY_FIELDS.get(section, [])
                        priority_items = []
                        other_items = []
                        
                        for key, orig in entry.items():
                            if key.endswith("_needs review"):
                                continue
                            if key in priority_fields:
                                priority_items.append((key, orig))
                            else:
                                other_items.append((key, orig))
                        
                        # Render priority fields first
                        for key, orig in priority_items:
                            with st.container():
                                cols = st.columns((3, 1, 0.2))
                                current_file = st.session_state.get("current_file", "unknown")
                                
                                # Add star for priority fields when showing all fields
                                field_schema = section_schema.get(key, {})
                                if show_all_fields:
                                    field_schema = field_schema.copy() if field_schema else {}
                                    field_schema['priority_marker'] = True
                                
                                needs_review = cols[1].checkbox(
                                    "🔍 Review",
                                    key=f"{current_file}.{section}[{idx}].{key}_needs review",
                                    value=entry.get(f"{key}_needs review", False),
                                    help="Mark this field if it needs manual review"
                                )
                                
                                val = create_field_input(
                                    f"{section}[{idx}]",
                                    key,
                                    orig,
                                    cols[0],
                                    field_schema,
                                    unsure=needs_review
                                )
                                temp[key] = val
                                temp[f"{key}_needs review"] = needs_review
                                st.write("")
                        
                        # Render non-priority fields only if showing all fields
                        if show_all_fields and other_items:
                            st.markdown("**📄 Additional Fields**")
                            for key, orig in other_items:
                                with st.container():
                                    cols = st.columns((3, 1, 0.2))
                                    current_file = st.session_state.get("current_file", "unknown")
                                    needs_review = cols[1].checkbox(
                                        "🔍 Review",
                                        key=f"{current_file}.{section}[{idx}].{key}_needs review",
                                        value=entry.get(f"{key}_needs review", False),
                                        help="Mark this field if it needs manual review"
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
                                    st.write("")
                        else:
                            # Still include non-priority fields with original values
                            for key, orig in other_items:
                                temp[key] = orig
                                temp[f"{key}_needs review"] = entry.get(f"{key}_needs review", False)
                    
                    updated[section].append(temp)

            # Scalar subsection
            else:
                cols = st.columns((3, 1))
                current_file = st.session_state.get("current_file", "unknown")
                needs_review = cols[1].checkbox("needs review", key=f"{current_file}.{section}_needs review")
                inp = cols[0].text_input(section, value=str(content), key=f"{current_file}.{section}")
                updated[section] = type_convert(inp, content)
                updated[f"{section}_needs review"] = needs_review

        # ─── Check if any fields are under review ─────────────────────────
        has_fields_under_review = _check_if_has_fields_under_review(updated)

        # ─── Validation summary & save button ────────────────────────────
        col1, col2 = st.columns([3, 1])
        
        with col1:
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
            elif has_fields_under_review:
                st.info("🔍 Some fields marked for review - data will be saved with review flags")
            else:
                st.success("✅ All fields validated - ready to save!")

        with col2:
            # Improved save button with keyboard hint
            save_clicked = st.form_submit_button(
                "💾 Save & Next",
                use_container_width=True,
                help="Save changes and move to next record (Ctrl+S)",
                type="primary"
            )
            
        # Quick data summary for review
        if show_all_fields or st.session_state.validation_errors:
            with st.expander("📊 Data Summary", expanded=len(st.session_state.validation_errors) > 0):
                summary_col1, summary_col2 = st.columns(2)
                
                with summary_col1:
                    # Show key data points
                    st.markdown("**Key Information:**")
                    for section, content in updated.items():
                        if section in ['header', 'main_entries'] and isinstance(content, dict):
                            for key, value in content.items():
                                if key in PRIORITY_FIELDS.get(section, []) and value and not key.endswith('_needs review'):
                                    st.text(f"• {key.replace('_', ' ').title()}: {value}")
                        elif section == 'main_entries' and isinstance(content, list):
                            for idx, entry in enumerate(content, 1):
                                name = entry.get('gezinshoofd', '')
                                if name:
                                    st.text(f"• Person #{idx}: {name}")
                
                with summary_col2:
                    # Show review flags and errors
                    review_count = sum(1 for section in updated.values() 
                                     for key, value in (section.items() if isinstance(section, dict) else [])
                                     if key.endswith('_needs review') and value)
                    
                    if review_count > 0:
                        st.markdown(f"**🔍 Fields for Review:** {review_count}")
                    
                    if st.session_state.validation_errors:
                        st.markdown("**❌ Validation Errors:**")
                        for error in list(st.session_state.validation_errors.values())[:3]:  # Show first 3
                            st.text(f"• {error}")
                        if len(st.session_state.validation_errors) > 3:
                            st.text(f"• ... and {len(st.session_state.validation_errors) - 3} more")

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
