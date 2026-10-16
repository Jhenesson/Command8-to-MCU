from command8_bridge import spy


def test_format_bytes_formats_uppercase_hex_pairs():
    assert spy.format_bytes([0xF0, 0x13, 0x00, 0xF7]) == "F0 13 00 F7"


def test_printable_ascii_keeps_only_printable_characters():
    assert spy.printable_ascii([0x41, 0x42, 0x00, 0x43, 0x7F]) == "AB.C."


def test_describe_recognizes_beacon():
    assert "beacon" in spy.describe([0x90, 0x00, 0x7F])


def test_describe_recognizes_channel_button():
    description = spy.describe([0x90, 0x03, 0x41])
    assert "Mute" in description
    assert "canal 2" in description
    assert "apert" in description


def test_describe_recognizes_fader_touch():
    description = spy.describe([0x90, 0x05, 0x40])
    assert "fader" in description
    assert "canal 1" in description
    assert "toque" in description


def test_describe_recognizes_fader_position():
    description = spy.describe([0xB0, 0x02, 0x64])
    assert "fader" in description
    assert "canal 3" in description
    assert "100" in description


def test_describe_recognizes_vpot_rotation():
    description = spy.describe([0xB0, 0x41, 0x41])
    assert "V-Pot" in description
    assert "canal 2" in description


def test_describe_recognizes_digidesign_family_sysex_and_extracts_text():
    message = [0xF0, 0x13, 0x40, 0x40, 0x00, 0x02, 0x05, 0x01] + list(b"ABCDEF") + [0xF7]
    description = spy.describe(message)
    assert "0x13" in description
    assert "ABCDEF" in description


def test_describe_flags_mcu_sysex_as_wrong_port():
    message = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00] + list(b"Kick") + [0xF7]
    description = spy.describe(message)
    assert "MCU" in description
    assert "porta errada" in description


def test_describe_marks_unrecognized_message():
    assert "?" in spy.describe([0xD0, 0x7F])


def test_repeat_collapser_suppresses_identical_consecutive_messages():
    collapser = spy.RepeatCollapser()

    first = collapser.feed([0x90, 0x00, 0x7F])
    second = collapser.feed([0x90, 0x00, 0x7F])

    assert first.emit is True
    assert second.emit is False


def test_repeat_collapser_reports_how_many_were_suppressed_when_stream_changes():
    collapser = spy.RepeatCollapser()
    collapser.feed([0x90, 0x00, 0x7F])
    collapser.feed([0x90, 0x00, 0x7F])
    collapser.feed([0x90, 0x00, 0x7F])

    result = collapser.feed([0x90, 0x03, 0x40])

    assert result.emit is True
    assert result.suppressed == 2


def test_describe_recognizes_mcu_device_query_as_host_scan():
    description = spy.describe([0xF0, 0x00, 0x00, 0x66, 0x14, 0x00, 0xF7])
    assert "device query" in description
    assert "0x14" in description
    assert "porta errada" not in description


def test_describe_recognizes_mcu_version_request():
    description = spy.describe([0xF0, 0x00, 0x00, 0x66, 0x10, 0x13, 0x00, 0xF7])
    assert "version request" in description
    assert "0x10" in description
    assert "porta errada" not in description
