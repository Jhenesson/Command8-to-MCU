from command8_bridge import command8_protocol as c8


# Esquema confirmado em docs/PROTOCOL.md via captura ao vivo (Tarefa 13):
# nota fixa por tipo de botão, velocity codifica canal (0-based) + estado
# (0x40+canal = apertar, 0x00+canal = soltar).


def test_decode_select_button_press_channel_0():
    assert c8.decode_channel_button([0x90, 0x00, 0x40]) == (0, "select", True)


def test_decode_select_button_release_channel_0():
    assert c8.decode_channel_button([0x90, 0x00, 0x00]) == (0, "select", False)


def test_decode_solo_button_press_channel_0():
    assert c8.decode_channel_button([0x90, 0x02, 0x40]) == (0, "solo", True)


def test_decode_mute_button_press_channel_0():
    assert c8.decode_channel_button([0x90, 0x03, 0x40]) == (0, "mute", True)


def test_decode_mute_button_press_channel_1():
    assert c8.decode_channel_button([0x90, 0x03, 0x41]) == (1, "mute", True)


def test_decode_mute_button_release_channel_1():
    assert c8.decode_channel_button([0x90, 0x03, 0x01]) == (1, "mute", False)


def test_decode_channel_button_unknown_note_returns_none():
    # nota 0x01 nunca foi observada em nenhum botão físico (ver PROTOCOL.md)
    assert c8.decode_channel_button([0x90, 0x01, 0x40]) is None


def test_decode_channel_button_rejects_out_of_range_channel():
    # anomalia documentada em PROTOCOL.md (velocity 0x4C -> canal 12, fora de 0-7)
    assert c8.decode_channel_button([0x90, 0x02, 0x4C]) is None


def test_encode_select_button_led_press_channel_0():
    assert c8.encode_channel_button_led(0, "select", True) == [0x90, 0x00, 0x40]


def test_encode_mute_button_led_press_channel_1():
    assert c8.encode_channel_button_led(1, "mute", True) == [0x90, 0x03, 0x41]


def test_encode_solo_button_led_release_channel_7():
    assert c8.encode_channel_button_led(7, "solo", False) == [0x90, 0x02, 0x07]


def test_decode_vpot_rotation_clockwise():
    # CC 64-71 (0x40-0x47), valor 0x41 (65) = sentido horário
    assert c8.decode_vpot_rotation([0xB0, 0x40, 0x41]) == (0, 1)


def test_decode_vpot_rotation_counterclockwise_channel_3():
    # valor 0x3F (63) = sentido anti-horário
    assert c8.decode_vpot_rotation([0xB0, 0x43, 0x3F]) == (3, -1)


def test_decode_vpot_rotation_ignores_out_of_range_cc():
    assert c8.decode_vpot_rotation([0xB0, 0x10, 0x41]) is None


def test_encode_vpot_led_ring_channel_1():
    # Frame corrigido em 2026-10-14 por captura ao vivo do V-Control Pro: o byte
    # de opcode 0x00 faltava. O último byte é NÍVEL 0-127, não bitmask — o
    # hardware desenha a barra sozinho (confirmado no vidro: 0x3F acendia só até
    # a metade do anel, porque 0x3F é metade de 0x7F).
    assert c8.encode_vpot_led_ring(1, 0x7F) == [0xF0, 0x13, 0x01, 0x00, 0x01, 0x7F, 0xF7]


# Fader confirmado em docs/PROTOCOL.md via captura ao vivo (2026-08-27): toque usa
# nota fixa 0x05 com o mesmo esquema velocity de canal+estado dos botões; posição
# vem em CC (0xB0), canal = byte1 % 8, valor 0-127 = byte2 direto.


def test_decode_fader_touch_press_channel_0():
    assert c8.decode_fader_touch([0x90, 0x05, 0x40]) == (0, True)


def test_decode_fader_touch_release_channel_6():
    assert c8.decode_fader_touch([0x90, 0x05, 0x06]) == (6, False)


def test_decode_fader_touch_ignores_other_notes():
    assert c8.decode_fader_touch([0x90, 0x00, 0x40]) is None


def test_decode_fader_position_channel_0():
    # captura real: B0 28 50 (canal 0, byte1=0x28 -> 0x28 % 8 == 0)
    assert c8.decode_fader_position([0xB0, 0x28, 0x50]) == (0, 0x50)


def test_decode_fader_position_channel_6():
    # captura real: B0 26 35 (canal 6, byte1=0x26 -> 0x26 % 8 == 6)
    assert c8.decode_fader_position([0xB0, 0x26, 0x35]) == (6, 0x35)


def test_decode_fader_position_ignores_vpot_rotation_range():
    assert c8.decode_fader_position([0xB0, 0x40, 0x41]) is None


def test_decode_fader_position_ignores_note_on():
    assert c8.decode_fader_position([0x90, 0x05, 0x40]) is None


def test_encode_fader_motor_position_channel_0_min():
    # confirmado ao vivo: B0 <canal> <posicao> move o motor do fader fisico
    assert c8.encode_fader_motor_position(0, 0x00) == [0xB0, 0x00, 0x00]


def test_encode_fader_motor_position_channel_0_max():
    assert c8.encode_fader_motor_position(0, 0x7F) == [0xB0, 0x00, 0x7F]


def test_encode_fader_motor_position_channel_6():
    assert c8.encode_fader_motor_position(6, 0x40) == [0xB0, 0x06, 0x40]


# LCD nativo — frame confirmado ao vivo no hardware (ver docs/PROTOCOL.md):
# F0 13 01 40 <célula> 7F 00 <7 × ASCII> F7, célula = linha*0x10 + strip.
def test_encode_lcd_text_builds_the_frame_confirmed_on_hardware():
    assert c8.encode_lcd_text(0, 0, "PONTE") == [
        0xF0, 0x13, 0x01, 0x40, 0x00, 0x7F, 0x00,
        0x50, 0x4F, 0x4E, 0x54, 0x45, 0x20, 0x20,
        0xF7,
    ]


def test_encode_lcd_text_addresses_lower_row_with_cell_offset():
    frame = c8.encode_lcd_text(1, 3, "abcdefg")

    assert frame[4] == 0x13


def test_encode_lcd_text_truncates_text_longer_than_seven_chars():
    frame = c8.encode_lcd_text(0, 0, "ABCDEFGHIJ")

    assert frame[7:14] == [ord(c) for c in "ABCDEFG"]


# Fórmula geral confirmada em 2026-10-14 (ver PROTOCOL.md): a velocity codifica a
# REGIÃO, não o canal. Strips são as regiões 0-7; o resto são regiões globais.
def test_decode_button_returns_region_index_and_state():
    assert c8.decode_button([0x90, 0x0B, 0x4E]) == (14, 0x0B, True)


def test_decode_button_decodes_release():
    assert c8.decode_button([0x90, 0x03, 0x02]) == (2, 0x03, False)


def test_decode_button_decodes_the_old_0x4c_anomaly_as_the_main_region():
    assert c8.decode_button([0x90, 0x02, 0x4C]) == (12, 0x02, True)


def test_decode_button_ignores_the_beacon():
    assert c8.decode_button([0x90, 0x00, 0x7F]) is None


def test_decode_button_ignores_non_note_on_messages():
    assert c8.decode_button([0xB0, 0x00, 0x40]) is None


# Bloco de transporte capturado ao vivo em 2026-10-14: notas 0x07-0x0B consecutivas
# na região 14, na ordem física Rewind, Forward, Stop, Play, Record.
def test_decode_transport_button_maps_play():
    assert c8.decode_transport_button([0x90, 0x0A, 0x4E]) == ("play", True)


def test_decode_transport_button_maps_record_confirming_the_documented_note():
    assert c8.decode_transport_button([0x90, 0x0B, 0x0E]) == ("record", False)


def test_decode_transport_button_ignores_channel_buttons():
    assert c8.decode_transport_button([0x90, 0x03, 0x40]) is None


def test_decode_transport_button_maps_return_to_zero():
    assert c8.decode_transport_button([0x90, 0x06, 0x4E]) == ("rtz", True)


# O visor tem 4 fileiras, e as bases não são lineares (confirmado sondando o
# hardware em 2026-10-14): 0x00, 0x10, 0x28, 0x38.
def test_encode_lcd_text_reaches_the_third_row():
    assert c8.encode_lcd_text(2, 0, "x")[4] == 0x28


def test_encode_lcd_text_reaches_the_fourth_row_right_side():
    assert c8.encode_lcd_text(3, 6, "668 1 1")[4] == 0x3E


# Meters nativos, capturados do V-Control Pro em 2026-10-14:
# 90 <0x40 | barra de 5 bits> <canal>, barra preenchendo do bit 4 pra baixo.
def test_encode_meter_with_no_segments():
    assert c8.encode_meter(0, 0) == [0x90, 0x40, 0x00]


def test_encode_meter_with_three_segments():
    assert c8.encode_meter(3, 3) == [0x90, 0x5C, 0x03]


def test_encode_meter_at_full_scale():
    assert c8.encode_meter(0, 5) == [0x90, 0x5F, 0x00]


def test_meter_level_from_mcu_scales_the_top_of_the_range():
    assert c8.meter_level_from_mcu(12) == 5


def test_meter_level_from_mcu_keeps_silence_dark():
    assert c8.meter_level_from_mcu(0) == 0


# Anel do V-Pot: F0 13 01 00 <canal> <máscara> F7. O opcode 0x00 estava FALTANDO
# na implementação anterior, vinda de documentação de terceiros.
def test_encode_vpot_led_ring_puts_the_low_leds_in_the_second_byte():
    assert c8.encode_vpot_led_ring(2, 0b1111111) == [0xF0, 0x13, 0x01, 0x00, 0x02, 0x7F, 0xF7]


def test_encode_vpot_led_ring_packs_the_high_leds_into_the_channel_byte():
    # Frame capturado ao vivo do V-Control Pro girando um pan: 79 60 é o canal 1
    # com os 4 LEDs altos acesos e dois dos baixos.
    assert c8.encode_vpot_led_ring(1, 0b11111100000) == [
        0xF0, 0x13, 0x01, 0x00, 0x79, 0x60, 0xF7
    ]


def test_encode_vpot_led_ring_can_close_the_whole_ring():
    frame = c8.encode_vpot_led_ring(0, 0b11111111111)

    assert frame[4] == 0x78 and frame[5] == 0x7F


def test_vpot_ring_mask_is_dark_at_position_zero():
    assert c8.vpot_ring_mask(1, 0) == 0


def test_vpot_ring_mask_draws_pan_as_a_bar_from_the_centre():
    # Reproduz exatamente a varredura capturada do V-Control Pro girando um pan:
    # todo à esquerda = bits 0-5, centro = bit 5, todo à direita = bits 5-10.
    assert c8.vpot_ring_mask(1, 1) == 0b00000111111
    assert c8.vpot_ring_mask(1, 6) == 0b00000100000
    assert c8.vpot_ring_mask(1, 11) == 0b11111100000


def test_vpot_ring_mask_fills_from_the_left_in_wrap_mode():
    assert c8.vpot_ring_mask(2, 11) == 0b11111111111


def test_vpot_ring_mask_lights_a_single_led_in_dot_mode():
    assert c8.vpot_ring_mask(0, 11) == 0b10000000000


# LED de transporte: mesma nota do botão, região 14 (confirmado no log, 90 0A 0E).
def test_encode_transport_led_on():
    assert c8.encode_transport_led("play", True) == [0x90, 0x0A, 0x4E]


def test_encode_transport_led_off():
    assert c8.encode_transport_led("play", False) == [0x90, 0x0A, 0x0E]


# Console View, mapeado ao vivo em 2026-10-14 apertando um botão de cada vez.
# Região 10 (Mode) menos o Display Mode, que fica na região 11 (Top).
def test_decode_console_button_maps_pan():
    assert c8.decode_console_button([0x90, 0x00, 0x4A]) == ("pan", True)


def test_decode_console_button_maps_the_letter_keys():
    assert c8.decode_console_button([0x90, 0x05, 0x4A]) == ("c", True)


def test_decode_console_button_maps_display_mode_in_the_top_region():
    assert c8.decode_console_button([0x90, 0x08, 0x4B]) == ("display", True)


def test_decode_console_button_ignores_channel_strip_buttons():
    assert c8.decode_console_button([0x90, 0x03, 0x40]) is None


# Mapa completo dos botões globais, levantado ao vivo em 2026-10-15.
def test_decode_global_button_in_the_main_region():
    assert c8.decode_global_button([0x90, 0x00, 0x4C]) == ("enter", True)


def test_decode_global_button_in_the_functions_region():
    assert c8.decode_global_button([0x90, 0x09, 0x4D]) == ("f1", True)


def test_decode_global_button_shares_a_region_with_the_transport():
    assert c8.decode_global_button([0x90, 0x01, 0x4E]) == ("mix", True)


def test_decode_global_button_reads_release():
    assert c8.decode_global_button([0x90, 0x07, 0x0B]) == ("esc", False)


def test_decode_global_button_ignores_channel_strips():
    assert c8.decode_global_button([0x90, 0x03, 0x40]) is None
