"""Project contributors shown in the app (GitHub avatars + links)."""

from __future__ import annotations

import html

import streamlit as st

# Keep in sync with CONTRIBUTORS.md at repo root.
APP_CONTRIBUTORS: tuple[dict[str, str], ...] = (
    {"name": "Noor ul huda", "github": "Reveuse1234"},
    {"name": "misbhahaha", "github": "misbhahaha"},
)

_CONTRIBUTORS_CSS = """
.pf-contributors-badge {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    margin-top: 1.25rem;
}
.pf-contributors-badge--fixed {
    position: fixed;
    left: 1rem;
    bottom: 3.75rem;
    z-index: 999;
    margin: 0;
    padding: 0.35rem 0.55rem 0.35rem 0.35rem;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid #e2e8f0;
    border-radius: 999px;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}
.pf-contributors-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: #64748b;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    white-space: nowrap;
}
.pf-contributors-avatars {
    display: flex;
    align-items: center;
}
.pf-contributors-avatars a {
    display: block;
    margin-left: -0.35rem;
    line-height: 0;
}
.pf-contributors-avatars a:first-child {
    margin-left: 0;
}
.pf-contributors-avatars img {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: 2px solid #fff;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12);
    transition: transform 0.15s ease;
}
.pf-contributors-avatars a:hover img {
    transform: scale(1.06);
}
.pf-sidebar-contributors {
    margin-top: 1.5rem;
    padding-top: 0.75rem;
    border-top: 1px solid #e2e8f0;
}
.pf-sidebar-contributors .pf-contributors-badge {
    margin-top: 0.35rem;
}
@media (max-width: 640px) {
    .pf-contributors-badge--fixed {
        left: 0.65rem;
        bottom: 3.5rem;
    }
}
"""


def _inject_contributors_css() -> None:
    if st.session_state.get("_pf_contributors_css"):
        return
    st.markdown(f"<style>{_CONTRIBUTORS_CSS}</style>", unsafe_allow_html=True)
    st.session_state["_pf_contributors_css"] = True


def render_contributors_badge(*, fixed: bool = False, compact: bool = False) -> None:
    """Show GitHub avatars for project contributors."""
    _inject_contributors_css()
    avatars = []
    for person in APP_CONTRIBUTORS:
        login = person["github"]
        name = html.escape(person.get("name") or login)
        avatars.append(
            f'<a href="https://github.com/{html.escape(login)}" target="_blank" rel="noopener" '
            f'title="{name} (@{html.escape(login)})">'
            f'<img src="https://github.com/{html.escape(login)}.png?size=64" alt="{name}" loading="lazy">'
            f"</a>"
        )
    fixed_cls = " pf-contributors-badge--fixed" if fixed else ""
    label = "" if compact else '<span class="pf-contributors-label">Contributors</span>'
    st.markdown(
        f'<div class="pf-contributors-badge{fixed_cls}">'
        f"{label}"
        f'<div class="pf-contributors-avatars">{"".join(avatars)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_sidebar_contributors() -> None:
    """Contributors row at the bottom of the sidebar."""
    st.markdown('<div class="pf-sidebar-contributors">', unsafe_allow_html=True)
    st.caption("Contributors")
    render_contributors_badge(compact=True)
    st.markdown("</div>", unsafe_allow_html=True)
