# Esquema real confirmado por captura ao vivo com o hardware (ver docs/PROTOCOL.md):
# a nota identifica o TIPO de botão (fixa, não muda por canal); a velocity
# codifica o canal (0-based) e o estado: 0x40+canal = apertar, 0x00+canal = soltar.
# A Command|8 não tem botão de Record por canal (só no transporte).
_BUTTON_TO_NOTE = {
    "select": 0x00,
    "solo": 0x02,
    "mute": 0x03,
}
_NOTE_TO_BUTTON = {note: name for name, note in _BUTTON_TO_NOTE.items()}


def decode_channel_button(message: list[int]) -> tuple[int, str, bool] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0x90:
        return None
    button = _NOTE_TO_BUTTON.get(message[1])
    if button is None:
        return None
    velocity = message[2]
    if velocity >= 0x40:
        channel, pressed = velocity - 0x40, True
    else:
        channel, pressed = velocity, False
    if not (0 <= channel <= 7):
        return None
    return channel, button, pressed


def encode_channel_button_led(channel: int, button: str, on: bool) -> list[int]:
    note = _BUTTON_TO_NOTE[button]
    velocity = (0x40 if on else 0x00) + channel
    return [0x90, note, velocity]


def decode_vpot_rotation(message: list[int]) -> tuple[int, int] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0xB0:
        return None
    cc = message[1]
    if not (0x40 <= cc <= 0x47):
        return None
    channel = cc - 0x40
    value = message[2]
    if value == 0x41:
        return channel, 1
    if value == 0x3F:
        return channel, -1
    return None


def encode_vpot_led_ring(channel: int, mask: int) -> list[int]:
    """Anel de LED do encoder, 11 LEDs:

        F0 13 01 00 <(4 LEDs altos << 3) | canal> <7 LEDs baixos> F7

    O 0x00 é o opcode de anel (o de display é 0x40). O anel tem 11 LEDs e um
    byte de dados MIDI carrega 7 bits, então os quatro restantes viajam nos bits
    altos do byte que também leva o canal. Decodificado capturando o V-Control
    Pro girar um pan de ponta a ponta (ver docs/PROTOCOL.md).

    `mask` é o bitmap de 11 bits, bit 0 = primeiro LED.
    """
    altos = (mask >> VPOT_RING_LOW_LEDS) & 0x0F
    baixos = mask & 0x7F
    return [0xF0, 0x13, 0x01, 0x00, (altos << 3) | (channel & 0x07), baixos, 0xF7]


# O último byte é BITMASK, um bit por LED — confirmado no vidro: 0x7F acende 7
# LEDs de uma vez, em barra. O anel físico tem 11 LEDs, mas um byte de dados MIDI
# só carrega 7 bits, e os LEDs restantes não se mostraram alcançáveis por este
# opcode (nem com outros endereços, nem com um segundo byte de valor — ver
# docs/PROTOCOL.md). A ponte usa a faixa de 7 que funciona.
VPOT_RING_LOW_LEDS = 7
VPOT_RING_LEDS = 11


# O LED do meio do anel de 11. É daqui que a barra de pan cresce pros dois lados.
VPOT_RING_CENTRE = 5


def vpot_ring_mask(mode: int, position: int) -> int:
    """Converte a posição do anel do MCU (0-11) no bitmap nativo de 11 LEDs.

    O MCU usa as mesmas 11 posições do anel físico: posição 0 apaga, 1-11
    acendem o LED correspondente. O modo decide o desenho:

    - 0 (ponto único): só o LED da posição
    - 2 (wrap): barra da esquerda até a posição — serve pra nível e send
    - outros (boost/cut, spread): barra a partir do CENTRO até a posição, que é
      como o pan é desenhado. Confirmado capturando o V-Control Pro girar um pan
      de ponta a ponta: todo à esquerda acende os bits 0-5, o centro só o bit 5,
      e todo à direita os bits 5-10.
    """
    position = max(0, min(VPOT_RING_LEDS, position))
    if position == 0:
        return 0

    led = position - 1
    if mode == 0:
        return 1 << led
    if mode == 2:
        return (1 << position) - 1

    inicio, fim = sorted((VPOT_RING_CENTRE, led))
    return ((1 << (fim - inicio + 1)) - 1) << inicio


# Meters: 90 <0x40 | barra de 5 bits> <canal>. A barra preenche do bit 4 pra
# baixo (0x10, 0x18, 0x1C, 0x1E, 0x1F), batendo com o numBits:5 que o binário do
# V-Control Pro declara pra Command|8.
METER_SEGMENTS = 5
_MCU_METER_MAX = 12


def encode_meter(channel: int, level: int) -> list[int]:
    level = max(0, min(METER_SEGMENTS, level))
    mask = (0x1F << (METER_SEGMENTS - level)) & 0x1F if level else 0x00
    return [0x90, 0x40 | mask, channel & 0x07]


def meter_level_from_mcu(mcu_level: int) -> int:
    return min(METER_SEGMENTS, mcu_level * METER_SEGMENTS // _MCU_METER_MAX)



# Fader: nota fixa 0x05 pra todos os canais, mesmo esquema velocity-codifica-canal
# dos botões de canal (ver PROTOCOL.md). Posição vem em CC (0xB0), canal = byte1 % 8,
# valor 0-127 = byte2 direto. Os 3 bits altos de byte1 não carregam informação de
# posição confiável (testado e descartado, ver PROTOCOL.md) — ignorados aqui.
_FADER_TOUCH_NOTE = 0x05


def decode_fader_touch(message: list[int]) -> tuple[int, bool] | None:
    if len(message) != 3 or message[0] != 0x90 or message[1] != _FADER_TOUCH_NOTE:
        return None
    velocity = message[2]
    if velocity >= 0x40:
        channel, touched = velocity - 0x40, True
    else:
        channel, touched = velocity, False
    if not (0 <= channel <= 7):
        return None
    return channel, touched


def decode_fader_position(message: list[int]) -> tuple[int, int] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0xB0:
        return None
    byte1, byte2 = message[1], message[2]
    if not (0x00 <= byte1 <= 0x3F):
        return None
    return byte1 % 8, byte2


def encode_fader_motor_position(channel: int, value_7bit: int) -> list[int]:
    """Move o motor do fader. Confirmado ao vivo: mesmo formato B0 <canal> <posição>
    usado pela leitura de posição (ver PROTOCOL.md, seção Motor)."""
    return [0xB0, channel & 0x07, value_7bit & 0x7F]


# LCD nativo. Frame capturado do V-Control Pro ao vivo e depois reproduzido por
# nós, com o texto aparecendo no visor físico (ver PROTOCOL.md, seção LCD):
#     F0 13 01 40 <célula> 7F 00 <7 × ASCII> F7
# célula = linha*0x10 + strip; linha 0 = superior, 1 = inferior; strip 0-7.
# São 7 caracteres por célula no fio — mesmo tamanho do MCU, então a tradução
# de texto é 1:1, sem truncamento.
LCD_CHARS_PER_CELL = 7

# O visor tem 4 fileiras de 8 células, e as bases NÃO são lineares — sondadas
# uma a uma no hardware em 2026-10-14. As fileiras 0 e 1 são os nomes/valores dos
# strips; 2 e 3 são a área onde o original mostra posição e modo.
LCD_ROW_BASES = (0x00, 0x10, 0x28, 0x38)

# Disposição do visor, copiando o original (V-Control Pro): contador em cima,
# nomes de faixa na linha de baixo. O MCU manda duas linhas de texto — a 0 são os
# nomes, a 1 são os valores — e aqui elas são remapeadas pras fileiras nativas.
LCD_ROW_FOR_MCU_LINE = (1, 2)

# Contador de posição: fileira de cima, duas células mais à direita (14
# caracteres, suficiente pros 10 dígitos do MCU).
LCD_TIMECODE_ROW = 0
LCD_TIMECODE_STRIPS = (6, 7)


def encode_lcd_text(row: int, strip: int, text: str) -> list[int]:
    cell = LCD_ROW_BASES[row % len(LCD_ROW_BASES)] + (strip & 0x07)
    body = text[:LCD_CHARS_PER_CELL].ljust(LCD_CHARS_PER_CELL)
    return (
        [0xF0, 0x13, 0x01, 0x40, cell, 0x7F, 0x00]
        + [ord(c) & 0x7F for c in body]
        + [0xF7]
    )


# Regiões do protocolo nativo, extraídas do binário do V-Control Pro e confirmadas
# ao vivo (ver PROTOCOL.md). A velocity de um Note On codifica a REGIÃO + estado:
# 0x40+região = apertar, 0x00+região = soltar. A nota é o índice do botão DENTRO
# da região. Os strips são as regiões 0-7, o que faz a antiga regra
# "velocity = 0x40+canal" ser só o caso particular dos botões de canal.
REGION_MODE = 10
REGION_TOP = 11
REGION_MAIN = 12
REGION_FUNCTIONS = 13
REGION_TRANSPORT = 14
REGION_FOOTSWITCH = 16
_MAX_REGION = REGION_FOOTSWITCH


def decode_button(message: list[int]) -> tuple[int, int, bool] | None:
    """Decodifica qualquer botão nativo em (região, índice, apertado).

    Vale pros botões de canal (regiões 0-7) e pros globais — transporte, Main,
    Mode, Top, Functions, Footswitch —, que `decode_channel_button` descarta por
    exigir canal 0-7.
    """
    if len(message) != 3 or message[0] != 0x90:
        return None

    velocity = message[2]
    pressed = velocity >= 0x40
    region = velocity - 0x40 if pressed else velocity
    if region > _MAX_REGION:
        return None
    return region, message[1], pressed


# Bloco de transporte, capturado ao vivo em 2026-10-14: notas consecutivas na
# região 14, na mesma ordem da fileira física. Record (0x0B) já estava documentado
# de uma sessão anterior e bate, o que valida a série inteira.
_TRANSPORT_NOTES = {
    0x06: "rtz",
    0x07: "rewind",
    0x08: "forward",
    0x09: "stop",
    0x0A: "play",
    0x0B: "record",
}


def decode_transport_button(message: list[int]) -> tuple[str, bool] | None:
    decoded = decode_button(message)
    if decoded is None:
        return None

    region, index, pressed = decoded
    if region != REGION_TRANSPORT:
        return None

    name = _TRANSPORT_NOTES.get(index)
    if name is None:
        return None
    return name, pressed

_NOTE_BY_TRANSPORT = {name: note for note, name in _TRANSPORT_NOTES.items()}


def encode_transport_led(name: str, on: bool) -> list[int]:
    velocity = (0x40 if on else 0x00) + REGION_TRANSPORT
    return [0x90, _NOTE_BY_TRANSPORT[name], velocity]


# Console View, mapeado ao vivo em 2026-10-14 apertando um botão de cada vez e
# conferindo contra três confirmações isoladas (Insert, Mon/0 e Display Mode).
# Três blocos consecutivos, seguindo a disposição física da mesa.
_MODE_BUTTONS = {
    0x00: "pan",
    0x01: "send",
    0x02: "insert",
    0x03: "a",
    0x04: "b",
    0x05: "c",
    0x06: "d",
    0x07: "e",
    0x0C: "default",
    0x0D: "mon",
}

# O Display Mode é o único do Console View fora da região Mode.
_TOP_BUTTONS = {0x08: "display"}


def decode_console_button(message: list[int]) -> tuple[str, bool] | None:
    decoded = decode_button(message)
    if decoded is None:
        return None

    region, index, pressed = decoded
    if region == REGION_MODE:
        name = _MODE_BUTTONS.get(index)
    elif region == REGION_TOP:
        name = _TOP_BUTTONS.get(index)
    else:
        return None

    if name is None:
        return None
    return name, pressed


# Mapa completo dos botões globais, levantado ao vivo em 2026-10-15 apertando um
# bloco de cada vez (ver docs/PROTOCOL.md). Quatro das cinco regiões são
# contíguas e seguem a disposição física da mesa.
#
# Substitui os mapas parciais anteriores de Console View e transporte, que viram
# fatias deste. Mantidos por compatibilidade: _MODE_BUTTONS, _TOP_BUTTONS e
# _TRANSPORT_NOTES continuam sendo a fonte dos decoders específicos.
GLOBAL_BUTTONS = {
    REGION_MODE: {
        0x00: "pan", 0x01: "send", 0x02: "insert_console",
        0x03: "a", 0x04: "b", 0x05: "c", 0x06: "d", 0x07: "e",
        0x08: "shift", 0x09: "option", 0x0A: "control", 0x0B: "command",
        0x0C: "default", 0x0D: "mon",
    },
    REGION_TOP: {
        0x00: "eq", 0x01: "dynamics", 0x02: "insert_channel",
        0x03: "pan_send_pre", 0x04: "page_left", 0x05: "page_right",
        0x06: "master_bypass", 0x07: "esc", 0x08: "display_mode",
    },
    REGION_MAIN: {
        0x00: "enter", 0x01: "undo", 0x03: "rec", 0x04: "pan_meter",
    },
    REGION_FUNCTIONS: {
        0x00: "flip", 0x01: "master_faders", 0x02: "bank", 0x03: "nudge",
        0x04: "zoom", 0x05: "left", 0x06: "right", 0x07: "up", 0x08: "down",
        0x09: "f1", 0x0A: "f2", 0x0B: "f3", 0x0C: "f4", 0x0D: "f5",
    },
    REGION_TRANSPORT: {
        0x00: "plugin", 0x01: "mix", 0x02: "edit",
        0x03: "loop_play", 0x04: "loop_record", 0x05: "quick_punch",
        0x06: "rtz", 0x07: "rewind", 0x08: "forward", 0x09: "stop",
        0x0A: "play", 0x0B: "record", 0x0C: "mem_loc",
    },
}


def decode_global_button(message: list[int]) -> tuple[str, bool] | None:
    """Decodifica qualquer botão global em (nome, apertado).

    Cobre as cinco regiões fora dos strips. Os strips (regiões 0-7) são tratados
    por `decode_channel_button` e `decode_fader_touch`.
    """
    decoded = decode_button(message)
    if decoded is None:
        return None

    region, index, pressed = decoded
    name = GLOBAL_BUTTONS.get(region, {}).get(index)
    if name is None:
        return None
    return name, pressed


_REGION_BY_GLOBAL_BUTTON = {
    nome: (regiao, nota)
    for regiao, botoes in GLOBAL_BUTTONS.items()
    for nota, nome in botoes.items()
}


def encode_global_button_led(name: str, on: bool) -> list[int]:
    """Acende/apaga o LED de um botão global.

    Mesmo formato do aperto: nota do botão, velocity = 0x40|0x00 + região.
    """
    region, note = _REGION_BY_GLOBAL_BUTTON[name]
    return [0x90, note, (0x40 if on else 0x00) + region]
