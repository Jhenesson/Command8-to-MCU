from command8_bridge import mcu_protocol as mcu


def test_encode_fader_position_channel_0_min():
    assert mcu.encode_fader_position(0, 0) == [0xE0, 0x00, 0x00]


def test_encode_fader_position_channel_0_max():
    # 16383 = 0x3FFF -> LSB 0x7F, MSB 0x7F
    assert mcu.encode_fader_position(0, 16383) == [0xE0, 0x7F, 0x7F]


def test_encode_fader_position_channel_7_mid():
    # 8192 = 0x2000 -> LSB 0x00, MSB 0x40
    assert mcu.encode_fader_position(7, 8192) == [0xE7, 0x00, 0x40]


def test_decode_fader_position_roundtrip():
    msg = mcu.encode_fader_position(3, 12000)
    assert mcu.decode_fader_position(msg) == (3, 12000)


def test_decode_fader_position_ignores_non_pitchbend():
    assert mcu.decode_fader_position([0x90, 0x40, 0x7F]) is None


def test_encode_fader_touch_pressed():
    assert mcu.encode_fader_touch(0, True) == [0x90, 0x68, 0x7F]


def test_encode_fader_touch_released_channel_7():
    assert mcu.encode_fader_touch(7, False) == [0x90, 0x6F, 0x00]


def test_encode_mute_led_on_channel_0():
    assert mcu.encode_channel_button_led(0, mcu.BUTTON_MUTE, True) == [0x90, 0x10, 0x7F]


def test_encode_select_led_off_channel_7():
    assert mcu.encode_channel_button_led(7, mcu.BUTTON_SELECT, False) == [0x90, 0x1F, 0x00]


def test_decode_rec_button_channel_3():
    assert mcu.decode_channel_button([0x90, 0x03, 0x7F]) == (3, mcu.BUTTON_REC, True)


def test_decode_solo_button_channel_5_release():
    assert mcu.decode_channel_button([0x90, 0x0D, 0x00]) == (5, mcu.BUTTON_SOLO, False)


def test_decode_channel_button_ignores_out_of_range():
    assert mcu.decode_channel_button([0x90, 0x60, 0x7F]) is None


def test_decode_vpot_rotation_clockwise():
    assert mcu.decode_vpot_rotation([0xB0, 0x10, 0x01]) == (0, 1)


def test_decode_vpot_rotation_counterclockwise_channel_7():
    assert mcu.decode_vpot_rotation([0xB0, 0x17, 0x41]) == (7, -1)


def test_decode_vpot_rotation_ignores_non_cc():
    assert mcu.decode_vpot_rotation([0x90, 0x10, 0x01]) is None


def test_encode_vpot_click_channel_2():
    assert mcu.encode_vpot_click(2, True) == [0x90, 0x22, 0x7F]


def test_encode_vpot_rotation_clockwise():
    assert mcu.encode_vpot_rotation(0, 1) == [0xB0, 0x10, 0x01]


def test_encode_vpot_rotation_counterclockwise_channel_7():
    assert mcu.encode_vpot_rotation(7, -1) == [0xB0, 0x17, 0x41]


def test_encode_vpot_led_ring_channel_0():
    # led_on=True (bit6), mode=0b01, value=0b0101
    result = mcu.encode_vpot_led_ring(0, True, 0b01, 0b0101)
    assert result == [0xB0, 0x30, 0b01010101]


def test_encode_vpot_led_ring_channel_7_off():
    result = mcu.encode_vpot_led_ring(7, False, 0b00, 0b0000)
    assert result == [0xB0, 0x37, 0b00000000]


# Task 5: Handshake de dispositivo

def test_compute_challenge_response_known_vector():
    # Vetor de teste construído a partir da fórmula documentada publicamente
    # (não é uma captura real do Logic — serve para travar o comportamento da função).
    challenge = [0x10, 0x20, 0x30, 0x40]
    response = mcu.compute_challenge_response(challenge)
    assert len(response) == 4
    assert all(0 <= b <= 0x7F for b in response)
    # Determinístico: mesma entrada, mesma saída
    assert mcu.compute_challenge_response(challenge) == response


def test_compute_challenge_response_matches_formula():
    c = [0x01, 0x02, 0x03, 0x04]
    r = mcu.compute_challenge_response(c)
    assert r[0] == (0x7F & (c[0] + (c[1] ^ 0x0A) - c[3]))
    assert r[1] == (0x7F & ((c[2] >> 4) ^ (c[0] + c[3])))
    assert r[2] == (0x7F & (c[3] - (c[2] << 2) ^ (c[0] | c[1])))
    assert r[3] == (0x7F & (c[1] - c[2] + (0xF0 ^ (c[3] << 4))))


def test_is_host_connection_query_true():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x01] + [0] * 7 + [1, 2, 3, 4] + [0xF7]
    assert mcu.is_host_connection_query(msg) is True


def test_is_host_connection_query_false_for_other_sysex():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00, 0xF7]
    assert mcu.is_host_connection_query(msg) is False


def test_encode_host_connection_reply_structure():
    serial = [1, 2, 3, 4, 5, 6, 7]
    challenge = [0x10, 0x20, 0x30, 0x40]
    msg = mcu.encode_host_connection_reply(serial, challenge)
    assert msg[:6] == [0xF0, 0x00, 0x00, 0x66, 0x14, 0x02]
    assert msg[6:13] == serial
    assert msg[13:17] == mcu.compute_challenge_response(challenge)
    assert msg[-1] == 0xF7


def test_encode_device_query():
    assert mcu.encode_device_query() == [0xF0, 0x00, 0x00, 0x66, 0x14, 0x00, 0xF7]


# Task 6: LCD text decode and transport buttons


def test_decode_lcd_text_basic():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00] + [ord(c) for c in "Kick  "] + [0xF7]
    assert mcu.decode_lcd_text(msg) == (0, "Kick  ")


def test_decode_lcd_text_offset_second_channel():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x07] + [ord(c) for c in "Snare "] + [0xF7]
    assert mcu.decode_lcd_text(msg) == (7, "Snare ")


def test_decode_lcd_text_ignores_other_sysex():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x00, 0xF7]
    assert mcu.decode_lcd_text(msg) is None


def test_decode_transport_play():
    assert mcu.decode_transport_button([0x90, 94, 0x7F]) == ("play", True)


def test_decode_transport_stop_release():
    assert mcu.decode_transport_button([0x90, 93, 0x00]) == ("stop", False)


def test_decode_transport_ignores_unrelated_note():
    assert mcu.decode_transport_button([0x90, 50, 0x7F]) is None



def test_encode_transport_button_press():
    assert mcu.encode_transport_button("play", True) == [0x90, 94, 0x7F]


def test_encode_transport_button_release():
    assert mcu.encode_transport_button("record", False) == [0x90, 95, 0x00]


# Timecode do MCU, capturado ao vivo do Logic em 2026-10-14: CC 0x40-0x49 com o
# caractere em ASCII puro (nada de 7 segmentos). 0x49 é o dígito mais à esquerda.
def test_decode_timecode_digit_maps_leftmost_position():
    assert mcu.decode_timecode_digit([0xB0, 0x49, 0x36]) == (0, "6")


def test_decode_timecode_digit_maps_rightmost_position():
    assert mcu.decode_timecode_digit([0xB0, 0x40, 0x39]) == (9, "9")


def test_decode_timecode_digit_ignores_vpot_ring_cc():
    assert mcu.decode_timecode_digit([0xB0, 0x30, 0x56]) is None


def test_decode_meter_splits_channel_and_level():
    assert mcu.decode_meter([0xD0, 0x35]) == (3, 5)


def test_decode_meter_ignores_other_messages():
    assert mcu.decode_meter([0x90, 0x00, 0x40]) is None


def test_decode_vpot_led_ring_splits_channel_mode_and_position():
    assert mcu.decode_vpot_led_ring([0xB0, 0x32, 0x56]) == (2, 1, 6)


def test_decode_vpot_led_ring_ignores_timecode_cc():
    assert mcu.decode_vpot_led_ring([0xB0, 0x40, 0x39]) is None


def test_encode_assignment_button_press():
    assert mcu.encode_assignment_button("pan", True) == [0x90, 0x2A, 0x7F]


def test_encode_function_key_release():
    assert mcu.encode_function_key("f1", False) == [0x90, 0x36, 0x00]


def test_encode_named_button_press():
    assert mcu.encode_named_button("enter", True) == [0x90, 0x55, 0x7F]


def test_encode_named_button_release():
    assert mcu.encode_named_button("shift", False) == [0x90, 0x48, 0x00]
