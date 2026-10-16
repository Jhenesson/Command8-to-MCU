from command8_bridge.lcd_buffer import LcdBuffer


def test_an_aligned_write_returns_the_cell_it_filled():
    buffer = LcdBuffer()

    assert buffer.write(0, "Kick   ") == [(0, 0, "Kick   ")]


def test_an_unaligned_write_returns_the_whole_cell_around_it():
    # O Logic manda valores em offsets no meio da célula (57, 58, 59). Antes do
    # buffer eles eram descartados em silêncio.
    buffer = LcdBuffer()
    buffer.write(56, "-6,0   ")

    assert buffer.write(57, "5,8") == [(1, 0, "-5,8   ")]


def test_a_write_that_changes_nothing_returns_no_cells():
    buffer = LcdBuffer()
    buffer.write(0, "Kick   ")

    assert buffer.write(0, "Kick   ") == []


def test_a_write_spanning_two_cells_returns_both():
    buffer = LcdBuffer()

    assert buffer.write(0, "Kick   Snare  ") == [(0, 0, "Kick   "), (0, 1, "Snare  ")]


def test_a_write_can_cross_from_one_row_to_the_next():
    buffer = LcdBuffer()

    mudadas = buffer.write(49, "LastOne" + "FirstOf")

    assert mudadas == [(0, 7, "LastOne"), (1, 0, "FirstOf")]


def test_writing_past_the_end_is_ignored():
    buffer = LcdBuffer()

    assert buffer.write(111, "AB") == [(1, 7, "      A")]
