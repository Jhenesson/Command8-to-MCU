FADER_TOUCH_NOTE_BASE = 0x68  # G#7, fader 0. Fader 7 = 0x6F, master = 0x70.


def encode_fader_position(channel: int, value_14bit: int) -> list[int]:
    """Pitch Bend de 14 bits por canal. 0 = todo pra baixo, 16383 = todo pra cima."""
    value_14bit = max(0, min(16383, value_14bit))
    lsb = value_14bit & 0x7F
    msb = (value_14bit >> 7) & 0x7F
    return [0xE0 | (channel & 0x0F), lsb, msb]


def decode_fader_position(message: list[int]) -> tuple[int, int] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0xE0:
        return None
    channel = message[0] & 0x0F
    value = message[1] | (message[2] << 7)
    return channel, value


def encode_fader_touch(channel: int, touched: bool) -> list[int]:
    note = FADER_TOUCH_NOTE_BASE + channel
    velocity = 0x7F if touched else 0x00
    return [0x90, note, velocity]


BUTTON_REC = "rec"
BUTTON_SOLO = "solo"
BUTTON_MUTE = "mute"
BUTTON_SELECT = "select"

_BUTTON_BASE_NOTE = {
    BUTTON_REC: 0x00,
    BUTTON_SOLO: 0x08,
    BUTTON_MUTE: 0x10,
    BUTTON_SELECT: 0x18,
}
_NOTE_TO_BUTTON = {base: name for name, base in _BUTTON_BASE_NOTE.items()}


def encode_channel_button_led(channel: int, button: str, on: bool) -> list[int]:
    note = _BUTTON_BASE_NOTE[button] + channel
    return [0x90, note, 0x7F if on else 0x00]


def decode_channel_button(message: list[int]) -> tuple[int, str, bool] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0x90:
        return None
    note = message[1]
    if note > 0x1F:
        return None
    base = note & 0xF8
    channel = note & 0x07
    button = _NOTE_TO_BUTTON.get(base)
    if button is None:
        return None
    return channel, button, message[2] > 0


def decode_vpot_rotation(message: list[int]) -> tuple[int, int] | None:
    """Decode V-Pot rotation message. Returns (channel, delta) or None."""
    if len(message) != 3 or (message[0] & 0xF0) != 0xB0:
        return None
    cc = message[1]
    if not (0x10 <= cc <= 0x17):
        return None
    channel = cc - 0x10
    value = message[2]
    direction = -1 if value & 0x40 else 1
    magnitude = value & 0x3F
    return channel, direction * max(1, magnitude)


def encode_vpot_rotation(channel: int, delta: int) -> list[int]:
    """Encode V-Pot rotation. delta > 0 = horário, delta < 0 = anti-horário."""
    magnitude = min(0x3F, abs(delta))
    value = (0x40 if delta < 0 else 0x00) | magnitude
    return [0xB0, 0x10 + channel, value]


def encode_vpot_click(channel: int, pressed: bool) -> list[int]:
    """Encode V-Pot click (press) message."""
    note = 0x20 + channel
    return [0x90, note, 0x7F if pressed else 0x00]


def encode_vpot_led_ring(channel: int, led_on: bool, mode: int, value: int) -> list[int]:
    """Encode V-Pot LED ring message.

    Args:
        channel: 0-7
        led_on: LED on/off (bit 6)
        mode: LED mode 0-3 (bits 4-5)
        value: LED value 0-15 (bits 0-3)
    """
    cc = 0x30 + channel
    byte = (0x40 if led_on else 0x00) | ((mode & 0x03) << 4) | (value & 0x0F)
    return [0xB0, cc, byte]


MCU_SYSEX_HEADER = [0xF0, 0x00, 0x00, 0x66, 0x14]

MSG_DEVICE_QUERY = 0x00
MSG_HOST_CONNECTION_QUERY = 0x01
MSG_HOST_CONNECTION_REPLY = 0x02


def compute_challenge_response(challenge: list[int]) -> list[int]:
    """Compute challenge response for MCU device handshake.

    Args:
        challenge: 4-byte challenge from host

    Returns:
        4-byte response (all bytes masked to 0x7F)
    """
    c = challenge
    r0 = 0x7F & (c[0] + (c[1] ^ 0x0A) - c[3])
    r1 = 0x7F & ((c[2] >> 4) ^ (c[0] + c[3]))
    r2 = 0x7F & (c[3] - (c[2] << 2) ^ (c[0] | c[1]))
    r3 = 0x7F & (c[1] - c[2] + (0xF0 ^ (c[3] << 4)))
    return [r0, r1, r2, r3]


def is_host_connection_query(message: list[int]) -> bool:
    """Check if message is a host connection query (type 0x01).

    Args:
        message: Potential SysEx message

    Returns:
        True if message is a host connection query, False otherwise
    """
    if len(message) < 6:
        return False
    return message[:5] == MCU_SYSEX_HEADER and message[5] == MSG_HOST_CONNECTION_QUERY


def encode_host_connection_reply(serial: list[int], challenge: list[int]) -> list[int]:
    """Encode host connection reply message.

    Args:
        serial: Device serial number (typically 7 bytes)
        challenge: 4-byte challenge from host

    Returns:
        Complete SysEx message with reply
    """
    response = compute_challenge_response(challenge)
    return MCU_SYSEX_HEADER + [MSG_HOST_CONNECTION_REPLY] + serial + response + [0xF7]


def encode_device_query() -> list[int]:
    """Encode device query message (initial handshake).

    Returns:
        Complete SysEx message for device query
    """
    return MCU_SYSEX_HEADER + [MSG_DEVICE_QUERY, 0xF7]


MSG_LCD_TEXT = 0x12

TRANSPORT_NOTES = {
    "rewind": 91,
    "forward": 92,
    "stop": 93,
    "play": 94,
    "record": 95,
}
_NOTE_TO_TRANSPORT = {note: name for name, note in TRANSPORT_NOTES.items()}


def decode_lcd_text(message: list[int]) -> tuple[int, str] | None:
    """Decode LCD text SysEx message.

    Args:
        message: Complete SysEx message

    Returns:
        Tuple of (offset, text) or None if not an LCD text message
    """
    if len(message) < 8 or message[:5] != MCU_SYSEX_HEADER or message[5] != MSG_LCD_TEXT:
        return None
    offset = message[6]
    text_bytes = message[7:-1]
    return offset, "".join(chr(b) for b in text_bytes)


def decode_transport_button(message: list[int]) -> tuple[str, bool] | None:
    """Decode transport button message.

    Args:
        message: MIDI message (status, note, velocity)

    Returns:
        Tuple of (button_name, pressed) or None if not a transport button
    """
    if len(message) != 3 or (message[0] & 0xF0) != 0x90:
        return None
    name = _NOTE_TO_TRANSPORT.get(message[1])
    if name is None:
        return None
    return name, message[2] > 0


LCD_CHARS_PER_STRIP = 7
LCD_CHARS_PER_ROW = 56


def encode_transport_button(name: str, pressed: bool) -> list[int]:
    return [0x90, TRANSPORT_NOTES[name], 0x7F if pressed else 0x00]


# Visor de posição: CC 0x40-0x49, um dígito por CC, caractere em ASCII puro
# (confirmado por captura ao vivo do Logic — nada de codificação de 7 segmentos).
# 0x49 é o dígito mais à esquerda, 0x40 o mais à direita. O formato do Logic é
# "BBB T D TTT": compasso, tempo, divisão, ticks.
TIMECODE_CC_LEFTMOST = 0x49
TIMECODE_CC_RIGHTMOST = 0x40


def decode_timecode_digit(message: list[int]) -> tuple[int, str] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0xB0:
        return None
    cc = message[1]
    if not (TIMECODE_CC_RIGHTMOST <= cc <= TIMECODE_CC_LEFTMOST):
        return None
    return TIMECODE_CC_LEFTMOST - cc, chr(message[2])


def decode_meter(message: list[int]) -> tuple[int, int] | None:
    """Meter do MCU: D0 <(canal << 4) | nível>."""
    if len(message) != 2 or (message[0] & 0xF0) != 0xD0:
        return None
    return message[1] >> 4, message[1] & 0x0F


VPOT_RING_CC_FIRST = 0x30
VPOT_RING_CC_LAST = 0x37


def decode_vpot_led_ring(message: list[int]) -> tuple[int, int, int] | None:
    """Anel do V-Pot do MCU: CC 0x30-0x37, valor = <centro><modo 2 bits><posição>."""
    if len(message) != 3 or (message[0] & 0xF0) != 0xB0:
        return None
    cc = message[1]
    if not (VPOT_RING_CC_FIRST <= cc <= VPOT_RING_CC_LAST):
        return None
    value = message[2]
    return cc - VPOT_RING_CC_FIRST, (value >> 4) & 0x03, value & 0x0F


# Botões de atribuição e teclas de função do MCU.
#
# ⚠️ ESTES NÚMEROS AINDA NÃO FORAM VERIFICADOS CONTRA O LOGIC REAL. Vieram de
# conhecimento prévio do protocolo, não de captura. Se um botão do Console View
# não fizer nada (ou fizer a coisa errada) no Logic, é aqui que se corrige.
ASSIGNMENT_NOTES = {
    "track": 0x28,
    "send": 0x29,
    "pan": 0x2A,
    "plugin": 0x2B,
    "eq": 0x2C,
    "instrument": 0x2D,
}

FUNCTION_KEY_NOTES = {f"f{n}": 0x35 + n for n in range(1, 9)}


def encode_assignment_button(name: str, pressed: bool) -> list[int]:
    return [0x90, ASSIGNMENT_NOTES[name], 0x7F if pressed else 0x00]


def encode_function_key(name: str, pressed: bool) -> list[int]:
    return [0x90, FUNCTION_KEY_NOTES[name], 0x7F if pressed else 0x00]


# Notas nomeadas do MCU.
#
# ⚠️ AINDA NÃO VERIFICADAS CONTRA O LOGIC REAL. Vêm de conhecimento do protocolo,
# não de captura. O teste de 2026-10-14 foi inconclusivo: havia duas pontes
# rodando e a porta Command8 MCU estava duplicada, com o Logic provavelmente
# ligado à instância antiga. Se um botão não fizer nada, é aqui que se corrige —
# e vale conferir antes que só exista UMA ponte rodando.
NAMED_NOTES = {
    # atribuição
    "assign_track": 0x28,
    "assign_send": 0x29,
    "assign_pan": 0x2A,
    "assign_plugin": 0x2B,
    "assign_eq": 0x2C,
    "assign_instrument": 0x2D,
    # bancos
    "bank_left": 0x2E,
    "bank_right": 0x2F,
    "channel_left": 0x30,
    "channel_right": 0x31,
    "flip": 0x32,
    # modificadores
    "shift": 0x48,
    "option": 0x49,
    "control": 0x4A,
    "command": 0x4B,
    # utilitários
    "save": 0x52,
    "undo": 0x53,
    "cancel": 0x54,
    "enter": 0x55,
    # marcadores e modos
    "marker": 0x56,
    "nudge": 0x57,
    "cycle": 0x58,
    "drop": 0x59,
    "replace": 0x5A,
    # navegação
    "up": 0x60,
    "down": 0x61,
    "left": 0x62,
    "right": 0x63,
    "zoom": 0x64,
    "scrub": 0x65,
}
NAMED_NOTES.update(FUNCTION_KEY_NOTES)


def encode_named_button(name: str, pressed: bool) -> list[int]:
    return [0x90, NAMED_NOTES[name], 0x7F if pressed else 0x00]
