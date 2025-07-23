import streamlit as st

PAGE_CONFIG = {
    "page_title": "JSON Validator",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

LOCK_DIR = "data/locks"
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tif']
DEFAULT_SIDEBAR_WIDTH = 500

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
                    --priority-bg: rgba(255, 107, 107, 0.1);
                    --error-bg: rgba(255, 68, 68, 0.1);
                    --success-bg: rgba(76, 175, 80, 0.1);
                    --text-color: #ffffff;
                }}
            }}
            
            @media (prefers-color-scheme: light) {{
                :root {{
                    --border-color: #e6e6e6;
                    --background-color: #fafafa;
                    --priority-bg: #fff5f5;
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
            
            /* Priority field highlighting - theme aware */
            .priority-field {{
                border-left: 3px solid #ff6b6b;
                padding-left: 10px;
                background-color: var(--priority-bg);
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
                margin-bottom: 0.5rem;
            }}
            
            /* Sidebar improvements */
            .css-1d391kg {{
                background-color: var(--background-color, rgba(255,255,255,0.02));
            }}
        </style>
        
        <script>
            // Keyboard shortcuts handler
            document.addEventListener('keydown', function(e) {{
                // Only handle shortcuts if not in an input field
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
            }});
            
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