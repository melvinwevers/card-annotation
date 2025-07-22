import os
import json
import streamlit as st
try:
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.error("⚠️ Dashboard requires pandas and plotly. Install with: pip install pandas plotly")

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from config import LOCK_DIR
try:
    from gcs_utils import get_gcs_file_lists, get_gcs_client, get_bucket
    from file_ops import list_available_jsons, compare_json_versions, is_file_corrected
    GCS_AVAILABLE = True
except Exception as e:
    GCS_AVAILABLE = False
    st.error(f"⚠️ GCS connection not available: {e}")


def get_dashboard_metrics() -> Dict:
    """Get real-time metrics for the dashboard"""
    if not GCS_AVAILABLE:
        return {
            'total_records': 0,
            'unvalidated': 0,
            'in_progress': 0,
            'corrected': 0,
            'completion_rate': 0
        }
    
    try:
        raw_files, corrected_files = get_gcs_file_lists()
        
        # Get lock files to determine in-progress records
        lock_files = []
        if os.path.exists(LOCK_DIR):
            lock_files = [f for f in os.listdir(LOCK_DIR) if f.endswith('.lock')]
        
        # Calculate metrics - now corrected files don't reduce the pool
        total_raw = len(raw_files)
        total_corrected = len(corrected_files)
        in_progress = len(lock_files)
        # Uncorrected = files that exist in raw but not in corrected, minus locked files
        uncorrected_files = set(raw_files) - corrected_files
        unvalidated = len(uncorrected_files) - in_progress
        
        # Calculate completion percentage
        if total_raw > 0:
            completion_rate = (total_corrected / total_raw) * 100
        else:
            completion_rate = 0
            
        return {
            'total_records': total_raw,
            'unvalidated': max(0, unvalidated),  # Ensure non-negative
            'in_progress': in_progress,
            'corrected': total_corrected,
            'completion_rate': completion_rate
        }
    except Exception as e:
        st.error(f"Error getting metrics: {e}")
        return {
            'total_records': 0,
            'unvalidated': 0,
            'in_progress': 0,
            'corrected': 0,
            'completion_rate': 0
        }


def get_lock_details() -> List[Dict]:
    """Get detailed information about locked files"""
    lock_details = []
    if not os.path.exists(LOCK_DIR):
        return lock_details
        
    for lock_file in os.listdir(LOCK_DIR):
        if not lock_file.endswith('.lock'):
            continue
            
        try:
            lock_path = os.path.join(LOCK_DIR, lock_file)
            locked_since = datetime.fromtimestamp(os.path.getmtime(lock_path))
            
            # Try to read user info from lock file
            try:
                with open(lock_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        lock_data = json.loads(content)
                        user = lock_data.get('user', 'Unknown')
                        session_id = lock_data.get('session_id', 'Unknown')
            except:
                # If lock file doesn't contain JSON, try to infer user from system
                import getpass
                user = getpass.getuser()
                session_id = 'Unknown'
            
            filename = lock_file.replace('.lock', '')
            duration = datetime.now() - locked_since
            hours = duration.total_seconds() / 3600
            
            lock_details.append({
                'filename': filename,
                'user': user,
                'session_id': session_id,
                'locked_since': locked_since,
                'duration': duration,
                'hours': hours
            })
        except Exception as e:
            continue
            
    return sorted(lock_details, key=lambda x: x['locked_since'], reverse=True)


def get_throughput_data():
    """Get throughput data over time from corrected files metadata"""
    if not GCS_AVAILABLE or not PLOTLY_AVAILABLE:
        return None
        
    try:
        client = get_gcs_client()
        bucket = get_bucket()
        
        # Get corrected files with their creation times
        corrected_blobs = list(client.list_blobs(bucket, prefix="corrected/"))
        
        throughput_data = []
        for blob in corrected_blobs:
            if blob.name.endswith('.json'):
                # Get creation/update time
                created = blob.time_created or blob.updated
                if created:
                    throughput_data.append({
                        'date': created.date(),
                        'filename': os.path.basename(blob.name),
                        'timestamp': created
                    })
        
        if not throughput_data:
            # Return empty DataFrame with proper structure
            return pd.DataFrame(columns=['date', 'count'])
            
        # Create DataFrame and aggregate by date
        df = pd.DataFrame(throughput_data)
        daily_counts = df.groupby('date').size().reset_index(name='count')
        daily_counts['date'] = pd.to_datetime(daily_counts['date'])
        
        # Fill in missing dates with 0 counts for better visualization
        if len(daily_counts) > 1:
            date_range = pd.date_range(
                start=daily_counts['date'].min(),
                end=daily_counts['date'].max(),
                freq='D'
            )
            full_range = pd.DataFrame({'date': date_range})
            daily_counts = full_range.merge(daily_counts, on='date', how='left').fillna(0)
        
        return daily_counts
        
    except Exception as e:
        st.error(f"Error getting throughput data: {e}")
        return None


def render_metrics_cards(metrics: Dict):
    """Render the main metrics cards"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📋 Total Records",
            value=metrics['total_records'],
            help="Total number of JSON records to process"
        )
    
    with col2:
        st.metric(
            label="⏳ Unvalidated",
            value=metrics['unvalidated'],
            help="Records waiting for validation"
        )
    
    with col3:
        st.metric(
            label="🔄 In Progress",
            value=metrics['in_progress'],
            help="Records currently being edited"
        )
    
    with col4:
        st.metric(
            label="✅ Corrected",
            value=metrics['corrected'],
            help="Records completed and saved"
        )


def render_progress_chart(metrics: Dict):
    """Render progress pie chart"""
    if not PLOTLY_AVAILABLE:
        return
        
    # Create pie chart data
    labels = ['Unvalidated', 'In Progress', 'Corrected']
    values = [
        metrics['unvalidated'],
        metrics['in_progress'],
        metrics['corrected']
    ]
    
    # Create pie chart
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=.3,
        marker_colors=['#ff9999', '#66b3ff', '#99ff99']
    )])
    
    fig.update_layout(
        title='Overall Progress',
        showlegend=True,
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_throughput_chart(df):
    """Render throughput over time chart"""
    if not PLOTLY_AVAILABLE:
        return
        
    if df is None or df.empty or len(df) == 0:
        return
    
    # Create line chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['count'],
        mode='lines+markers',
        name='Records Completed',
        line=dict(color='#00CC88', width=2),
        marker=dict(size=8)
    ))
    
    # Update layout
    fig.update_layout(
        title='Records Completed Over Time',
        xaxis_title='Date',
        yaxis_title='Number of Records',
        showlegend=True,
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def unlock_stale_records(hours_threshold: int = 2) -> List[Dict]:
    """Unlock records that have been locked for more than the specified hours"""
    unlocked_files = []
    if not os.path.exists(LOCK_DIR):
        return unlocked_files
        
    for lock_file in os.listdir(LOCK_DIR):
        if not lock_file.endswith('.lock'):
            continue
            
        try:
            lock_path = os.path.join(LOCK_DIR, lock_file)
            locked_since = datetime.fromtimestamp(os.path.getmtime(lock_path))
            duration = datetime.now() - locked_since
            hours = duration.total_seconds() / 3600
            
            if hours > hours_threshold:
                user = 'Unknown'  # Default value
                # Try to read user info before removing
                try:
                    with open(lock_path, 'r') as f:
                        content = f.read().strip()
                        if content:
                            lock_data = json.loads(content)
                            user = lock_data.get('user', 'Unknown')
                except:
                    pass  # Keep the default 'Unknown' user
                
                # Remove the lock file
                os.remove(lock_path)
                unlocked_files.append({
                    'filename': lock_file.replace('.lock', ''),
                    'user': user,
                    'duration': f"{hours:.1f}h"
                })
        except Exception as e:
            st.error(f"Error unlocking {lock_file}: {e}")
            continue
            
    return unlocked_files


def render_activity_section(lock_details: List[Dict]):
    """Render the current activity section with detailed information"""
    st.subheader("👥 Current Activity")
    
    if not lock_details:
        st.info("No active records at the moment")
        return
    
    # Check for stale records first and show warning prominently
    long_running = [lock for lock in lock_details if lock['hours'] > 2]
    if long_running:
        st.error(f"⚠️ WARNING: {len(long_running)} record(s) have been locked for more than 2 hours!")
        st.markdown("---")
        
        # Show details of stale records
        st.markdown("### 🔒 Stale Records")
        stale_data = []
        for lock in long_running:
            stale_data.append({
                'Record': lock['filename'],
                'User': lock['user'],
                'Locked Since': lock['locked_since'].strftime('%Y-%m-%d %H:%M'),
                'Duration': f"{lock['hours']:.1f}h"
            })
        
        if PLOTLY_AVAILABLE:
            df_stale = pd.DataFrame(stale_data)
            st.dataframe(df_stale, use_container_width=True, hide_index=True)
        else:
            for item in stale_data:
                st.write(f"**{item['Record']}** - Locked by {item['User']} since {item['Locked Since']} ({item['Duration']})")
        
        # Add unlock button
        if st.button("🔓 Unlock All Stale Records", type="primary", use_container_width=True):
            unlocked = unlock_stale_records()
            if unlocked:
                st.success(f"✅ Successfully unlocked {len(unlocked)} stale records:")
                for record in unlocked:
                    st.write(f"- {record['filename']} (locked by {record['user']} for {record['duration']})")
                st.rerun()
            else:
                st.error("No stale records found to unlock")
        
        st.markdown("---")
    
    # Group locks by user
    user_locks = {}
    for lock in lock_details:
        user = lock['user']
        if user not in user_locks:
            user_locks[user] = []
        user_locks[user].append(lock)
    
    # Display user activity
    for user, locks in user_locks.items():
        st.markdown(f"### 👤 {user}")
        
        # Create a DataFrame for this user's locks
        display_data = []
        for lock in locks:
            duration_str = str(lock['duration']).split('.')[0]  # Remove microseconds
            display_data.append({
                'Record': lock['filename'],
                'Started': lock['locked_since'].strftime('%Y-%m-%d %H:%M'),
                'Duration': duration_str,
                'Hours': f"{lock['hours']:.1f}h"
            })
        
        if PLOTLY_AVAILABLE:
            df_locks = pd.DataFrame(display_data)
            st.dataframe(df_locks, use_container_width=True, hide_index=True)
        else:
            # Fallback display without pandas
            for item in display_data:
                st.write(f"**{item['Record']}** - Started: {item['Started']} ({item['Duration']})")
    
    # Overall statistics
    st.markdown("### 📊 Activity Summary")
    total_locks = len(lock_details)
    avg_duration = sum(lock['hours'] for lock in lock_details) / total_locks if total_locks > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Active Records", total_locks)
    with col2:
        st.metric("Active Users", len(user_locks))
    with col3:
        st.metric("Average Lock Duration", f"{avg_duration:.1f}h")


def render_comparison_analytics():
    """Render comparison analytics section"""
    st.subheader("📊 Comparison Analytics")
    
    if not GCS_AVAILABLE:
        st.info("GCS connection required for comparison analytics")
        return
        
    try:
        raw_files, corrected_files = get_gcs_file_lists()
        
        # Get files that have both original and corrected versions
        comparable_files = [f for f in raw_files if f in corrected_files]
        
        if not comparable_files:
            st.info("No files available for comparison yet. Complete some corrections to enable analytics.")
            return
            
        st.metric("Files Available for Comparison", len(comparable_files))
        
        # Sample comparison for demonstration
        if st.button("🔍 Analyze Sample Corrections", use_container_width=True):
            with st.spinner("Analyzing corrections..."):
                sample_size = min(10, len(comparable_files))
                sample_files = comparable_files[:sample_size]
                
                changes_detected = 0
                for filename in sample_files:
                    comparison = compare_json_versions(filename)
                    if comparison and comparison.get('has_changes'):
                        changes_detected += 1
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Sample Size", sample_size)
                with col2:
                    st.metric("Files with Changes", changes_detected)
                    
                if changes_detected > 0:
                    change_rate = (changes_detected / sample_size) * 100
                    st.success(f"✅ Change rate: {change_rate:.1f}% of sampled files had corrections")
                else:
                    st.info("No changes detected in sample - original data may already be accurate")
        
        # File picker for detailed comparison
        st.markdown("### 🔍 Detailed File Comparison")
        selected_file = st.selectbox(
            "Select a file to compare:",
            comparable_files,
            key="comparison_file_selector"
        )
        
        if st.button(f"Compare {selected_file}", use_container_width=True):
            comparison = compare_json_versions(selected_file)
            if comparison:
                if comparison['has_changes']:
                    st.success("✅ Changes detected between original and corrected versions")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Original Version:**")
                        st.json(comparison['original'])
                    with col2:
                        st.markdown("**Corrected Version:**")
                        st.json(comparison['corrected'])
                else:
                    st.info("ℹ️ No differences found between versions")
            else:
                st.error("Failed to load comparison data")
                
    except Exception as e:
        st.error(f"Error in comparison analytics: {e}")


def render_dashboard():
    """Main dashboard rendering function"""
    st.title("📊 JSON Validator Dashboard")
    st.markdown("Real-time insights into the correction process")
    
    # Add refresh button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh", help="Update all metrics"):
            # Clear caches to get fresh data
            if GCS_AVAILABLE:
                get_gcs_file_lists.clear()
            st.rerun()
    
    with col2:
        st.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get metrics
    metrics = get_dashboard_metrics()
    render_metrics_cards(metrics)
    
    # Two column layout for charts
    col1, col2 = st.columns(2)
    
    with col1:
        render_progress_chart(metrics)
    
    with col2:
        st.subheader("📈 Throughput Over Time")
        throughput_data = get_throughput_data()
        if throughput_data is not None and not throughput_data.empty:
            render_throughput_chart(throughput_data)
        else:
            st.info("No throughput data available yet. Complete some records to see trends!")
    
    st.markdown("---")
    
    # Get lock details
    lock_details = get_lock_details()
    
    # Render activity section with detailed information
    render_activity_section(lock_details)
    
    st.markdown("---")
    
    # Render comparison analytics section
    render_comparison_analytics() 