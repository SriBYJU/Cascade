from engine.tutorial import render_tutorial


def test_tutorial_covers_safe_end_to_end_flow():
    text = render_tutorial()
    assert "optimizer doctor" in text
    assert "optimizer project-install" in text
    assert "optimizer plan" in text
    assert "optimizer run" in text
    assert "optimizer trace" in text
    assert "optimizer stats" in text
    assert "--apply" in text
    assert "optimizer savings" in text
    assert "optimizer project-uninstall" in text
