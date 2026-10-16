"""Anotação legível de MIDI cru, pra engenharia reversa do protocolo nativo.

Usado por `tools/midi_spy.py`. A lógica fica aqui (testável) e o tool é só a
casca de I/O.
"""

from dataclasses import dataclass

from command8_bridge import command8_protocol

# Prefixo de SysEx da família Digidesign/Neyrinck. Duas fontes independentes
# apontam pra 0x13 (=19 decimal): o `encode_vpot_led_ring` do projeto, vindo de
# documentação de terceiros da Command|8, e o `midimap` embutido no V-Control Pro
# pras superfícies irmãs (`"sysex":"[19,64,64,...]"` = 13 40 40). Ver
# docs/re/00-SINTESE.md.
_DIGIDESIGN_SYSEX_ID = 0x13

# Cabeçalho de SysEx do Mackie Control. Se aparecer aqui, a captura está
# apontada pra porta MCU em vez da porta nativa.
_MCU_SYSEX_HEADER = [0x00, 0x00, 0x66]

_BEACON = [0x90, 0x00, 0x7F]


def format_bytes(message: list[int]) -> str:
    return " ".join(f"{byte:02X}" for byte in message)


def printable_ascii(payload: list[int]) -> str:
    return "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in payload)


def describe(message: list[int]) -> str:
    if message == _BEACON:
        return "beacon (procurando host)"

    if message and message[0] == 0xF0:
        return _describe_sysex(message)

    touch = command8_protocol.decode_fader_touch(message)
    if touch is not None:
        channel, touched = touch
        estado = "toque iniciado" if touched else "toque solto"
        return f"fader canal {channel + 1} {estado}"

    button = command8_protocol.decode_channel_button(message)
    if button is not None:
        channel, name, pressed = button
        estado = "apertado" if pressed else "solto"
        return f"botão {name.capitalize()} canal {channel + 1} {estado}"

    rotation = command8_protocol.decode_vpot_rotation(message)
    if rotation is not None:
        channel, delta = rotation
        return f"V-Pot canal {channel + 1} girou {delta:+d}"

    position = command8_protocol.decode_fader_position(message)
    if position is not None:
        channel, value = position
        return f"fader canal {channel + 1} posição {value}"

    return "? (não reconhecido)"


def _describe_sysex(message: list[int]) -> str:
    payload = message[1:-1] if message[-1:] == [0xF7] else message[1:]

    if payload[:3] == _MCU_SYSEX_HEADER:
        return _describe_mcu_sysex(payload[3:])

    if payload[:1] == [_DIGIDESIGN_SYSEX_ID]:
        return (
            f"SysEx família Digidesign/Neyrinck (0x13) · "
            f"{len(payload)} bytes · '{printable_ascii(payload[1:])}'"
        )

    return f"SysEx desconhecido · {len(payload)} bytes · '{printable_ascii(payload)}'"


def _describe_mcu_sysex(rest: list[int]) -> str:
    """`rest` começa no device ID, depois do cabeçalho 00 00 66."""
    if not rest:
        return "SysEx MCU · truncado"

    device = f"0x{rest[0]:02X}"
    body = rest[1:]

    if body == [0x00]:
        return f"SysEx MCU · device query (dev {device}) — varredura de superfície do host"
    if body == [0x13, 0x00]:
        return f"SysEx MCU · version request (dev {device})"
    if not body:
        return f"SysEx MCU · dev {device} sem opcode"
    if body[0] == 0x12:
        return (
            f"SysEx MCU · escrita de LCD (dev {device}) — porta errada? · "
            f"'{printable_ascii(body[1:])}'"
        )
    return f"SysEx MCU · dev {device} op 0x{body[0]:02X} · '{printable_ascii(body[1:])}'"


@dataclass(frozen=True)
class CollapseResult:
    emit: bool
    suppressed: int


class RepeatCollapser:
    """Colapsa mensagens idênticas consecutivas.

    Necessário porque a Command|8 manda o beacon `90 00 7F` a cada ~0.5s e o
    host manda medidor continuamente — sem isso o log afoga o que interessa.
    """

    def __init__(self) -> None:
        self._last: list[int] | None = None
        self._repeats = 0

    def feed(self, message: list[int]) -> CollapseResult:
        if message == self._last:
            self._repeats += 1
            return CollapseResult(emit=False, suppressed=0)

        suppressed = self._repeats
        self._last = list(message)
        self._repeats = 0
        return CollapseResult(emit=True, suppressed=suppressed)
