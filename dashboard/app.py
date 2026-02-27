import sys
from pathlib import Path

# Add project root to sys.path for Streamlit Cloud compatibility
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from dashboard.components.alert_feed import render_alert_feed
from dashboard.components.imbalance_trend import render_imbalance_trend
from dashboard.components.metrics_cards import render_metrics_cards
from dashboard.components.multi_metric_windows import render_multi_metric_windows
from dashboard.components.orderbook_viz import render_orderbook_viz
from dashboard.components.services_health_status import render_status_indicators
from dashboard.components.timeseries import render_timeseries_chart
from dashboard.components.volatility_heatmap import render_volatility_heatmap
# from dashboard.components.windowed_aggregates import render_windowed_aggregates
from dashboard.components.windowed_statistics import render_windowed_stats
from dashboard.data.data_layer import DataLayer
from src.config import settings

# Initialize once per session
if 'data_layer' not in st.session_state:
    st.session_state.data_layer = DataLayer()

render_status_indicators()

# st.title('Crypto Orderbook Dashboard')
st.set_page_config(
    page_title='Crypto Orderbook Dashboard',
    page_icon=':chart_with_upwards_trend:',
    layout='wide',
    initial_sidebar_state="expanded"
)

"""
# :material/query_stats: Crypto Orderbook Pipeline

Stream orderbook data in real-time with metric calculations & alerts.
"""

# st.sidebar.title()
# st.logo(f'🚀 Stock Pipeline')
# st.logo(sidebar_logo, icon_image=main_body_logo) # https://docs.streamlit.io/develop/api-reference/media/st.logo

symbol = st.sidebar.selectbox(
    'Symbol',
    settings.symbol_list
)

# interval = st.sidebar.selectbox(
#     'Interval',
#     ('1m', '5m', '1h', '4h', '1d')
# )
# st.sidebar.caption('not currently using interval input')

# refresh at component level
# refresh_rate = st.sidebar.selectbox(
#     'Refresh rate',
#     options=[1000, 2000, 5000, 10000, 30000, 60000],  # milliseconds
#     format_func=lambda x: f"{x // 1000}s",  # display as "1s", "2s", etc.
#     index=3
# )

timezone_pref = st.sidebar.selectbox(
    'Timezone',
    ['America/New_York', 'America/Chicago', 'America/Los_Angeles', 'Europe/London', 'UTC'],
    index=0
)

st.sidebar.space('stretch')

# doesn't work (need to go CSS injection route to switch themes)
# # Initialize theme state
# if "theme" not in st.session_state:
#     st.session_state.theme = "dark"

# # Sidebar theme switcher
# # with st.sidebar:
#     # st.header("⚙️ Settings")
# theme_choice = st.sidebar.radio(
#     "Choose Theme:",
#     options=["light", "dark"],
#     index=0 if st.session_state.theme == "light" else 1
# )

# if theme_choice != st.session_state.theme:
#     st.session_state.theme = theme_choice
#     st.rerun()

# display metrics (price, imbalance, spread, volume)
render_metrics_cards(symbol)

# display real-time imbalance chart
with st.container(border=True):
    render_timeseries_chart(symbol, hours=1, ) # interval=interval

with st.container(border=True):
    render_orderbook_viz(symbol=symbol, depth_levels=20)


# active alerts
render_alert_feed(symbol=symbol, limit=50)

# two columns: windowed statistics; alert frequency
col_windowed_stats, col_alert_freq = st.columns(2)

with col_windowed_stats:
    st.text('📊 Windowed Statistics')
    render_windowed_stats(symbol, timezone_pref=timezone_pref)

with col_alert_freq:
    # st.bar_chart()
    st.text('TODO: Alert Frequency')


with st.container(border=True):
    render_imbalance_trend(symbol, timezone_pref)

with st.container(border=True):
    render_volatility_heatmap(symbol=symbol, timezone_pref=timezone_pref)

with st.container(border=True):
    render_multi_metric_windows(symbol=symbol, timezone_pref=timezone_pref)

#################################
# ===== dynamic theme switcher =====
#################################

# # ==================== PAGE CONFIG ====================
# st.set_page_config(
#     page_title="Theme Switcher - Config Based",
#     page_icon="🎨",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# # ==================== THEME PERSISTENCE SETUP ====================
# PREFERENCES_FILE = ".streamlit/user_preferences.json"

# def ensure_preferences_file():
#     """Create preferences file if it doesn't exist"""
#     os.makedirs(".streamlit", exist_ok=True)
#     if not os.path.exists(PREFERENCES_FILE):
#         with open(PREFERENCES_FILE, "w") as f:
#             json.dump({"theme": "light"}, f)

# def load_saved_theme():
#     """Load theme preference from file"""
#     ensure_preferences_file()
#     try:
#         with open(PREFERENCES_FILE, "r") as f:
#             prefs = json.load(f)
#             return prefs.get("theme", "light")
#     except:
#         return "light"

# def save_theme_preference(theme):
#     """Save theme preference to file"""
#     ensure_preferences_file()
#     with open(PREFERENCES_FILE, "w") as f:
#         json.dump({"theme": theme}, f)

# # ==================== THEME CONFIGURATIONS ====================
# THEME_CONFIGS = {
#     "light": {
#         "primaryColor": "#FF6B6B",
#         "backgroundColor": "#FFFFFF",
#         "secondaryBackgroundColor": "#F0F2F6",
#         "textColor": "#262730",
#         "font": "sans serif",
#         "base": "light",
#     },
#     "dark": {
#         "primaryColor": "#FF6B6B",
#         "backgroundColor": "#0E1117",
#         "secondaryBackgroundColor": "#262730",
#         "textColor": "#FAFAFA",
#         "font": "sans serif",
#         "base": "dark",
#     },
#     "ocean": {
#         "primaryColor": "#00D4FF",
#         "backgroundColor": "#001F3F",
#         "secondaryBackgroundColor": "#003D5C",
#         "textColor": "#E8F4F8",
#         "font": "sans serif",
#         "base": "dark",
#     },
#     "forest": {
#         "primaryColor": "#2ECC71",
#         "backgroundColor": "#0B1E0F",
#         "secondaryBackgroundColor": "#1A3A1F",
#         "textColor": "#E8F5E9",
#         "font": "sans serif",
#         "base": "dark",
#     },
#     "sunset": {
#         "primaryColor": "#FF6B35",
#         "backgroundColor": "#FFF3E0",
#         "secondaryBackgroundColor": "#FFE0B2",
#         "textColor": "#4E342E",
#         "font": "sans serif",
#         "base": "light",
#     }
# }

# # ==================== SESSION STATE INITIALIZATION ====================
# if "theme" not in st.session_state:
#     st.session_state.theme = load_saved_theme()

# # ==================== CONFIG FILE MANAGEMENT ====================
# def create_or_update_config():
#     """Create or update .streamlit/config.toml with current theme"""
#     os.makedirs(".streamlit", exist_ok=True)
    
#     theme_config = THEME_CONFIGS[st.session_state.theme]
    
#     config_content = f"""
# [theme]
# primaryColor = "{theme_config['primaryColor']}"
# backgroundColor = "{theme_config['backgroundColor']}"
# secondaryBackgroundColor = "{theme_config['secondaryBackgroundColor']}"
# textColor = "{theme_config['textColor']}"
# font = "{theme_config['font']}"
# base = "{theme_config['base']}"

# [client]
# showErrorDetails = true

# [logger]
# level = "info"
# """
    
#     with open(".streamlit/config.toml", "w") as f:
#         f.write(config_content)

# # ==================== CUSTOM CSS ENHANCEMENT ====================
# def apply_enhanced_styling():
#     """Apply additional CSS for better theming"""
#     theme = st.session_state.theme
#     theme_config = THEME_CONFIGS[theme]
    
#     css = f"""
#     <style>
#         /* Color scheme */
#         :root {{
#             color-scheme: {'dark' if theme_config['base'] == 'dark' else 'light'};
#         }}
        
#         /* Sidebar Styling */
#         .sidebar .sidebar-content {{
#             background-color: {theme_config['secondaryBackgroundColor']};
#         }}
        
#         /* Header Styling */
#         header {{
#             background-color: {theme_config['secondaryBackgroundColor']};
#             border-bottom: 2px solid {theme_config['primaryColor']};
#         }}
        
#         /* Card Styling */
#         .stCard {{
#             background-color: {theme_config['secondaryBackgroundColor']};
#             border-left: 4px solid {theme_config['primaryColor']};
#             padding: 15px;
#             border-radius: 8px;
#         }}
        
#         /* Button Styling */
#         button {{
#             transition: all 0.3s ease;
#         }}
        
#         button:hover {{
#             background-color: {theme_config['primaryColor']};
#             color: white;
#             transform: translateY(-2px);
#             box-shadow: 0 4px 8px rgba(0,0,0,0.2);
#         }}
        
#         /* Metric Container */
#         .metric-value {{
#             color: {theme_config['primaryColor']};
#             font-weight: bold;
#         }}
        
#         /* Expander */
#         .streamlit-expanderContent {{
#             background-color: {theme_config['secondaryBackgroundColor']};
#         }}
        
#         /* Links */
#         a {{
#             color: {theme_config['primaryColor']};
#             text-decoration: none;
#         }}
        
#         a:hover {{
#             text-decoration: underline;
#         }}
        
#         /* Input Focus */
#         input:focus, textarea:focus, select:focus {{
#             border-color: {theme_config['primaryColor']} !important;
#             box-shadow: 0 0 5px {theme_config['primaryColor']}33;
#         }}
        
#         /* Divider */
#         hr {{
#             border-top: 2px solid {theme_config['primaryColor']};
#             opacity: 0.3;
#         }}
        
#         /* Code Block */
#         pre {{
#             background-color: {theme_config['secondaryBackgroundColor']};
#             border-left: 3px solid {theme_config['primaryColor']};
#             border-radius: 5px;
#         }}
        
#         /* Tab Styling */
#         .stTabs [data-baseweb="tab-list"] {{
#             gap: 2px;
#         }}
        
#         .stTabs [data-baseweb="tab"] {{
#             background-color: {theme_config['secondaryBackgroundColor']};
#             border-radius: 4px 4px 0 0;
#         }}
        
#         .stTabs [aria-selected="true"] {{
#             background-color: {theme_config['primaryColor']};
#             color: white;
#         }}
#     </style>
#     """
    
#     st.markdown(css, unsafe_allow_html=True)

# # ==================== SIDEBAR NAVIGATION ====================
# with st.sidebar:
#     st.title("⚙️ Settings")
    
#     st.subheader("🎨 Theme Selection")
    
#     theme_emojis = {
#         "light": "☀️ Light",
#         "dark": "🌙 Dark",
#         "ocean": "🌊 Ocean",
#         "forest": "🌲 Forest",
#         "sunset": "🌅 Sunset"
#     }
    
#     theme_options = list(theme_emojis.values())
#     current_theme_index = list(theme_emojis.keys()).index(st.session_state.theme)
    
#     selected_theme_display = st.selectbox(
#         "Select a theme:",
#         options=theme_options,
#         index=current_theme_index,
#         label_visibility="collapsed"
#     )
    
#     # Extract theme key from display name
#     selected_theme_key = [k for k, v in theme_emojis.items() if v == selected_theme_display][0]
    
#     if selected_theme_key != st.session_state.theme:
#         st.session_state.theme = selected_theme_key
#         save_theme_preference(selected_theme_key)
#         st.rerun()
    
#     st.divider()
    
#     # Theme Info Box
#     with st.expander("ℹ️ Theme Information"):
#         st.write(f"**Current Theme:** {selected_theme_display}")
#         st.write(f"**Base:** {THEME_CONFIGS[st.session_state.theme]['base'].capitalize()}")
#         st.write(f"**Primary Color:** {THEME_CONFIGS[st.session_state.theme]['primaryColor']}")

# # ==================== APPLY THEME AND STYLING ====================
# apply_enhanced_styling()
# create_or_update_config()

# # ==================== MAIN CONTENT ====================

# st.title("🎨 Theme Switcher - Config File Solution")
# st.markdown("""
# This app demonstrates **persistent theme switching** using Streamlit's config files.
# Your theme preference is **saved automatically** and will be remembered across sessions!

# > 📝 **Note:** This solution creates a `.streamlit/config.toml` file that persists theme settings.
# """)

# st.divider()

# # Section 1: Theme Overview
# st.subheader("🎯 Available Themes")

# theme_info = {
#     "Light": "Perfect for daytime use, bright and clean interface",
#     "Dark": "Easy on the eyes, great for night-time viewing",
#     "Ocean": "Cool blue tones inspired by the ocean",
#     "Forest": "Natural green tones for a calming effect",
#     "Sunset": "Warm orange and yellow tones"
# }

# cols = st.columns(len(theme_info))
# for col, (theme_name, description) in zip(cols, theme_info.items()):
#     with col:
#         st.info(f"**{theme_name}**\n\n{description}")

# st.divider()

# # Section 2: Message Boxes
# st.subheader("📊 Message Boxes Demo")
# col1, col2 = st.columns(2)

# with col1:
#     st.info("ℹ️ This is an info message. Your theme choice is persistent!")
#     st.success("✅ Your preference is automatically saved to `.streamlit/user_preferences.json`")

# with col2:
#     st.warning("⚠️ Config files are created in `.streamlit/config.toml`")
#     st.error("❌ Remember to add `.streamlit/` to your `.gitignore` if needed")

# st.divider()

# # Section 3: Metrics Dashboard
# st.subheader("📈 Dashboard Metrics")
# col1, col2, col3, col4 = st.columns(4)

# metrics_data = [
#     ("Total Users", "12,456", "+15.3%"),
#     ("Revenue", "$45,231", "+8.2%"),
#     ("Growth Rate", "34.5%", "+2.1%"),
#     ("Engagement", "78.9%", "+5.4%"),
# ]

# for col, (label, value, delta) in zip([col1, col2, col3, col4], metrics_data):
#     with col:
#         st.metric(label=label, value=value, delta=delta)

# st.divider()

# # Section 4: Data Visualization
# st.subheader("📉 Analytics Charts")

# # Generate sample data
# np.random.seed(42)
# dates = [datetime.now() - timedelta(days=x) for x in range(30, 0, -1)]
# data = pd.DataFrame({
#     'Date': dates,
#     'Revenue': np.cumsum(np.random.randn(30) * 100) + 5000,
#     'Users': np.cumsum(np.random.randn(30) * 20) + 1000,
#     'Engagement': np.cumsum(np.random.randn(30) * 2) + 70
# })

# col1, col2 = st.columns(2)

# with col1:
#     st.write("**Revenue Trend**")
#     st.line_chart(data.set_index('Date')['Revenue'])

# with col2:
#     st.write("**User Growth**")
#     st.area_chart(data.set_index('Date')['Users'])

# st.divider()

# # Section 5: Data Table
# st.subheader("📋 Sample Data")

# sample_data = pd.DataFrame({
#     'ID': range(1, 11),
#     'Product': ['Product A', 'Product B', 'Product C', 'Product D', 'Product E',
#                 'Product F', 'Product G', 'Product H', 'Product I', 'Product J'],
#     'Sales': np.random.randint(500, 5000, 10),
#     'Users': np.random.randint(100, 1000, 10),
#     'Status': ['✅ Active'] * 7 + ['⏳ Pending'] * 3
# })

# st.dataframe(sample_data, width='stretch')

# st.divider()

# # Section 6: Tabs Example
# st.subheader("📑 Tabbed Interface")

# tab1, tab2, tab3 = st.tabs(["Overview", "Details", "Settings"])

# with tab1:
#     st.write("This is the overview tab.")
#     st.write("Your selected theme affects the styling of these tabs!")

# with tab2:
#     st.write("Here are the details about the current configuration:")
#     st.code(f"""
# Current Theme: {st.session_state.theme}
# Config File: .streamlit/config.toml
# Preferences File: .streamlit/user_preferences.json
#     """)

# with tab3:
#     st.write("Theme configuration is stored in multiple files:")
#     st.json(THEME_CONFIGS[st.session_state.theme])

# st.divider()

# # Section 7: Interactive Elements
# st.subheader("🎯 Interactive Components")

# col1, col2 = st.columns(2)

# with col1:
#     st.write("**User Input:**")
#     name = st.text_input("Enter your name", placeholder="Type here...")
#     if name:
#         st.success(f"Welcome, {name}! 👋")
    
#     st.write("**Slider Control:**")
#     age = st.slider("How old are you?", 0, 100, 25)
#     st.write(f"You are {age} years old")

# with col2:
#     st.write("**Dropdown Selection:**")
#     option = st.selectbox("Choose an option", 
#                          ["Python", "JavaScript", "Go", "Rust", "Java"])
#     st.write(f"You selected: {option}")
    
#     st.write("**Multiple Choice:**")
#     agree = st.checkbox("I agree with the terms & conditions")
#     if agree:
#         st.balloons()

# st.divider()

# # Section 8: Configuration Files
# st.subheader("💻 Configuration Details")

# with st.expander("📄 View Config Files"):
#     col1, col2 = st.columns(2)
    
#     with col1:
#         st.write("**config.toml:**")
#         try:
#             with open(".streamlit/config.toml", "r") as f:
#                 st.code(f.read(), language="toml")
#         except:
#             st.info("Config file will be created on first theme change")
    
#     with col2:
#         st.write("**user_preferences.json:**")
#         try:
#             with open(".streamlit/user_preferences.json", "r") as f:
#                 st.code(f.read(), language="json")
#         except:
#             st.info("Preferences file will be created automatically")

# st.divider()

# # Footer with comparison
# st.write("""
# ---
# ### 📊 Solution 2 Features:

# ✅ **Persistent theme preferences** - Settings saved across sessions  
# ✅ **Config file based** - Uses `.streamlit/config.toml`  
# ✅ **Multiple theme options** - Light, Dark, Ocean, Forest, Sunset  
# ✅ **File-based persistence** - Theme stored in JSON file  
# ✅ **Professional appearance** - Enhanced CSS styling  
# ✅ **Easy management** - Preferences stored locally  

# ### ⚠️ Important Notes:

# - Add `.streamlit/` to `.gitignore` if using git
# - Config file is auto-generated and updated
# - User preferences stored in JSON format
# - Works across browser sessions

# ### 🚀 When to use Solution 2:

# Perfect for apps where you want **persistent theme preferences** that survive page refreshes and sessions.
# """)