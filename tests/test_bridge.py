from command8_bridge import command8_protocol as c8
from command8_bridge import mcu_protocol as mcu
from command8_bridge.bridge import Bridge
from command8_bridge.channel_state import ChannelState


class FakeMidiOut:
    def __init__(self):
        self.sent: list[list[int]] = []

    def send_message(self, message):
        self.sent.append(list(message))


def test_hardware_mute_button_forwards_to_host_as_mcu():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x03, 0x40])  # mute channel 0 apertado, nativo

    assert host_out.sent == [[0x90, 0x10, 0x7F]]  # nota MCU de mute canal 0


def test_hardware_mute_button_repeated_does_not_resend():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x03, 0x40])
    bridge.handle_hardware_message([0x90, 0x03, 0x40])  # repetido, sem mudança de estado

    assert host_out.sent == [[0x90, 0x10, 0x7F]]


def test_hardware_vpot_rotation_forwards_as_mcu_cc():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0xB0, 0x40, 0x41])  # encoder 0, horário, nativo

    assert host_out.sent == [[0xB0, 0x10, 0x01]]  # CC MCU equivalente


def test_hardware_fader_touch_forwards_to_host_as_mcu():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x05, 0x40])  # fader canal 0 tocado, nativo

    assert host_out.sent == [[0x90, 0x68, 0x7F]]  # nota MCU de touch canal 0


def test_hardware_fader_release_forwards_to_host_as_mcu():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x05, 0x00])  # fader canal 0 solto, nativo

    assert host_out.sent == [[0x90, 0x68, 0x00]]


def test_hardware_fader_position_forwards_as_mcu_pitch_bend():
    from command8_bridge import mcu_protocol as mcu

    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0xB0, 0x28, 0x50])  # fader canal 0, posição 0x50 nativa

    assert host_out.sent == [mcu.encode_fader_position(0, 0x50 * 129)]


def test_host_fader_position_forwards_as_motor_command():
    from command8_bridge import mcu_protocol as mcu

    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_host_message(mcu.encode_fader_position(0, 0x50 * 129))  # canal 0, MCU

    assert hardware_out.sent == [[0xB0, 0x00, 0x50]]  # motor nativo canal 0


def test_host_mute_led_forwards_to_hardware():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_host_message([0x90, 0x10, 0x7F])  # Logic liga LED mute canal 0 (nota MCU)

    assert hardware_out.sent == [[0x90, 0x03, 0x40]]  # mute canal 0 apertado, nativo


def test_host_lcd_text_forwards_to_hardware_as_native_frame():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    # Logic manda texto de LCD do MCU pro strip 1, linha de cima
    bridge.handle_host_message(
        [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00] + list(b"Kick   " * 8) + [0xF7]
    )

    # nomes vão pra fileira de baixo (célula 0x10), copiando o original
    assert (
        [0xF0, 0x13, 0x01, 0x40, 0x10, 0x7F, 0x00] + list(b"Kick   ") + [0xF7]
    ) in hardware_out.sent


def test_hardware_transport_button_forwards_to_host():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x0A, 0x4E])  # Play apertado, nativo

    assert host_out.sent == [[0x90, 94, 0x7F]]  # Play do MCU


def test_hardware_return_to_zero_is_not_forwarded_for_lack_of_an_mcu_equivalent():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x06, 0x4E])  # RTZ apertado, nativo

    assert host_out.sent == []


def test_host_timecode_renders_into_the_timecode_display_cells():
    hardware_out = FakeMidiOut()
    tempo = [0.0]
    bridge = Bridge(
        hardware_out=hardware_out,
        host_out=FakeMidiOut(),
        state=ChannelState(),
        now=lambda: tempo[0],
    )

    for cc, char in zip(range(0x49, 0x3F, -1), "668 1 1 39"):
        bridge.handle_host_message([0xB0, cc, ord(char)])

    tempo[0] = 1.0  # passou o intervalo mínimo
    bridge.handle_host_message([0xB0, 0x40, ord("8")])  # último dígito muda

    linha = c8.LCD_TIMECODE_ROW
    esq, dir = c8.LCD_TIMECODE_STRIPS
    # com o separador entre divisão e ticks: "668 1 1" + "  38"
    assert hardware_out.sent[-2:] == [
        c8.encode_lcd_text(linha, esq, "668 1 1"),
        c8.encode_lcd_text(linha, dir, "  38"),
    ]


def test_host_meter_forwards_to_hardware():
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())

    bridge.handle_host_message([0xD0, 0x3C])  # canal 3, nível 12 (topo) no MCU

    assert hardware_out.sent == [c8.encode_meter(3, 5)]


def test_host_vpot_ring_forwards_to_hardware():
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())

    bridge.handle_host_message([0xB0, 0x32, 0x06])  # canal 2, modo 0, posição 6

    assert hardware_out.sent == [c8.encode_vpot_led_ring(2, c8.vpot_ring_mask(0, 6))]


def test_host_transport_led_forwards_to_hardware():
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())

    bridge.handle_host_message([0x90, 94, 0x7F])  # Play aceso, MCU

    assert hardware_out.sent == [c8.encode_transport_led("play", True)]


def test_hardware_console_pan_button_becomes_an_mcu_assignment():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x00, 0x4A])  # Pan, região 10

    assert host_out.sent == [[0x90, 0x2A, 0x7F]]


def test_hardware_function_key_reaches_the_host():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x09, 0x4D])  # F1, região Functions

    assert host_out.sent == [[0x90, 0x36, 0x7F]]


def test_hardware_display_mode_button_is_reserved_and_not_forwarded():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x08, 0x4B])  # Display Mode

    assert host_out.sent == []


def test_hardware_enter_button_reaches_the_host_as_the_mcu_enter():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x00, 0x4C])  # Enter, região Main

    assert host_out.sent == [[0x90, 0x55, 0x7F]]


def test_hardware_arrow_key_reaches_the_host():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x07, 0x4D])  # Up, região Functions

    assert host_out.sent == [[0x90, 0x60, 0x7F]]


def test_hardware_button_without_an_mcu_equivalent_is_not_forwarded():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x04, 0x4A])  # botão B, sem equivalente

    assert host_out.sent == []


def _mcu_lcd(offset, texto):
    return [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, offset] + [ord(c) for c in texto] + [0xF7]


def test_track_name_survives_a_fader_touch():
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())

    bridge.handle_host_message(_mcu_lcd(0, "Kick   "))      # Logic manda o nome
    bridge.handle_hardware_message([0x90, 0x05, 0x40])      # toque no fader 1
    hardware_out.sent.clear()
    bridge.handle_host_message(_mcu_lcd(0, " -6.0dB"))      # Logic troca pelo volume

    # o valor não pode cair na fileira dos nomes
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]
    assert hardware_out.sent != [c8.encode_lcd_text(linha_nomes, 0, " -6.0dB")]


def test_the_name_cell_only_ever_receives_the_name_during_a_touch_cycle():
    # Com o render centralizado o nome não precisa ser "restaurado": ele nunca
    # chega a sair do visor durante o ciclo de toque.
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())
    esperado = c8.encode_lcd_text(c8.LCD_ROW_FOR_MCU_LINE[0], 0, "Kick   ")
    celula = esperado[4]

    bridge.handle_host_message(_mcu_lcd(0, "Kick   " * 8))
    bridge.handle_hardware_message([0x90, 0x05, 0x40])
    bridge.handle_host_message(_mcu_lcd(0, " -6.0dB"))
    bridge.handle_hardware_message([0x90, 0x05, 0x00])

    escritas = [m for m in hardware_out.sent if m[:5] == esperado[:5] and m[4] == celula]
    assert escritas == [esperado]


def test_value_text_arriving_just_after_release_does_not_replace_the_name():
    hardware_out = FakeMidiOut()
    tempo = [0.0]
    bridge = Bridge(
        hardware_out=hardware_out, host_out=FakeMidiOut(),
        state=ChannelState(), now=lambda: tempo[0],
    )
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]

    bridge.handle_host_message(_mcu_lcd(0, "Kick   "))
    bridge.handle_hardware_message([0x90, 0x05, 0x40])   # toca
    bridge.handle_hardware_message([0x90, 0x05, 0x00])   # solta
    hardware_out.sent.clear()

    tempo[0] = 0.1                                       # dentro da carência
    bridge.handle_host_message(_mcu_lcd(0, " -6.0dB"))

    assert c8.encode_lcd_text(linha_nomes, 0, " -6.0dB") not in hardware_out.sent



def test_a_touch_also_shields_the_neighbour_strip_from_being_blanked():
    # Ao tocar um fader o Logic escreve o rótulo no strip tocado E APAGA o
    # vizinho (offset 7 com espaços). Nenhum dos dois pode virar nome.
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]

    bridge.handle_host_message(_mcu_lcd(0, "Kick   Snare  "))
    bridge.handle_hardware_message([0x90, 0x05, 0x40])   # toca o fader 1
    hardware_out.sent.clear()

    bridge.handle_host_message(_mcu_lcd(0, "Volume"))    # rótulo no strip 0
    bridge.handle_host_message(_mcu_lcd(7, "      "))    # Logic apaga o strip 1

    assert c8.encode_lcd_text(linha_nomes, 1, "      ") not in hardware_out.sent


def test_the_db_suffix_is_stripped_from_the_value_display():
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())

    bridge.handle_host_message(_mcu_lcd(56, "14,0 dB"))

    # mantém o comprimento pra não desalinhar as posições seguintes
    assert c8.encode_lcd_text(c8.LCD_ROW_FOR_MCU_LINE[1], 0, "14,0   ") in hardware_out.sent


def test_bank_held_turns_the_arrows_into_single_channel_shifts():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x02, 0x4D])   # segura Bank
    host_out.sent.clear()
    bridge.handle_hardware_message([0x90, 0x06, 0x4D])   # seta direita

    assert host_out.sent == [mcu.encode_named_button("channel_right", True)]


def test_the_arrows_are_cursor_keys_when_bank_is_not_held():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x06, 0x4D])   # seta direita sozinha

    assert host_out.sent == [mcu.encode_named_button("right", True)]


def test_releasing_bank_restores_the_cursor_behaviour():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x02, 0x4D])   # segura
    bridge.handle_hardware_message([0x90, 0x02, 0x0D])   # solta
    host_out.sent.clear()
    bridge.handle_hardware_message([0x90, 0x05, 0x4D])   # seta esquerda

    assert host_out.sent == [mcu.encode_named_button("left", True)]


def test_the_bank_button_itself_is_not_forwarded():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x02, 0x4D])

    assert host_out.sent == []


def test_holding_bank_lights_its_own_led():
    # A ponte intercepta o Bank e não o encaminha, então o host nunca acende o
    # LED dele — quem acende somos nós.
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x02, 0x4D])

    assert hardware_out.sent == [[0x90, 0x02, 0x4D]]


def test_releasing_bank_turns_its_led_off():
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x02, 0x4D])
    hardware_out.sent.clear()
    bridge.handle_hardware_message([0x90, 0x02, 0x0D])

    assert hardware_out.sent == [[0x90, 0x02, 0x0D]]


def test_pressing_mute_does_not_let_the_label_replace_the_track_name():
    hardware_out = FakeMidiOut()
    tempo = [0.0]
    bridge = Bridge(
        hardware_out=hardware_out, host_out=FakeMidiOut(),
        state=ChannelState(), now=lambda: tempo[0],
    )
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]

    bridge.handle_host_message(_mcu_lcd(0, "Kick   "))
    bridge.handle_hardware_message([0x90, 0x03, 0x40])   # mute do canal 1
    hardware_out.sent.clear()

    tempo[0] = 0.2
    bridge.handle_host_message(_mcu_lcd(0, "Mute   "))

    assert c8.encode_lcd_text(linha_nomes, 0, "Mute   ") not in hardware_out.sent



def test_the_motor_is_not_driven_while_the_user_is_holding_the_fader():
    # Senão o motor briga com a mão: a posição vai pro host, o host devolve, e a
    # ponte reposiciona o fader que está sendo segurado.
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x05, 0x40])   # toca o fader 1
    hardware_out.sent.clear()
    bridge.handle_host_message(mcu.encode_fader_position(0, 0x50 * 129))

    assert hardware_out.sent == []


def test_the_motor_moves_again_once_the_fader_is_released():
    hardware_out = FakeMidiOut()
    tempo = [0.0]
    bridge = Bridge(
        hardware_out=hardware_out, host_out=FakeMidiOut(),
        state=ChannelState(), now=lambda: tempo[0],
    )

    bridge.handle_hardware_message([0x90, 0x05, 0x40])
    bridge.handle_hardware_message([0x90, 0x05, 0x00])
    tempo[0] = 2.0
    hardware_out.sent.clear()
    bridge.handle_host_message(mcu.encode_fader_position(0, 0x50 * 129))

    assert hardware_out.sent == [[0xB0, 0x00, 0x50]]


def test_a_short_write_never_becomes_a_track_name():
    # Rótulos ("Volume", "Mute") chegam como escritas curtas num strip só.
    # Só um refresh da linha inteira é nome de verdade.
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]

    bridge.handle_host_message(_mcu_lcd(0, "Kick   " * 8))   # refresh completo
    hardware_out.sent.clear()
    bridge.handle_host_message(_mcu_lcd(0, "Volume"))        # rótulo

    assert c8.encode_lcd_text(linha_nomes, 0, "Volume ") not in hardware_out.sent


def test_a_full_row_refresh_updates_every_name():
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]

    nomes = "Kick   Snare  HatOH  Bass   Gtr    Keys   Vox    Perc   "
    bridge.handle_host_message(_mcu_lcd(0, nomes))

    assert c8.encode_lcd_text(linha_nomes, 1, "Snare  ") in hardware_out.sent
    assert c8.encode_lcd_text(linha_nomes, 7, "Perc   ") in hardware_out.sent


def test_a_bank_change_refresh_with_trailing_blank_trimmed_still_updates_names():
    # Capturado ao vivo: ao trocar de banco o Logic manda a linha de nomes com
    # 55 caracteres (o espaço final é cortado), não 56.
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]

    bridge.handle_host_message(_mcu_lcd(0, "Kick   " * 8))
    hardware_out.sent.clear()
    bridge.handle_host_message(_mcu_lcd(0, ("Aux 8  " * 8)[:55]))

    assert c8.encode_lcd_text(linha_nomes, 0, "Aux 8  ") in hardware_out.sent
    assert c8.encode_lcd_text(linha_nomes, 7, "Aux 8  ") in hardware_out.sent


def test_console_view_a_is_sent_as_f6_press_only_so_the_release_does_not_undo_it():
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=FakeMidiOut(), host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x03, 0x4A])   # Console View A apertado
    bridge.handle_hardware_message([0x90, 0x03, 0x0A])   # solto

    # Com o "solto" o Logic desfazia o comando de abrir pilha ao soltar o botão.
    assert host_out.sent == [mcu.encode_named_button("f6", True)]


def _linha(*nomes):
    return "".join(n.ljust(7) for n in nomes)


def test_names_follow_a_stack_opening_written_as_head_and_tail():
    # Capturado ao vivo: ao abrir uma pasta o Logic desliza a linha de nomes e
    # a reescreve em duas partes (cabeça em offset 0, cauda perto do fim), sem
    # nenhuma delas ter 50+ caracteres.
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]
    antes = ["GTR", "BAIXO", "TECLAD", "DRUM", "SN", "01", "02", "KIK"]
    depois = ["BAIXO", "TECLAD", "DRUM", "SN", "01", "02", "KIK", "T1"]

    bridge.handle_host_message(_mcu_lcd(0, _linha(*antes)))
    hardware_out.sent.clear()
    bridge.handle_host_message(_mcu_lcd(0, _linha(*depois[:6])))
    bridge.handle_host_message(_mcu_lcd(35, _linha(*depois[5:])))

    for strip, nome in enumerate(depois):
        assert c8.encode_lcd_text(linha_nomes, strip, nome.ljust(7)) in hardware_out.sent


def test_a_label_written_next_to_a_name_does_not_become_a_name():
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]

    bridge.handle_host_message(_mcu_lcd(0, _linha("DRUM", "SN", "KIK", "T1", "T2", "OH", "PAD", "AUX")))
    hardware_out.sent.clear()
    bridge.handle_host_message(_mcu_lcd(0, "DRUM   Select"))

    assert c8.encode_lcd_text(linha_nomes, 1, "Select ") not in hardware_out.sent


def test_the_leftover_of_an_erased_label_does_not_become_a_name():
    # Capturado ao vivo: pra apagar "Volume" o Logic escreve só "olume" + brancos
    # em offset 1, com 12 caracteres.
    hardware_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=FakeMidiOut(), state=ChannelState())
    linha_nomes = c8.LCD_ROW_FOR_MCU_LINE[0]

    bridge.handle_host_message(_mcu_lcd(0, _linha("VX", "GTR", "BAIXO", "TECLAD", "DRUM", "SN", "KIK", "T1")))
    hardware_out.sent.clear()
    bridge.handle_host_message(_mcu_lcd(1, "olume       "))

    assert [m for m in hardware_out.sent if m[:5] == c8.encode_lcd_text(linha_nomes, 0, "x")[:5]] == []
