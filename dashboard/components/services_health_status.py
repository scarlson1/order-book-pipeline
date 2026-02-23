from typing import Dict
import streamlit as st

from dashboard.utils.async_runner import run_async


def render_status_indicators():
    """Render status indicators with actual health checks."""
    
    # Get health data (in real app, use st.fragment for async)
    data_client = st.session_state.data_layer
    result = run_async(data_client.health_check(), timeout=10)
    
    statuses = {
        "Redpanda": True,   # Replace with actual health check
        "Flink": True,      # Replace with actual health check  
        "PostgreSQL": result['database']['healthy'],
        "Redis": result['redis'],
    }

    # st.markdown("""
    # <style>
    #     .fixed-header {
    #         position: fixed;
    #         top: 0;
    #         left: 0;
    #         right: 0;
    #         z-index: 1;
    #         background-color: white; /* Match your app's background */
    #         padding: 10px;
    #         box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    #     }
    # </style>
    # """, unsafe_allow_html=True)

    # Use a container for the header content
    with st.container():
        # st.markdown('<div class="fixed-header"><h1>My Sticky Header</h1></div>', unsafe_allow_html=True)


        cols = st.columns(4)
        
        for i, (service, is_healthy) in enumerate(statuses.items()):
            color = "#22c55e" if is_healthy else "#ef4444"  # green or red
            label = "●" if is_healthy else "●"
            
            with cols[i]:
                st.markdown(
                    f"""
                    <div  style="
                        text-align: center;
                        padding: 4px;
                        background-color: #1f2937;
                        border-radius: 6px;
                        border: 1px solid {"#22c55e" if is_healthy else "#ef4444"};
                    ">
                        <span style="color: {color}; font-size: 10px;">{label}</span>
                        <span style="color: white; font-size: 12px;">{service}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
