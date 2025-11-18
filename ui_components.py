import base64
import os
from typing import Any, Dict, List, Optional

import portalocker  # lock reference still needed elsewhere
import streamlit as st
import streamlit.components.v1 as components

from config import LOCK_DIR
from file_ops import (
    get_file_status,
    list_available_jsons,
    load_image_from_gcs,
    load_json_from_gcs,
)
from schemas import FIELD_SCHEMAS, FieldType
from utils import type_convert, validate_field, validate_entry_dates


def format_filename_for_display(filename: str) -> str:
    """
    Format filename for display by removing leading zeros from numeric parts.

    Example: WKAPL00197000001.json -> WKAPL197000001.json
    """
    import re

    def remove_leading_zeros(match):
        num = match.group(0)
        # Keep at least one digit (handle edge case of all zeros)
        return num.lstrip("0") or "0"

    # Process each numeric sequence independently
    formatted = re.sub(r"\d+", remove_leading_zeros, filename)
    return formatted


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
) -> Any:
    """Render a single text input with inline validation and return the
    type‑converted value."""
    # Include current file name in the key to prevent cross-record value persistence
    current_file = st.session_state.get("current_file", "unknown")
    field_key = f"{current_file}.{section}.{key}"
    # field_key = key

    # Use description as label if available, otherwise use the key
    label = schema.get("description", key) if schema else key

    # Convert value to string and handle special cases
    str_value = str(value)

    # For record_no and volg_nr fields, strip leading zeros for display
    # (but keep them for other fields like dates)
    if key in ("record_no", "volg_nr") and str_value.isdigit() and len(str_value) > 1:
        str_value = str_value.lstrip('0') or '0'

    inp = col.text_input(
        label,
        value=str_value,
        key=field_key,
        placeholder=schema.get("placeholder", "") if schema else None,
    )

    # Live value - regardless of original type
    val_now = st.session_state.get(field_key, inp)

    # For record_no and volg_nr fields, also strip leading zeros from the actual value
    # This includes handling whitespace and ensuring we strip even single leading zeros
    if key in ("record_no", "volg_nr") and isinstance(val_now, str):
        val_now = val_now.strip()  # Remove whitespace first
        if val_now.isdigit() and len(val_now) > 1:
            val_now = val_now.lstrip('0') or '0'

    # Placeholder for an eventual error message
    error_container = col.empty()

    if schema:
        valid, err = validate_field(val_now, schema, key, section)
        if not valid:
            error_container.error(err)
            st.session_state.validation_errors[field_key] = err
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
        if (
            st.button(
                "⬅️ Previous",
                key="prev_button",
                use_container_width=True,
                disabled=prev_disabled,
                help="Go to previous record (Ctrl+←)",
            )
            and not prev_disabled
        ):
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
            st.caption(
                f"✅ {len(completed_files)} completed ({completion_rate:.0%} done)"
            )
        else:
            st.caption("📊 Session starting...")

    with col_next:
        next_disabled = st.session_state.idx >= len(files) - 1
        if (
            st.button(
                "Next ➡️",
                key="next_button",
                use_container_width=True,
                disabled=next_disabled,
                help="Go to next record (Ctrl+→)",
            )
            and not next_disabled
        ):
            st.session_state.idx += 1
            st.session_state.validation_errors.clear()

    current = files[st.session_state.idx]
    st.session_state.current_file = current  # keep in sync for the next run

    # Show file status
    status = get_file_status(current)
    status_emoji = {"uncorrected": "📝", "corrected": "✅", "locked": "🔒"}
    status_color = {"uncorrected": "", "corrected": ":green", "locked": ":orange"}

    # Format filename for display (remove leading zeros)
    display_name = format_filename_for_display(current)
    st.title(f"Record {st.session_state.idx + 1}/{len(files)}: {display_name}")
    st.markdown(
        f"{status_emoji.get(status, '')} **Status**: "
        f"{status_color.get(status, '')}{status.title()}"
    )

    if status == "corrected":
        st.info("ℹ️ This file has been corrected but can be re-edited if needed")

    return current


def render_image_sidebar(data: Dict) -> None:
    with st.sidebar:
        st.header("📸 Image Reference")
        img_base = (
            data.get("image_filename")
            or os.path.splitext(st.session_state.current_file)[0]
        )
        img_bytes, img_name = load_image_from_gcs(img_base)
        if img_bytes:
            # Add zoom controls with more options
            zoom_level = st.select_slider(
                "🔍 Zoom Level",
                options=["50%", "75%", "100%", "125%", "150%", "200%", "250%"],
                value="100%",
                key="image_zoom",
                help="Adjust image size for better viewing",
            )

            # Display image with zoom - use container width for consistent sizing
            zoom_factor = int(zoom_level.rstrip("%")) / 100

            # Create a container with specific styling for image zoom
            if zoom_factor != 1.0:
                st.markdown(
                    f"""
                <div style="
                    overflow: auto;
                    max-height: 600px;
                    border: 1px solid var(--border-color, #ddd);
                    border-radius: 8px;
                    padding: 10px;
                    background: var(--background-color, white);
                    box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
                ">
                """,
                    unsafe_allow_html=True,
                )

                st.image(
                    img_bytes,
                    caption=f"📄 {img_name} ({zoom_level})",
                    use_container_width=False,
                    width=int(480 * zoom_factor),  # Fixed base width for sidebar
                )

                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.image(img_bytes, caption=f"📄 {img_name}", use_container_width=True)

            # Image info
            st.caption(f"File: {img_name}")

            # Quick image actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    "🔄 Refresh", help="Reload image", use_container_width=True
                ):
                    st.cache_data.clear()
                    st.rerun()
            with col2:
                # Download button would go here if needed
                st.button(
                    "🔍 Enhance",
                    help="Coming soon",
                    disabled=True,
                    use_container_width=True,
                )
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

        # Also clear deleted entries tracking for previous file
        prev_file = st.session_state.get("previous_file")
        if prev_file:
            for key in list(st.session_state.keys()):
                if isinstance(key, str) and key.startswith(f"{prev_file}.deleted_"):
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
        st.write("")  # Placeholder for layout consistency

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
            # Get first few field names with errors
            error_fields = list(st.session_state.validation_errors.keys())[:3]
            # Extract just the field name from keys like "main_entries_0_datum"
            field_names = [k.split('_')[-1] for k in error_fields]
            fields_preview = ', '.join(field_names)
            if error_count > 3:
                fields_preview += f" +{error_count - 3} more"
            st.error(
                f"❌ {error_count} error{'s' if error_count != 1 else ''}: "
                f"{fields_preview}"
            )
        else:
            st.success("✅ Valid")

    # Show shortcuts panel if toggled on
    if st.session_state.get("show_shortcuts_panel", False):
        st.info(
            """
        **⌨️ Keyboard Shortcuts:**
        - `Enter`: Save/validate current field
        - `Tab`: Move to next field
        - `Ctrl + S`: Save all changes and move to next record
        - `Ctrl + →`: Next record
        - `Ctrl + ←`: Previous record
        """
        )

    # Better info styling with expandable tips
    info_col, tips_col = st.columns([3, 1])

    with info_col:
        st.write("")  # Placeholder for layout consistency

    with tips_col:
        with st.expander("💡 Annotation Tips"):
            st.markdown(
                """
            **Quick Tips:**
            - Use `Tab` to move between fields
            - Date format: DDMMYY (e.g., 160636)
            - Names: Last, First (e.g., Keijzer, Tonko)
            - Leave empty if illegible
            """
            )

            # Quick reference for common patterns
            st.markdown(
                """
            **Common Patterns:**
            - House numbers: 18, 18a, 18 II, 18 huis
            - Dates: 6 digits DDMMYY
            - Years: 2 digits YY (94 = 1894)
            """
            )

    # Initialize deletion tracking
    current_file = st.session_state.get("current_file", "unknown")

    with st.form("edit_form", clear_on_submit=False):
        updated: Dict = {}

        # ─── Dynamic field generation ────────────────────────────────────
        for section, content in validated_data.items():
            # Skip footer_notes - preserve but don't display
            if section == "footer_notes":
                updated[section] = content
                continue

            # Better section headers with visual separators
            section_title = section.replace("_", " ").title()
            header_text = f"### 📋 {section_title}"

            st.markdown(header_text)
            st.markdown("---")

            section_schema = FIELD_SCHEMAS.get(section, {})

            # Dict‑like subsection
            if isinstance(content, dict):
                updated[section] = {}

                for key, orig in content.items():
                    if key.endswith("_needs review"):
                        continue
                    # Skip M/V fields - preserve them but don't show in form
                    if key in ("M", "V"):
                        updated[section][key] = orig
                        continue
                    with st.container():
                        field_schema = section_schema.get(key, {})

                        val = create_field_input(
                            section,
                            key,
                            orig,
                            st,
                            field_schema,
                        )
                        updated[section][key] = val

            # List‑like subsection
            elif isinstance(content, list):
                updated[section] = []

                # Get deleted entries tracking
                deleted_key = f"{current_file}.deleted_{section}"
                if deleted_key not in st.session_state:
                    st.session_state[deleted_key] = set()

                # Track pending deletion confirmation
                pending_confirm_key = f"{current_file}.pending_confirm_{section}"
                if pending_confirm_key not in st.session_state:
                    st.session_state[pending_confirm_key] = None

                for idx, entry in enumerate(content, start=1):
                    # Skip if this entry is marked for deletion
                    if idx in st.session_state[deleted_key]:
                        continue

                    # Better entry headers with person names
                    entry_title = f"📝 {section.title().rstrip('s')} #{idx}"

                    # Add person name to entry title if available
                    if section == "main_entries":
                        person_name = entry.get("gezinshoofd", "").strip()
                        if person_name:
                            # Show full name in entry header
                            entry_title = f"👤 **Main Entry #{idx}: {person_name}**"
                    elif section == "follow_up_entries":
                        person_name = entry.get("inwonenden", "").strip()
                        if person_name:
                            entry_title = f"👥 **Follow-up #{idx}: {person_name}**"

                    with st.expander(entry_title, expanded=True):
                        temp: Dict = {}

                        for key, orig in entry.items():
                            if key.endswith("_needs review"):
                                continue
                            # Skip M/V fields - preserve them but don't show in form
                            if key in ("M", "V"):
                                temp[key] = orig
                                continue
                            with st.container():
                                field_schema = section_schema.get(key, {})

                                val = create_field_input(
                                    f"{section}[{idx}]",
                                    key,
                                    orig,
                                    st,
                                    field_schema,
                                )
                                temp[key] = val

                        # Validate entry dates (departure must be after registration)
                        date_valid, date_error = validate_entry_dates(temp, section)
                        if not date_valid:
                            error_key = f"{current_file}.{section}[{idx}].date_comparison"
                            st.error(date_error)
                            st.session_state.validation_errors[error_key] = date_error
                        else:
                            # Clear any existing date comparison error for this entry
                            error_key = f"{current_file}.{section}[{idx}].date_comparison"
                            st.session_state.validation_errors.pop(error_key, None)

                        updated[section].append(temp)

                        # Add delete button at the bottom of the expander
                        st.markdown("---")

                        # Check if this entry is pending confirmation
                        is_pending_confirm = st.session_state[pending_confirm_key] == idx

                        if is_pending_confirm:
                            # Show confirmation buttons
                            conf_col1, conf_col2, conf_col3 = st.columns([3, 1, 1])
                            with conf_col1:
                                st.warning(f"⚠️ Delete this entry?")
                            with conf_col2:
                                confirm_yes = st.form_submit_button(
                                    "✓ Yes",
                                    help="Confirm deletion",
                                    use_container_width=True,
                                )
                            with conf_col3:
                                confirm_no = st.form_submit_button(
                                    "✗ No",
                                    help="Cancel deletion",
                                    use_container_width=True,
                                )

                            # Handle confirmation outside the columns
                            if confirm_yes:
                                st.session_state[deleted_key].add(idx)
                                st.session_state[pending_confirm_key] = None
                                st.rerun()
                            elif confirm_no:
                                st.session_state[pending_confirm_key] = None
                                st.rerun()
                        else:
                            # Show delete button
                            _, delete_col2 = st.columns([5, 1])
                            with delete_col2:
                                # Use unique label including section name to avoid duplicate key errors
                                delete_clicked = st.form_submit_button(
                                    f"🗑️ Del {section[:4]}{idx}",
                                    help=f"Delete this entry",
                                    use_container_width=True,
                                )

                            if delete_clicked:
                                # Set pending confirmation
                                st.session_state[pending_confirm_key] = idx
                                st.rerun()

            # Scalar subsection
            else:
                inp = st.text_input(
                    section, value=str(content), key=f"{current_file}.{section}"
                )
                updated[section] = type_convert(inp, content)

        # ─── Validation summary & save button ────────────────────────────
        col1, col2 = st.columns([3, 1])

        with col1:
            if st.session_state.validation_errors:
                st.error(
                    f"⚠️ {len(st.session_state.validation_errors)} validation error"
                    f"{'s' if len(st.session_state.validation_errors) != 1 else ''} – "
                    "please fix before saving."
                )
            else:
                st.success("✅ All fields validated - ready to save!")

        with col2:
            # Improved save button with keyboard hint
            save_clicked = st.form_submit_button(
                "💾 Save & Next",
                use_container_width=True,
                help="Save changes and move to next record (Ctrl+S)",
                type="primary",
            )

        # Quick data summary for review
        with st.expander(
            "📊 Data Summary", expanded=len(st.session_state.validation_errors) > 0
        ):
            summary_col1, summary_col2 = st.columns(2)

            with summary_col1:
                # Show key data points
                st.markdown("**Key Information:**")
                if isinstance(updated.get("header"), dict):
                    header = updated["header"]
                    for key, value in header.items():
                        if value and not key.endswith("_needs review"):
                            st.text(f"• {key.replace('_', ' ').title()}: {value}")
                if isinstance(updated.get("main_entries"), list):
                    for idx, entry in enumerate(updated["main_entries"], 1):
                        name = entry.get("gezinshoofd", "")
                        if name:
                            st.text(f"• Person #{idx}: {name}")

            with summary_col2:
                # Show errors
                if st.session_state.validation_errors:
                    st.markdown("**❌ Validation Errors:**")
                    errors = list(st.session_state.validation_errors.values())
                    for error in errors[:3]:
                        st.text(f"• {error}")
                    if len(errors) > 3:
                        st.text(f"• ... and {len(errors) - 3} more")

    # After the *with* block so we can safely return a value or abort
    if save_clicked:
        # Only allow saving if no validation errors
        if st.session_state.validation_errors:
            # Validation failed → stay on the same record
            return None
        # All clear → return finalised payload
        return updated

    # Scroll to top and focus first input only after navigating
    if st.session_state.get("just_navigated", False):
        # Use multiple methods to ensure scroll happens
        st.markdown(
            """
            <script>
            (function() {
                let scrollAttempts = 0;
                const maxScrollAttempts = 20;

                function forceScrollToTop() {
                    // Scroll window
                    window.scrollTo(0, 0);

                    // Scroll all scrollable elements
                    document.documentElement.scrollTop = 0;
                    document.body.scrollTop = 0;

                    // Scroll all Streamlit containers
                    const selectors = ['.main', '.stApp', '[data-testid="stAppViewContainer"]',
                                      '.block-container', 'section.main', 'div.main'];
                    selectors.forEach(selector => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            if (el && el.scrollTop !== undefined) {
                                el.scrollTop = 0;
                            }
                        });
                    });

                    scrollAttempts++;
                }

                // Immediate scroll
                forceScrollToTop();

                // Keep scrolling until we're sure we're at top or max attempts
                const scrollInterval = setInterval(function() {
                    forceScrollToTop();

                    // Check if we're at top
                    const isAtTop = window.pageYOffset === 0 &&
                                   document.documentElement.scrollTop === 0 &&
                                   document.body.scrollTop === 0;

                    if (isAtTop || scrollAttempts >= maxScrollAttempts) {
                        clearInterval(scrollInterval);

                        // Focus first input after we're done scrolling
                        setTimeout(function() {
                            const firstInput = document.querySelector('input[type="text"], textarea, select');
                            if (firstInput) {
                                firstInput.focus({preventScroll: true});
                            }
                        }, 100);
                    }
                }, 50);

                // Stop after 1 second regardless
                setTimeout(function() {
                    clearInterval(scrollInterval);
                }, 1000);
            })();
            </script>
        """,
            unsafe_allow_html=True,
        )
        st.session_state.just_navigated = False

    # Nothing to persist this turn
    return None
