#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.core.ContextManager import ContextManager
from archive_agent.util.text_util import replace_file_uris_with_markdown
from archive_agent.util.json_util import generate_json_filename, write_to_json

from archive_agent import __version__

import streamlit as st
from streamlit.components.v1 import html as st_html

import logging
import asyncio
import sys
import json
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GuiManager:
    """
    GUI manager.
    """

    def __init__(self) -> None:
        """
        Initialize GUI manager. Ensures ContextManager is created only once.
        """
        st.set_page_config(page_title="Archive Agent", page_icon="⚡", layout="centered")

        # Build ContextManager once and cache in session_state
        if "context" not in st.session_state:
            st.session_state.context = ContextManager(
                invalidate_cache=st.session_state.get("is_nocache", False),
                verbose=st.session_state.get("is_verbose", False),
                to_json_auto_dir=st.session_state.get("_to_json_auto_dir", None),
            )

        self.context: ContextManager = st.session_state.context

    def run(self) -> None:
        """
        Run GUI.
        """
        self._render_layout()

    @staticmethod
    def postprocess_answer_text(text: str) -> str:
        """
        Postprocess answer text: Make file URIs clickable Markdown links.
        :param text: Text.
        :return: Text.
        """
        return replace_file_uris_with_markdown(text)

    def get_answer(self, question: str) -> str:
        """
        Get answer to question.
        :param question: Question.
        :return: Answer.
        """
        query_result, answer_text = asyncio.run(self.context.qdrant.query(question))

        if query_result.is_rejected:
            return f"**Query rejected:** {query_result.rejection_reason}"
        else:
            if self.context.to_json_auto_dir:
                json_filename = self.context.to_json_auto_dir / generate_json_filename(
                    question
                )
                if json_filename:
                    write_to_json(
                        json_filename=json_filename,
                        question=question,
                        query_result=query_result.model_dump(),
                        answer_text=answer_text,
                    )
            return self.postprocess_answer_text(answer_text)

    def _render_layout(self) -> None:
        """
        Render GUI with centered image and search form.
        """
        stats = asyncio.run(self.context.qdrant.get_stats())
        files_count = stats["files_count"]
        chunks_count = stats["chunks_count"]

        image_path = Path(__file__).parent.parent / "assets" / "Archive-Agent-800x300.png"

        cols = st.columns(3)

        with cols[0]:
            file_s = "" if files_count == 1 else "s"
            chunk_s = "" if chunks_count == 1 else "s"
            st.markdown(
                f"<small><b>{self.context.profile_manager.get_profile_name()}</b></small>  \n"
                f"<small>({files_count}) file{file_s}</small>  \n"
                f"<small>({chunks_count}) chunk{chunk_s}</small>  \n",
                unsafe_allow_html=True,
            )

        with cols[1]:
            st.markdown(
                f"<small><i>Archive Agent v{__version__}</i></small>  \n"
                f"<small>[Qdrant dashboard]({self.context.config.data[self.context.config.QDRANT_SERVER_URL]}/dashboard)</small>",
                unsafe_allow_html=True,
            )

        with cols[2]:
            st.image(image_path, width=400)

        # Session state: only need to track the last answer
        if "last_answer" not in st.session_state:
            st.session_state.last_answer = None

        # Search form - handles Enter key natively, clears input on submit
        with st.form("search_form", clear_on_submit=True):
            search_col, button_col = st.columns([5, 1])
            with search_col:
                query = st.text_input(
                    "Ask something…",
                    label_visibility="collapsed",
                    placeholder="Ask something…",
                )
            with button_col:
                submitted = st.form_submit_button("⚡", use_container_width=True)

        # Process query on submit
        if submitted and query and query.strip():
            with st.spinner("Thinking..."):
                try:
                    st.session_state.last_answer = self.get_answer(query.strip())
                except Exception as e:
                    st.session_state.last_answer = f"**Error:** {e}"

        # Display last answer
        if st.session_state.last_answer:
            self.display_answer(st.session_state.last_answer)

    @staticmethod
    def display_answer(answer: str) -> None:
        """
        Displays answer with a copy button above.
        :param answer: Answer.
        """
        st.markdown(answer)
        GuiManager._render_copy_button(answer, "Copy")

    @staticmethod
    def _render_copy_button(text: str, label: str = "Copy") -> None:
        """
        Render a copy button that uses document.execCommand('copy') only.
        This works over HTTP/IP without requiring the Clipboard API/HTTPS.
        Styled to match Streamlit's native button appearance.
        :param text: Text to copy.
        :param label: Button label.
        """
        btn_id = f"copy_btn_{uuid.uuid4().hex}"
        payload = json.dumps({"text": text, "label": label})
        st_html(
            f"""
                <div class="copy-wrap">
                    <style>
                        .copy-wrap {{ display: inline-block; }}
                        .copy-wrap button {{
                            -webkit-appearance: none;
                            appearance: none;
                            background-color: rgb(255, 255, 255);
                            color: rgb(38, 39, 48);
                            border: 1px solid rgba(49, 51, 63, 0.2);
                            border-radius: 4px;
                            padding: 5px 16px;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                            font-size: 14px;
                            font-weight: 500;
                            line-height: 20px;
                            text-align: center;
                            cursor: pointer;
                            transition: all 0.2s ease;
                            white-space: nowrap;
                        }}
                        .copy-wrap button:hover {{
                            background-color: rgb(246, 247, 249);
                            border-color: rgba(49, 51, 63, 0.1);
                        }}
                        .copy-wrap button:active {{
                            background-color: rgb(230, 234, 241);
                            border-color: rgba(49, 51, 63, 0.2);
                        }}
                        .copy-wrap button:focus {{
                            box-shadow: rgba(0, 89, 220, 0.2) 0px 0px 0px 3px;
                            outline: none;
                        }}
                    </style>
                    <button type="button" id="{btn_id}" aria-label="{label}">{label}</button>
                </div>
                <script>
                    (function() {{
                        const data = {payload};
                        const btn = document.getElementById('{btn_id}');
                        btn.addEventListener('click', function(e) {{
                            e.preventDefault();
                            e.stopPropagation();
                            try {{
                                const ta = document.createElement('textarea');
                                ta.value = data.text;
                                ta.setAttribute('readonly', '');
                                ta.style.position = 'fixed';
                                ta.style.top = '-1000px';
                                ta.style.left = '-1000px';
                                ta.style.opacity = '0';
                                document.body.appendChild(ta);
                                ta.focus();
                                ta.select();
                                ta.setSelectionRange(0, ta.value.length);
                                const ok = document.execCommand('copy');
                                document.body.removeChild(ta);
                                if (ok) {{
                                    btn.textContent = 'Copied ✓';
                                    setTimeout(function() {{ btn.textContent = data.label; }}, 1500);
                                }} else {{
                                    btn.textContent = 'Copy failed';
                                    setTimeout(function() {{ btn.textContent = data.label; }}, 1500);
                                    window.alert('Copy failed. Please copy manually.');
                                }}
                            }} catch (err) {{
                                btn.textContent = 'Copy failed';
                                setTimeout(function() {{ btn.textContent = data.label; }}, 1500);
                                window.alert('Copy failed. Please copy manually.');
                            }}
                            return false;
                        }});
                    }})();
                </script>
            """,
            height=40,
        )


if __name__ == "__main__":
    # Parse CLI args only once and stash in session_state
    if "cli_parsed" not in st.session_state:
        is_nocache: bool = False
        is_verbose: bool = False
        _to_json_auto_dir: Optional[Path] = None

        args = sys.argv[1:]
        while args:
            arg = args.pop(0)
            if arg == "--nocache":
                is_nocache = True
            elif arg == "--verbose":
                is_verbose = True
            elif arg == "--to-json-auto":
                assert args, "Expected path after --to-json-auto"
                _to_json_auto_dir = Path(args.pop(0)).expanduser().resolve()

        st.session_state.is_nocache = is_nocache
        st.session_state.is_verbose = is_verbose
        st.session_state._to_json_auto_dir = _to_json_auto_dir
        st.session_state.cli_parsed = True

        logger.info("Press CTRL+C to stop the GUI server.")

    gui = GuiManager()
    gui.run()
