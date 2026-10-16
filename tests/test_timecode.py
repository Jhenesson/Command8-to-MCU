from command8_bridge.timecode import TimecodeDisplay


def test_text_assembles_the_digits_in_order():
    display = TimecodeDisplay()
    for i, char in enumerate("668 1 1 39"):
        display.feed(i, char)

    assert display.text() == "668 1 1 39"


def test_take_render_returns_the_text_the_first_time():
    display = TimecodeDisplay(min_interval=0.1)
    display.feed(0, "1")

    assert display.take_render(now=0.0) == "1         "


def test_take_render_returns_none_when_nothing_changed():
    display = TimecodeDisplay(min_interval=0.1)
    display.feed(0, "1")
    display.take_render(now=0.0)

    assert display.take_render(now=5.0) is None


def test_take_render_holds_back_updates_that_come_too_fast():
    display = TimecodeDisplay(min_interval=0.1)
    display.feed(0, "1")
    display.take_render(now=0.0)
    display.feed(0, "2")

    assert display.take_render(now=0.05) is None


def test_take_render_releases_the_update_once_the_interval_passed():
    display = TimecodeDisplay(min_interval=0.1)
    display.feed(0, "1")
    display.take_render(now=0.0)
    display.feed(0, "2")

    assert display.take_render(now=0.2) == "2         "


def test_format_for_display_separates_division_from_ticks():
    from command8_bridge.timecode import format_for_display

    assert format_for_display("684 4 2197") == "684 4 2 197"
