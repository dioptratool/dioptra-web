import re

from django.utils.html import escapejs

from ombucore.admin.panel_commands import Redirect, Resolve


def _extract_payload_script_id(rendered):
    match = re.search(
        r'<script id="(?P<script_id>panel-command-payload-[a-f0-9]+)" type="application/json">', rendered
    )
    assert match
    return match.group("script_id")


class TestPanelCommands:
    def test_payload_is_rendered_as_inert_json_script_data(self):
        payload = {
            "operation": "selected",
            "info": {
                "title": "</script><script>alert(81)</script>&",
            },
        }

        rendered = Resolve(payload).render()
        payload_script_id = _extract_payload_script_id(rendered)

        assert f'document.getElementById("{escapejs(payload_script_id)}")' in rendered
        assert 'const panelMethod = "resolve";' in rendered
        assert "Panels.current[panelMethod](payload);" in rendered
        assert "\\u003C/script\\u003E\\u003Cscript\\u003Ealert(81)\\u003C/script\\u003E\\u0026" in rendered
        assert "</script><script>alert(81)" not in rendered.lower()
        assert rendered.lower().count("</script>") == 2

    def test_each_panel_command_payload_script_id_is_unique(self):
        first_id = _extract_payload_script_id(Resolve({"operation": "first"}).render())
        second_id = _extract_payload_script_id(Resolve({"operation": "second"}).render())

        assert first_id != second_id

    def test_redirect_payload_is_escaped_for_javascript_string_context(self):
        rendered = Redirect('"/><script>alert(1)</script>').render()

        assert "<script>alert(1)" not in rendered.lower()
        assert "\\u003cscript\\u003ealert(1)" in rendered.lower()
        assert rendered.lower().count("</script>") == 1
