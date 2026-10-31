"""The desktop's title bar colours, from a Metacity/Marco window theme (#122)."""

from helper.platform.linux_x11.desktop import title_colours_from

THEME = """<metacity_theme>
  <draw_ops name="bar_focused">
    <rectangle color="#0055AA" filled="true" x="0" y="0" width="width" height="height"/>
  </draw_ops>
  <draw_ops name="bar_unfocused">
    <rectangle color="#888888" filled="true" x="0" y="0" width="width" height="height"/>
  </draw_ops>
  <draw_ops name="text_focused"><title color="{text}" x="0" y="0"/></draw_ops>
  <frame_style name="focused" geometry="normal">
    <piece position="titlebar" draw_ops="bar_focused"/>
    <piece position="title" draw_ops="text_focused"/>
  </frame_style>
  <frame_style name="unfocused" geometry="normal">
    <piece position="titlebar" draw_ops="bar_unfocused"/>
  </frame_style>
  <frame_style_set name="normal">
    <frame focus="no" state="normal" style="unfocused"/>
    <frame focus="yes" state="normal" style="focused"/>
  </frame_style_set>
  <window type="normal" style_set="normal"/>
</metacity_theme>"""


def test_takes_a_focused_title_bars_colour_and_text():
    assert title_colours_from(THEME.format(text="#FFFFFF")) == ("#0055aa", "#ffffff")


def test_swaps_text_that_cant_be_read_on_the_bar():
    assert title_colours_from(THEME.format(text="#0066BB")) == ("#0055aa", "#ffffff")


def test_a_bar_in_gtk_colours_gives_nothing():
    themed = THEME.format(text="#FFFFFF").replace('"#0055AA"', '"gtk:bg[SELECTED]"')
    assert title_colours_from(themed) is None


def test_a_gradient_bar_takes_its_first_colour():
    gradient = '<gradient type="vertical" x="0" y="0" width="width" height="height">'
    gradient += '<color value="#336699"/><color value="#000000"/></gradient>'
    start = THEME.index('<rectangle color="#0055AA"')
    end = THEME.index("/>", start) + 2
    themed = (THEME[:start] + gradient + THEME[end:]).format(text="#FFFFFF")
    assert title_colours_from(themed) == ("#336699", "#ffffff")


def test_text_that_isnt_xml_gives_nothing():
    assert title_colours_from("not a theme") is None
