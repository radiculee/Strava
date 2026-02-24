"""
Personalized Strava cycling dashboard.

Reads pipeline outputs from data/cycling_summary.csv and data/cycling_paths.csv.
Data freshness is controlled by the scheduled daily ETL pipeline.
"""

from __future__ import annotations

import base64
import calendar
import hashlib
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import requests
import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv


DATA_DIR = Path("data")
SUMMARY_CSV = DATA_DIR / "cycling_summary.csv"
ASSETS_DIR = Path("dashboard/assets")
USER_NAME = "Vedant Gaikwad"
USER_LOCATION = "Dublin, County Dublin, Ireland"
DEFAULT_ACCESS_LOG_TABLE = "dashboard_access_logs"
EMAIL_HEADER_CANDIDATES = (
    "cf-access-authenticated-user-email",
    "x-auth-request-email",
    "x-forwarded-email",
)

load_dotenv()


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_request_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    context = getattr(st, "context", None)
    if context is None:
        return headers
    context_headers = getattr(context, "headers", None)
    if context_headers is None:
        return headers
    if hasattr(context_headers, "items"):
        for key, value in context_headers.items():
            headers[str(key).lower()] = str(value)
    return headers


def _extract_authenticated_email(request_headers: dict[str, str]) -> str | None:
    for header_name in EMAIL_HEADER_CANDIDATES:
        value = request_headers.get(header_name)
        if value:
            return value.strip().lower()
    return None


def _ensure_authenticated_access() -> tuple[dict[str, str], str]:
    require_gateway_auth = _to_bool(os.getenv("REQUIRE_GATEWAY_AUTH"), default=False)
    request_headers = _get_request_headers()
    email = _extract_authenticated_email(request_headers)

    if require_gateway_auth and not email:
        st.error("Access denied. Please sign in through the protected dashboard link.")
        st.info("Expected an authenticated email header from your access gateway.")
        st.stop()

    return request_headers, email or "unknown@local"


def _hash_value(raw: str | None) -> str | None:
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _log_access_to_supabase(email: str, request_headers: dict[str, str]) -> None:
    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    supabase_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    table = (os.getenv("ACCESS_LOG_TABLE") or DEFAULT_ACCESS_LOG_TABLE).strip()

    if not supabase_url or not supabase_key:
        return
    if st.session_state.get("_access_log_written"):
        return

    session_id = str(uuid.uuid4())
    st.session_state["_dashboard_session_id"] = session_id
    payload = {
        "email": email,
        "session_id": session_id,
        "ip_hash": _hash_value(request_headers.get("x-forwarded-for")),
        "user_agent": request_headers.get("user-agent"),
        "source": "linkedin",
    }

    rest_base = supabase_url.rstrip("/")
    endpoint = f"{rest_base}/rest/v1/{table}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=8)
        response.raise_for_status()
        st.session_state["_access_log_written"] = True
    except requests.RequestException:
        st.warning("Authenticated access detected, but failed to write Supabase access log.")


def _apply_showcase_sanitization(df: pd.DataFrame, enabled: bool) -> pd.DataFrame:
    if df.empty:
        return df
    sanitized = df.copy()
    if enabled:
        # Strip precise ride times in showcase mode; keep only day-level granularity.
        sanitized["Start_DateTime"] = sanitized["Start_DateTime"].dt.normalize() + pd.Timedelta(hours=12)
        sanitized["Distance_KM"] = sanitized["Distance_KM"].round(1)
        sanitized["Elevation_M"] = sanitized["Elevation_M"].round(0)
        sanitized["Average_Speed_KMH"] = sanitized["Average_Speed_KMH"].round(1)
        sanitized["Moving_Time_Minutes"] = (sanitized["Moving_Time_Minutes"] / 5).round() * 5
    return sanitized


def _image_to_data_uri(image_path: Path) -> str | None:
    if not image_path.exists():
        return None

    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime = mime_map.get(image_path.suffix.lower())
    if mime is None:
        return None

    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def _load_personal_photo_uris(max_photos: int = 3) -> list[str]:
    if not ASSETS_DIR.exists():
        return []

    files = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        files.extend(sorted(ASSETS_DIR.glob(ext)))

    uris = []
    for path in files[:max_photos]:
        data_uri = _image_to_data_uri(path)
        if data_uri:
            uris.append(data_uri)
    return uris


def _inject_theme(photo_uris: list[str]) -> None:
    bg_photo = photo_uris[0] if photo_uris else ""
    st.markdown(
        f"""
        <style>
        :root {{
            --bg: #0f1117;
            --card: #1a1d25;
            --text: #f3f4f6;
            --muted: #9ca3af;
            --accent: #fc4c02;
            --accent-soft: rgba(252,76,2,0.18);
            --ok: #22c55e;
        }}
        .stApp {{
            background:
                linear-gradient(145deg, rgba(10,12,16,.90), rgba(9,10,14,.92)),
                radial-gradient(circle at 20% 0%, #1d2330 0%, #0f1117 55%);
            color: var(--text);
        }}
        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: -1;
            opacity: 0.22;
            background-image: url("{bg_photo}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
        }}
        section[data-testid="stSidebar"] {{ background: #11141b; border-right: 1px solid #242938; }}
        div[data-testid="stMetric"] {{ background: var(--card); border: 1px solid #2a2e39; border-radius: 14px; padding: 10px 14px; }}
        div[data-testid="stMetricValue"] {{ color: var(--accent); font-weight: 700; }}
        div[data-testid="stMetricLabel"] {{ color: #c8ced8; }}
        .card {{
            background: linear-gradient(160deg, rgba(26,29,37,.95), rgba(19,21,29,.95));
            border: 1px solid #2a2e39;
            border-radius: 16px;
            padding: 14px 16px;
            margin-bottom: 12px;
        }}
        .title {{ font-size: 1.6rem; font-weight: 700; letter-spacing: 0.2px; margin-bottom: 2px; }}
        .muted {{ color: var(--muted); font-size: 0.88rem; }}
        .profile-wrap {{ text-align: right; margin-top: 4px; }}
        .profile-name {{ font-size: 1.02rem; font-weight: 700; color: #ffffff; line-height: 1.2; }}
        .profile-location {{ font-size: 0.84rem; color: #c9cfdb; line-height: 1.2; }}
        .section-title {{ font-size: 1.35rem; font-weight: 700; margin: 6px 0 8px 0; }}
        .photo-strip {{
            display: grid;
            grid-template-columns: 1.35fr 1fr 1fr;
            gap: 12px;
            margin: 16px 0 12px 0;
        }}
        .photo-tile {{
            border-radius: 16px;
            min-height: 170px;
            border: 1px solid rgba(255,255,255,.12);
            box-shadow: 0 14px 30px rgba(0,0,0,.32);
            background-size: cover;
            background-position: center;
            position: relative;
            overflow: hidden;
        }}
        .photo-tile::after {{
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, rgba(4,5,7,.44), rgba(4,5,7,.08));
        }}
        .pill {{
            display: inline-block;
            border: 1px solid rgba(252,76,2,.5);
            background: var(--accent-soft);
            color: #ffd4c2;
            border-radius: 999px;
            padding: 2px 10px;
            font-size: .82rem;
            margin-right: 6px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=45, show_spinner=False)
def _load_data() -> pd.DataFrame:
    if not SUMMARY_CSV.exists():
        return pd.DataFrame()

    summary = pd.read_csv(SUMMARY_CSV)
    summary["Date"] = pd.to_datetime(summary["Date"], errors="coerce")
    if "Start_Date_Local" in summary.columns:
        summary["Start_DateTime"] = pd.to_datetime(summary["Start_Date_Local"], errors="coerce")
    else:
        summary["Start_DateTime"] = pd.to_datetime(summary["Date"], errors="coerce")
    summary["Start_DateTime"] = summary["Start_DateTime"].fillna(summary["Date"])
    summary["Distance_KM"] = pd.to_numeric(summary["Distance_KM"], errors="coerce").fillna(0.0)
    summary["Elevation_M"] = pd.to_numeric(summary["Elevation_M"], errors="coerce").fillna(0.0)
    summary["Moving_Time_Minutes"] = pd.to_numeric(
        summary["Moving_Time_Minutes"], errors="coerce"
    ).fillna(0.0)
    summary["Average_Speed_KMH"] = pd.to_numeric(
        summary["Average_Speed_KMH"], errors="coerce"
    ).fillna(0.0)

    return summary.dropna(subset=["Date"])


def _compute_streak(dates: pd.Series) -> int:
    if dates.empty:
        return 0
    day_set = {d.date() for d in dates.dt.normalize()}
    streak = 0
    cursor = datetime.now().date()
    while cursor in day_set:
        streak += 1
        cursor -= timedelta(days=1)
    if streak == 0 and (datetime.now().date() - timedelta(days=1)) in day_set:
        # If no ride today but rode yesterday, treat as active streak carry.
        cursor = datetime.now().date() - timedelta(days=1)
        while cursor in day_set:
            streak += 1
            cursor -= timedelta(days=1)
    return streak


def _render_calendar(month_df: pd.DataFrame) -> pd.DataFrame:
    if month_df.empty:
        return pd.DataFrame(columns=["date", "activities"])
    cal = (
        month_df.assign(day=month_df["Date"].dt.date)
        .groupby("day")
        .size()
        .reset_index(name="activities")
        .rename(columns={"day": "date"})
    )
    cal["date"] = pd.to_datetime(cal["date"])
    return cal


def _datetime_dropdown(
    label: str,
    default_dt: datetime,
    min_dt: datetime,
    max_dt: datetime,
    key_prefix: str,
) -> datetime:
    st.markdown(f"**{label}**")
    years = list(range(min_dt.year, max_dt.year + 1))
    year_labels = [f"{y}" for y in years]
    year_label = st.selectbox("Year", year_labels, index=years.index(default_dt.year), key=f"{key_prefix}_year")
    year = int(year_label)
    month_names = list(calendar.month_name)[1:]
    month_name = st.selectbox("Month", month_names, index=default_dt.month - 1, key=f"{key_prefix}_month")
    month = month_names.index(month_name) + 1
    max_day = calendar.monthrange(year, month)[1]
    days = list(range(1, max_day + 1))
    default_day = min(default_dt.day, max_day)
    day_labels = [f"{d:02d}" for d in days]
    day_label = st.selectbox("Date", day_labels, index=days.index(default_day), key=f"{key_prefix}_day")
    day = int(day_label)
    hours = list(range(0, 24))
    hour_labels = [f"{h:02d}" for h in hours]
    hour_label = st.selectbox("Hour", hour_labels, index=hours.index(default_dt.hour), key=f"{key_prefix}_hour")
    hour = int(hour_label)
    minutes = [0, 15, 30, 45]
    nearest_min = min(minutes, key=lambda x: abs(x - default_dt.minute))
    minute_labels = [f"{m:02d}" for m in minutes]
    minute_label = st.selectbox("Minute", minute_labels, index=minutes.index(nearest_min), key=f"{key_prefix}_minute")
    minute = int(minute_label)

    selected = datetime(year, month, day, hour, minute)
    if selected < min_dt:
        selected = min_dt
    if selected > max_dt:
        selected = max_dt
    return selected


def main() -> None:
    st.set_page_config(page_title="Strava Cycling Dashboard", layout="wide")
    showcase_mode = _to_bool(os.getenv("SHOWCASE_MODE"), default=True)
    request_headers, user_email = _ensure_authenticated_access()
    _log_access_to_supabase(user_email, request_headers)

    photo_uris = _load_personal_photo_uris(max_photos=3)
    _inject_theme(photo_uris)

    summary = _load_data()
    summary = _apply_showcase_sanitization(summary, enabled=showcase_mode)

    header_left, header_right = st.columns([3.2, 1.6])
    with header_left:
        st.markdown('<div class="title">Personalized Strava Cycling Dashboard</div>', unsafe_allow_html=True)
    with header_right:
        st.markdown(
            f'<div class="profile-wrap"><div class="profile-name">{USER_NAME}</div>'
            f'<div class="profile-location">{USER_LOCATION}</div></div>',
            unsafe_allow_html=True,
        )

    last_update = datetime.fromtimestamp(SUMMARY_CSV.stat().st_mtime) if SUMMARY_CSV.exists() else None
    freshness = "No data yet"
    if last_update:
        freshness = f"Last ETL update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}"
    st.markdown(
        f'<span class="pill">Daily ETL Update Mode</span>'
        f'<span class="pill">{freshness}</span>'
        f'<span class="pill">Access: {("Gateway Auth" if user_email != "unknown@local" else "Open")}</span>'
        f'<span class="pill">Mode: {"Showcase" if showcase_mode else "Private"}</span>',
        unsafe_allow_html=True,
    )
    if photo_uris:
        # Repeat last image if fewer than 3 are available so layout stays balanced.
        tiles = photo_uris + ([photo_uris[-1]] * (3 - len(photo_uris)))
        st.markdown(
            "<div class='photo-strip'>"
            f"<div class='photo-tile' style=\"background-image:url('{tiles[0]}')\"></div>"
            f"<div class='photo-tile' style=\"background-image:url('{tiles[1]}')\"></div>"
            f"<div class='photo-tile' style=\"background-image:url('{tiles[2]}')\"></div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Add your cycling photos to `dashboard/assets/` as `.jpg/.jpeg/.png/.webp` for personalized backgrounds.")

    if summary.empty:
        st.warning("No summary data found. Run `python main.py --force` first.")
        st.stop()

    min_dt = summary["Start_DateTime"].min().to_pydatetime()
    max_dt = summary["Start_DateTime"].max().to_pydatetime()
    default_start_dt = max(min_dt, max_dt - timedelta(days=90))

    with st.sidebar:
        st.header("Filters")
        start_dt = _datetime_dropdown(
            "Start Date/Time",
            default_dt=default_start_dt,
            min_dt=min_dt,
            max_dt=max_dt,
            key_prefix="start",
        )
        end_dt = _datetime_dropdown(
            "End Date/Time",
            default_dt=max_dt,
            min_dt=min_dt,
            max_dt=max_dt,
            key_prefix="end",
        )
        st.caption(f"From: {start_dt.strftime('%B %d, %Y %H:%M')}")
        st.caption(f"To: {end_dt.strftime('%B %d, %Y %H:%M')}")
        activity_types = sorted(summary["Activity_Type"].dropna().astype(str).unique().tolist())
        selected_types = st.multiselect("Activity type", options=activity_types, default=activity_types)
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    filtered = summary[
        (summary["Start_DateTime"] >= start_dt)
        & (summary["Start_DateTime"] <= end_dt)
        & (summary["Activity_Type"].isin(selected_types))
    ].copy()

    if filtered.empty:
        st.info("No activities match current filters.")
        st.stop()

    # Journey-level KPIs (independent of sidebar filters)
    all_time_distance = summary["Distance_KM"].sum()
    all_time_rides = int(summary["Activity_ID"].count())
    all_time_hours = summary["Moving_Time_Minutes"].sum() / 60.0

    month_options = sorted(summary["Date"].dt.to_period("M").dropna().unique().tolist())
    month_display_labels = [m.strftime("%B %Y") for m in month_options]
    month_display_map = {label: period for label, period in zip(month_display_labels, month_options)}
    latest_month_label = month_display_labels[-1] if month_display_labels else datetime.now().strftime("%B %Y")

    st.markdown('<div class="section-title">All-Time Journey KPIs</div>', unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    k1.metric("Total Distance (km)", f"{all_time_distance:.1f}")
    k2.metric("Total Rides", f"{all_time_rides}")
    k3.metric("Total Time (hrs)", f"{all_time_hours:.1f}")

    st.markdown('<div class="section-title">Monthly Journey KPIs</div>', unsafe_allow_html=True)
    selected_month_label = st.selectbox(
        "Select month",
        options=month_display_labels if month_display_labels else [latest_month_label],
        index=(len(month_display_labels) - 1) if month_display_labels else 0,
    )
    selected_month = month_display_map.get(selected_month_label, pd.Period(datetime.now(), freq="M"))
    monthly_base = summary[summary["Date"].dt.to_period("M") == selected_month]
    monthly_distance = monthly_base["Distance_KM"].sum()
    monthly_rides = int(monthly_base["Activity_ID"].count())
    monthly_hours = monthly_base["Moving_Time_Minutes"].sum() / 60.0

    m1, m2, m3 = st.columns(3)
    m1.metric("Monthly Distance (km)", f"{monthly_distance:.1f}")
    m2.metric("Monthly Rides", f"{monthly_rides}")
    m3.metric("Monthly Time (hrs)", f"{monthly_hours:.1f}")

    st.markdown('<div class="section-title">Filtered View KPIs</div>', unsafe_allow_html=True)
    total_distance = filtered["Distance_KM"].sum()
    total_elevation = filtered["Elevation_M"].sum()
    total_hours = filtered["Moving_Time_Minutes"].sum() / 60.0
    ride_days = filtered["Date"].dt.date.nunique()
    streak_days = _compute_streak(summary["Date"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Distance (km)", f"{total_distance:.1f}")
    c2.metric("Elevation (m)", f"{total_elevation:.0f}")
    c3.metric("Ride Time (hrs)", f"{total_hours:.1f}")
    c4.metric("Ride Days", f"{ride_days}")
    c5.metric("Current Streak (days)", f"{streak_days}")

    col_left, col_right = st.columns([1.8, 1.2])
    with col_left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Distance Trend")
        daily = (
            filtered.assign(day=filtered["Date"].dt.date)
            .groupby("day", as_index=False)["Distance_KM"]
            .sum()
            .rename(columns={"day": "Date"})
        )
        st.line_chart(daily.set_index("Date")["Distance_KM"], color="#fc4c02")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("This Month Activity Calendar")
        now = datetime.now()
        month_df = summary[(summary["Date"].dt.year == now.year) & (summary["Date"].dt.month == now.month)]
        cal = _render_calendar(month_df)
        if cal.empty:
            st.caption("No activities this month yet.")
        else:
            cal = cal.set_index("date").resample("D").sum().fillna(0)
            st.bar_chart(cal["activities"], color="#fc4c02")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader(f"Monthly Recap - {selected_month.strftime('%B %Y')}")
    monthly_days = int(monthly_base["Date"].dt.date.nunique()) if not monthly_base.empty else 0
    monthly_elev = float(monthly_base["Elevation_M"].sum()) if not monthly_base.empty else 0.0

    recap_left, recap_right = st.columns([1.1, 2.0])
    with recap_left:
        st.metric("Days", f"{monthly_days}")
        st.metric("Hrs", f"{monthly_hours:.1f}")
        st.metric("KM", f"{monthly_distance:.1f}")
        st.metric("M", f"{monthly_elev:.0f}")

    with recap_right:
        if monthly_base.empty:
            st.caption("No activities in selected month.")
        else:
            month_start = selected_month.to_timestamp()
            month_end = month_start + pd.offsets.MonthEnd(0)

            # Calendar window aligned Sunday->Saturday and covering the whole month.
            start_offset = (month_start.weekday() + 1) % 7  # Monday=0 -> Sunday offset.
            calendar_start = month_start - pd.Timedelta(days=start_offset)
            end_offset = (5 - month_end.weekday()) % 7  # Monday=0 -> Saturday end.
            calendar_end = month_end + pd.Timedelta(days=end_offset)

            recap_days = pd.DataFrame({"Date": pd.date_range(calendar_start, calendar_end, freq="D")})
            recap_days["day_num"] = recap_days["Date"].dt.day
            recap_days["in_month"] = (recap_days["Date"] >= month_start) & (recap_days["Date"] <= month_end)
            recap_days["weekday"] = (recap_days["Date"].dt.weekday + 1) % 7  # Sunday=0 ... Saturday=6
            recap_days["weekday_label"] = recap_days["weekday"].map(
                {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
            )
            recap_days["week"] = ((recap_days["Date"] - calendar_start).dt.days // 7) + 1
            recap_days["day_label"] = recap_days.apply(
                lambda row: str(int(row["day_num"])) if row["in_month"] else "",
                axis=1,
            )

            rides_by_day = (
                monthly_base.assign(day_only=monthly_base["Date"].dt.normalize())
                .groupby("day_only", as_index=False)
                .size()
                .rename(columns={"day_only": "Date", "size": "rides"})
            )
            recap_days = recap_days.merge(rides_by_day, on="Date", how="left")
            recap_days["rides"] = recap_days["rides"].fillna(0).astype(int)
            recap_days["has_ride"] = recap_days["rides"] > 0

            base = alt.Chart(recap_days).encode(
                x=alt.X(
                    "weekday_label:N",
                    sort=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                    axis=alt.Axis(
                        title=None,
                        labelColor="#111111",
                        labelFontSize=14,
                        labelPadding=10,
                        labelAngle=0,
                    ),
                ),
                y=alt.Y(
                    "week:O",
                    sort=list(range(1, int(recap_days["week"].max()) + 1)),
                    axis=None,
                ),
                tooltip=[
                    alt.Tooltip("Date:T", title="Date", format="%B %d, %Y"),
                    alt.Tooltip("rides:Q", title="Rides"),
                ],
            )

            tiles = base.mark_rect(stroke="#b8b8b8", strokeWidth=1.6).encode(
                color=alt.condition(
                    alt.datum.in_month,
                    alt.value("#ffffff"),
                    alt.value("#f0f0f0"),
                )
            )
            labels = base.mark_text(fontSize=20, fontWeight="normal").encode(
                text=alt.Text("day_label:N"),
                color=alt.condition(
                    alt.datum.has_ride,
                    alt.value("#fc4c02"),
                    alt.value("#111111"),
                ),
            )

            calendar_chart = (
                (tiles + labels)
                .properties(height=320)
                .configure_view(stroke="#b8b8b8", strokeWidth=1.6, fill="#ffffff")
            )
            st.altair_chart(calendar_chart, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Top Efforts")
    top_efforts = (
        filtered.assign(month=filtered["Date"].dt.to_period("M").dt.to_timestamp())
        .groupby("month", as_index=False)
        .agg(
            Distance_KM=("Distance_KM", "sum"),
            Average_KMH=("Average_Speed_KMH", "mean"),
        )
        .sort_values("Distance_KM", ascending=False)
        .head(8)
        .rename(columns={"month": "Month"})
    )
    if top_efforts.empty:
        st.caption("No efforts available for current filters.")
    else:
        top_efforts["Month"] = pd.to_datetime(top_efforts["Month"]).dt.strftime("%B %Y")
        top_efforts["Distance_KM"] = top_efforts["Distance_KM"].round(1)
        top_efforts["Average_KMH"] = top_efforts["Average_KMH"].round(1)
        chart = (
            alt.Chart(top_efforts)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#fc4c02")
            .encode(
                x=alt.X(
                    "Month:N",
                    sort=None,
                    axis=alt.Axis(labelAngle=0, labelColor="#d6dbe6", title="Month", titleColor="#d6dbe6"),
                ),
                y=alt.Y("Distance_KM:Q", title="Distance (km)", axis=alt.Axis(labelColor="#d6dbe6", titleColor="#d6dbe6")),
                tooltip=[
                    alt.Tooltip("Month:N", title="Month"),
                    alt.Tooltip("Distance_KM:Q", title="Distance (km)", format=".1f"),
                    alt.Tooltip("Average_KMH:Q", title="Average KM/H", format=".1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
        st.dataframe(
            top_efforts.rename(
                columns={
                    "Distance_KM": "Distance (km)",
                    "Average_KMH": "Average KM/H",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
