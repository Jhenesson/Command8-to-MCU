"""Montagem do visor de posição do MCU.

O Logic manda a posição dígito a dígito (CC 0x40-0x49, caractere em ASCII puro —
confirmado por captura ao vivo, ver docs/PROTOCOL.md). São ~100 mensagens por
segundo durante o playback, então renderizar a cada dígito inundaria a porta MIDI.
Esta classe acumula os dígitos e libera o texto no máximo a cada `min_interval`.
"""

DIGITS = 10


class TimecodeDisplay:
    def __init__(self, min_interval: float = 0.1):
        self._chars = [" "] * DIGITS
        self._min_interval = min_interval
        self._rendered: str | None = None
        self._rendered_at: float | None = None

    def feed(self, index: int, char: str) -> None:
        if 0 <= index < DIGITS:
            self._chars[index] = char

    def text(self) -> str:
        return "".join(self._chars)

    def take_render(self, now: float) -> str | None:
        """Texto a desenhar, ou None se nada mudou ou se a última saiu cedo demais."""
        texto = self.text()
        if texto == self._rendered:
            return None
        if self._rendered_at is not None and now - self._rendered_at < self._min_interval:
            return None

        self._rendered = texto
        self._rendered_at = now
        return texto


# O MCU manda os 10 dígitos sem separador entre divisão e ticks: "684 4 2197"
# é compasso 684, tempo 4, divisão 2, ticks 197. Separar deixa legível.
_TICKS_START = 7


def format_for_display(raw: str) -> str:
    return raw[:_TICKS_START] + " " + raw[_TICKS_START:]
