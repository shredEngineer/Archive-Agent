#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from pathlib import Path

import streamlit as st

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

    def _render_layout(self) -> None:
        """
        Render GUI.
        """
        col1, col2 = st.columns([1, 5])

        with col1:
            image_path = Path(__file__).parent.parent / "assets" / "Archive-Agent-400x300.png"
            st.image(image_path, width=200)

        with col2:
            query: str = st.text_input(
                "Ask a question",
                label_visibility="collapsed",
                placeholder="Ask something..."
            )

        if query:
            with st.spinner("Thinking..."):
                result_md: str = self.get_answer(query)
            self.display_answer(result_md)

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

    @staticmethod
    def display_answer(answer: str) -> None:
        """
        Displays answer.
        :param answer: Answer.
        """
        st.markdown(answer, unsafe_allow_html=True)


if __name__ == '__main__':
    gui = GuiManager()
    gui.run()
