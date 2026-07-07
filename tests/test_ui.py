from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parent.parent / "know_it_all_friend" / "ui" / "app.py"


def test_ui_script_runs_without_exception() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)

    at.run()

    assert not at.exception
    assert at.title[0].value == "📚 Know-it-all Friend"
