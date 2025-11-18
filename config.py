import streamlit as st

PAGE_CONFIG = {
    "page_title": "JSON Validator",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

LOCK_DIR = "data/locks"
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tif', '.jp2']
DEFAULT_SIDEBAR_WIDTH = 500

# Cache TTL settings (in seconds)
CACHE_TTL_SHORT = 300  # 5 minutes - for frequently changing data
CACHE_TTL_MEDIUM = 600  # 10 minutes - for moderately stable data
CACHE_TTL_LONG = 3600  # 1 hour - for rarely changing data

def apply_custom_css():
    """Apply custom CSS for sidebar width and improved styling - dark mode compatible"""
    st.markdown(f"""
        <style>
            /* Sidebar width */
            section[data-testid=\"stSidebar\"] {{
                width: {DEFAULT_SIDEBAR_WIDTH}px !important;
            }}
            .main .block-container {{
                max-width: calc(100% - {DEFAULT_SIDEBAR_WIDTH + 20}px) !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }}
            section[data-testid=\"stSidebar\"] > div:first-child {{
                width: {DEFAULT_SIDEBAR_WIDTH}px !important;
            }}
            
            /* Form styling improvements - theme aware */
            .stForm {{
                border: 1px solid var(--border-color, #e6e6e6);
                border-radius: 8px;
                padding: 20px;
                background-color: var(--background-color, rgba(255,255,255,0.05));
                backdrop-filter: blur(10px);
            }}
            
            /* Dark mode detection and variables */
            @media (prefers-color-scheme: dark) {{
                :root {{
                    --border-color: #404040;
                    --background-color: rgba(255,255,255,0.02);
                    --error-bg: rgba(255, 68, 68, 0.1);
                    --success-bg: rgba(76, 175, 80, 0.1);
                    --text-color: #ffffff;
                }}
            }}

            @media (prefers-color-scheme: light) {{
                :root {{
                    --border-color: #e6e6e6;
                    --background-color: #fafafa;
                    --error-bg: #ffebee;
                    --success-bg: #f1f8e9;
                    --text-color: #000000;
                }}
            }}
            
            /* Better button styling - theme aware */
            .stButton > button {{
                border-radius: 6px;
                border: 1px solid var(--border-color, #ddd);
                transition: all 0.2s ease;
                background: var(--background-color, transparent);
            }}
            
            .stButton > button:hover {{
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                border-color: var(--primary-color, #ff4b4b);
            }}
            
            /* Error field highlighting - theme aware */
            .error-field {{
                border-left: 3px solid #ff4444;
                background-color: var(--error-bg);
            }}
            
            /* Success field highlighting - theme aware */
            .valid-field {{
                border-left: 3px solid #4caf50;
                background-color: var(--success-bg);
            }}
            
            /* Better container spacing */
            .block-container {{
                padding-top: 2rem !important;
            }}
            
            /* Improved input field styling */
            .stTextInput > div > div > input {{
                border-radius: 6px;
                border: 1px solid var(--border-color, #ddd);
                background-color: var(--background-color, #ffffff);
                transition: border-color 0.2s ease;
            }}
            
            .stTextInput > div > div > input:focus {{
                border-color: var(--primary-color, #ff4b4b);
                box-shadow: 0 0 0 1px var(--primary-color, #ff4b4b);
            }}
            
            /* Checkbox improvements */
            .stCheckbox {{
                padding: 0.25rem 0;
            }}
            
            /* Progress bar styling */
            .stProgress > div > div > div {{
                border-radius: 10px;
            }}
            
            /* Expander improvements */
            .streamlit-expanderHeader {{
                font-weight: 600;
                border-radius: 6px;
                background-color: var(--background-color, rgba(0,0,0,0.02));
            }}
            
            /* Alert improvements */
            .stAlert {{
                border-radius: 8px;
                border-left: 4px solid var(--primary-color, #ff4b4b);
            }}
            
            /* Column spacing improvements */
            .element-container {{
                margin-bottom: 0.1rem;
            }}

            /* Reduce spacing between form fields */
            .stTextInput {{
                margin-bottom: 0rem;
            }}

            /* Reduce spacing in form containers */
            .stForm .element-container {{
                margin-bottom: 0rem;
            }}

            /* Tighter spacing for text input labels */
            .stTextInput > label {{
                margin-bottom: 0.1rem !important;
                padding-bottom: 0 !important;
            }}

            /* Reduce padding inside text inputs */
            .stTextInput > div {{
                margin-bottom: 0.2rem !important;
            }}
            
            /* Sidebar improvements */
            .css-1d391kg {{
                background-color: var(--background-color, rgba(255,255,255,0.02));
            }}
        </style>
        
        <script>
            // Keyboard shortcuts handler - use capture phase to catch events early
            document.addEventListener('keydown', function(e) {{
                // Handle Enter key in input fields - just save/validate, don't move
                if ((e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') && e.key === 'Enter') {{
                    // Stop form submission
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();

                    // Just blur to trigger validation/save
                    e.target.blur();

                    // Re-focus the same field after a brief moment
                    setTimeout(() => {{
                        e.target.focus();
                    }}, 50);

                    return false;
                }}

                // Only handle other shortcuts if not in an input field
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
                    return;
                }}

                // Ctrl+S: Save (prevent default browser save)
                if (e.ctrlKey && e.key === 's') {{
                    e.preventDefault();
                    const saveButton = document.querySelector('button[kind="formSubmit"]');
                    if (saveButton) {{
                        saveButton.click();
                        console.log('Save shortcut triggered');
                    }}
                }}

                // Ctrl+Left: Previous
                if (e.ctrlKey && e.key === 'ArrowLeft') {{
                    e.preventDefault();
                    const prevButton = Array.from(document.querySelectorAll('button')).find(btn =>
                        btn.textContent.includes('Previous') || btn.textContent.includes('⬅️')
                    );
                    if (prevButton && !prevButton.disabled) {{
                        prevButton.click();
                        console.log('Previous shortcut triggered');
                    }}
                }}

                // Ctrl+Right: Next
                if (e.ctrlKey && e.key === 'ArrowRight') {{
                    e.preventDefault();
                    const nextButton = Array.from(document.querySelectorAll('button')).find(btn =>
                        btn.textContent.includes('Next') || btn.textContent.includes('➡️')
                    );
                    if (nextButton && !nextButton.disabled) {{
                        nextButton.click();
                        console.log('Next shortcut triggered');
                    }}
                }}
            }}, true);  // Use capture phase to intercept Enter key before form submission
            
            // Theme detection and CSS variable updates
            function updateTheme() {{
                const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
                const root = document.documentElement;
                
                if (isDark) {{
                    root.style.setProperty('--border-color', '#404040');
                    root.style.setProperty('--background-color', 'rgba(255,255,255,0.02)');
                    root.style.setProperty('--text-color', '#ffffff');
                }} else {{
                    root.style.setProperty('--border-color', '#e6e6e6');
                    root.style.setProperty('--background-color', '#fafafa');
                    root.style.setProperty('--text-color', '#000000');
                }}
            }}
            
            // Update theme on load and when it changes
            updateTheme();
            if (window.matchMedia) {{
                window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateTheme);
            }}
        </script>
    """, unsafe_allow_html=True)