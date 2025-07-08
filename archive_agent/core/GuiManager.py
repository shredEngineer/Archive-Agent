#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from pathlib import Path

import streamlit as st

from st_copy_to_clipboard import st_copy_to_clipboard

from archive_agent.core.ContextManager import ContextManager
from archive_agent.util.text_util import replace_file_uris_with_markdown


logger = logging.getLogger(__name__)


class GuiManager:
    """
    GUI manager.
    """

    def __init__(self) -> None:
        """
        Initialize GUI manager.
        """
        st.set_page_config(page_title="Archive Agent", layout="centered")

        self.context = ContextManager()

    def run(self) -> None:
        """
        Run GUI.
        """
        logger.info("Press CTRL+C to stop the GUI server.")
        self._render_layout()

    @staticmethod
    def format_chunk_refs(text: str) -> str:
        """
        Format chunk reference designators in the text.
        :param text: Text.
        :return: Text.
        """
        return replace_file_uris_with_markdown(text.replace("<<< ", "").replace(" >>>", ""))

    def get_answer(self, question: str) -> str:
        """
        Get answer to question.
        :param question: Question.
        :return: Answer.
        """
        query_result, answer_text = self.context.qdrant.query(question)
        if query_result.reject:
            return f"**Query rejected:** {query_result.rejection_reason}"
        else:
            return self.format_chunk_refs(answer_text)

    def _render_layout(self) -> None:
        """
        Render GUI with centered image and search form.
        """
        image_path = Path(__file__).parent.parent / "assets" / "Archive-Agent-800x300.png"

        cols = st.columns(3)
        with cols[0]:
            # TODO: Implement files and chunks count.
            # files_count = "NaN"
            # chunks_count = "NaN"
            # st.markdown(f"📄 {files_count} files")
            # st.markdown(f"🧩 {chunks_count} chunks")
            pass
        with cols[2]:
            st.image(image_path, width=400)

        # The search bar and button in a form, side by side
        with st.form("search_form"):
            search_col, button_col = st.columns([5, 1])
            with search_col:
                query = st.text_input(
                    "Ask a question",
                    label_visibility="collapsed",
                    placeholder="Ask something..."
                )
            with button_col:
                submitted = st.form_submit_button("⚡", use_container_width=True)

        if submitted and query:
            with st.spinner("Thinking..."):
                result_md: str = self.get_answer(query)
            self.display_answer(result_md)

    @staticmethod
    def display_answer(answer: str) -> None:
        """
        Displays answer with a copy button above.
        :param answer: Answer.
        """
        st.markdown(answer, unsafe_allow_html=True)
        st_copy_to_clipboard(answer, "Copy")


if __name__ == '__main__':
    gui = GuiManager()
    gui.run()
