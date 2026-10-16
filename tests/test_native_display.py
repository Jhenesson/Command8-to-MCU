from command8_bridge.native_display import NativeDisplay


def test_setting_a_cell_for_the_first_time_counts_as_a_change():
    display = NativeDisplay()

    assert display.set(1, 0, "Kick   ") is True


def test_setting_the_same_content_again_is_not_a_change():
    display = NativeDisplay()
    display.set(1, 0, "Kick   ")

    assert display.set(1, 0, "Kick   ") is False


def test_a_cell_that_was_overwritten_is_a_change_again():
    display = NativeDisplay()
    display.set(1, 0, "Kick   ")
    display.set(1, 0, "Volume ")

    assert display.set(1, 0, "Kick   ") is True


def test_cells_are_tracked_independently():
    display = NativeDisplay()
    display.set(1, 0, "Kick   ")

    assert display.set(1, 1, "Kick   ") is True
