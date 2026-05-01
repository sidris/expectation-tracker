import streamlit as st
import plotly.graph_objects as go

PALETTE = ["#8B5CF6", "#EC4899", "#3B82F6", "#F59E0B", "#10B981", "#EF4444", "#06B6D4"]


def inject_theme():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .stApp { background: #fbfbfe; }
        section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #f0edf8; }
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #f0edf8;
            border-radius: 18px;
            padding: 18px 18px;
            box-shadow: 0 10px 35px rgba(31, 41, 55, 0.04);
        }
        div[data-testid="stMetricLabel"] { color: #8a8a9f; font-weight: 600; }
        div[data-testid="stMetricValue"] { color: #242436; font-weight: 800; }
        .soft-card {
            background: #ffffff;
            border: 1px solid #f0edf8;
            border-radius: 22px;
            padding: 20px;
            box-shadow: 0 18px 50px rgba(31, 41, 55, 0.055);
            margin-bottom: 18px;
        }
        .hero {
            background: linear-gradient(135deg, #ffffff 0%, #f4edff 100%);
            border: 1px solid #eee5ff;
            border-radius: 26px;
            padding: 26px 30px;
            box-shadow: 0 18px 60px rgba(139, 92, 246, 0.10);
            margin-bottom: 20px;
        }
        .hero h1 { margin: 0; color: #242436; font-size: 34px; }
        .hero p { color: #74748a; margin-top: 8px; }
        .medal-card {
            background: #ffffff;
            border: 1px solid #f0edf8;
            border-radius: 22px;
            padding: 22px;
            text-align: center;
            box-shadow: 0 16px 42px rgba(31, 41, 55, 0.05);
        }
        .medal-card .medal { font-size: 38px; }
        .medal-card .name { font-size: 18px; font-weight: 800; margin-top: 10px; color: #242436; }
        .medal-card .score { color: #8a8a9f; font-weight: 600; margin-top: 6px; }
        .stButton button, .stDownloadButton button {
            border-radius: 14px;
            border: 0;
            background: linear-gradient(135deg, #8B5CF6, #A855F7);
            color: white;
            font-weight: 700;
            box-shadow: 0 10px 25px rgba(139, 92, 246, 0.22);
        }
        .stDataFrame { border-radius: 18px; overflow: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def plot_layout(fig: go.Figure, height: int = 420):
    fig.update_layout(
        height=height,
        template="plotly_white",
        margin=dict(l=10, r=10, t=28, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#525266"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#f2effa", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#f2effa", zeroline=False)
    return fig


def styled_line(df, x, y, color=None, title=None, markers=True, fill=False):
    fig = go.Figure()
    if color and color in df.columns:
        for i, (name, g) in enumerate(df.groupby(color)):
            c = PALETTE[i % len(PALETTE)]
            fig.add_trace(go.Scatter(
                x=g[x], y=g[y], mode="lines+markers" if markers else "lines", name=str(name),
                line=dict(width=3, color=c, shape="spline"),
                marker=dict(size=7, color=c),
                fill="tozeroy" if fill and i == 0 else None,
                fillcolor="rgba(139, 92, 246, 0.13)" if fill and i == 0 else None,
            ))
    else:
        fig.add_trace(go.Scatter(
            x=df[x], y=df[y], mode="lines+markers" if markers else "lines", name=title or y,
            line=dict(width=3, color=PALETTE[0], shape="spline"), marker=dict(size=7, color=PALETTE[0]),
            fill="tozeroy" if fill else None, fillcolor="rgba(139, 92, 246, 0.14)" if fill else None,
        ))
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=18, color="#242436")))
    return plot_layout(fig)
