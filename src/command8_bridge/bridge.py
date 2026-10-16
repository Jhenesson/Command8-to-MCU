import os
import time

from command8_bridge import command8_protocol as c8
from command8_bridge import mcu_protocol as mcu
from command8_bridge.channel_state import ChannelState
from command8_bridge import lcd_buffer
from command8_bridge.lcd_buffer import LcdBuffer
from command8_bridge.native_display import NativeDisplay
from command8_bridge.timecode import TimecodeDisplay, format_for_display


# Para onde cada botão do Console View aponta no MCU. Pan/Send/Insert têm
# equivalente direto; A-E, Default e Mon/0 eram modos de console do Pro Tools,
# sem correspondente no Logic, então viram teclas de função — que o usuário
# mapeia nas Atribuições de Controlador sem mexer em código.
# "display" fica de fora de propósito: reservado pra alternar o visor, que agora
# é nosso.
CONSOLE_TO_MCU = {
    "pan": ("assignment", "pan"),
    "send": ("assignment", "send"),
    "insert": ("assignment", "plugin"),
    "a": ("function", "f1"),
    "b": ("function", "f2"),
    "c": ("function", "f3"),
    "d": ("function", "f4"),
    "e": ("function", "f5"),
    "default": ("function", "f6"),
    "mon": ("function", "f7"),
}


# Botões globais da Command|8 que têm equivalente natural no MCU. Quem não está
# aqui não é encaminhado — são os que não têm correspondente nenhum (A-E,
# Default, Mon/0, as janelas do Pro Tools, Master Bypass) e que ficam pra um
# mapeamento personalizado depois.
GLOBAL_TO_MCU = {
    "enter": "enter",
    "undo": "undo",
    "shift": "shift",
    "option": "option",
    "control": "control",
    "command": "command",
    "flip": "flip",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "zoom": "zoom",
    "nudge": "nudge",
    # Page Left/Right viram banco de canais: a Command|8 não tem outro jeito de
    # alcançar além dos 8 faders, e banking é essencial numa superfície de 8.
    "page_left": "bank_left",
    "page_right": "bank_right",
    "pan": "assign_pan",
    "send": "assign_send",
    "insert_console": "assign_plugin",
    "eq": "assign_eq",
    "dynamics": "assign_instrument",
    "insert_channel": "assign_plugin",
    "pan_send_pre": "assign_pan",
    "loop_play": "cycle",
    "quick_punch": "drop",
    "mem_loc": "marker",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4", "f5": "f5",
}

# Console View A vira F6 pra expandir/fechar Summing Stack: o MCU não tem comando
# pra isso, então o Logic mapeia a tecla (Atribuições de Controlador). Manda só o
# aperto: com o "solto" o Logic desfazia o comando ao soltar o botão.
_SO_APERTO = {"a": "f6"}





# O visor é estreito e a unidade é óbvia pelo contexto. Trocamos por espaços em
# vez de remover pra não deslocar o que vier depois na mesma linha.
_UNIDADE_REDUNDANTE = "dB"

# Palavras que o host escreve na linha de nomes como rótulo transitório.
_ROTULOS = {"select", "volume", "mute", "muted", "solo", "pan"}


def _tem_rotulo(offset: int, text: str) -> bool:
    """Diz se alguma célula da escrita contém só um rótulo conhecido."""
    celula = lcd_buffer.CHARS_PER_CELL
    inicio = 0
    while inicio < len(text):
        fim = min(len(text), inicio + celula - (offset + inicio) % celula)
        pedaco = text[inicio:fim].strip().lower()
        # além do rótulo inteiro, o resto dele: o Logic apaga "Volume" escrevendo "olume"
        if pedaco in _ROTULOS or (len(pedaco) >= 3 and any(pedaco in r for r in _ROTULOS)):
            return True
        inicio = fim
    return False



# O Bank é modificador das setas, como no desenho original da mesa: segurando
# Bank, esquerda/direita andam um canal por vez (o Page Left/Right já pula o
# banco de 8) em vez de mover o cursor. O MCU
# não tem Bank modal (só Bank Left e Bank Right como botões próprios), então
# quem implementa o modo é a ponte — e por isso ela também precisa acender o LED
# do botão, já que o host nunca vê esse aperto.
_BANK_BUTTON = "bank"
_ARROWS_WHEN_BANKING = {"left": "channel_left", "right": "channel_right"}


# Loga cada célula escrita no visor. Ative com COMMAND8_DEBUG_LCD=1.
DEBUG_LCD = os.environ.get("COMMAND8_DEBUG_LCD") == "1"


class Bridge:
    def __init__(self, hardware_out, host_out, state: ChannelState | None = None, now=time.monotonic):
        self.hardware_out = hardware_out
        self.host_out = host_out
        self.state = state or ChannelState()
        self._now = now
        self._timecode = TimecodeDisplay()
        self._lcd = LcdBuffer()
        self._display = NativeDisplay()
        self._track_names: dict[int, str] = {}
        self._names = LcdBuffer()
        self._touched: dict[int, float] = {}
        self._bank_held = False

    def handle_hardware_message(self, message: list[int]) -> None:
        button = c8.decode_channel_button(message)
        if button is not None:
            channel, name, on = button
            if self.state.should_forward_button(channel, name, on):
                self.state.set_button_led(channel, name, on)
                self.host_out.send_message(mcu.encode_channel_button_led(channel, name, on))
            return

        transport = c8.decode_transport_button(message)
        if transport is not None:
            name, pressed = transport
            # O MCU não tem nota de Return to Zero; preferimos não mandar nada a
            # inventar um mapeamento errado. O botão fica decodificado e inerte.
            if name in mcu.TRANSPORT_NOTES:
                self.host_out.send_message(mcu.encode_transport_button(name, pressed))
            return

        global_button = c8.decode_global_button(message)
        if global_button is not None:
            name, pressed = global_button

            if name == _BANK_BUTTON:
                self._bank_held = pressed
                # o host nunca vê este aperto, então o LED é nosso
                self.hardware_out.send_message(
                    c8.encode_global_button_led(name, pressed)
                )
                return

            if self._bank_held and name in _ARROWS_WHEN_BANKING:
                name = _ARROWS_WHEN_BANKING[name]
                self.host_out.send_message(mcu.encode_named_button(name, pressed))
                return

            if name in _SO_APERTO:
                if pressed:
                    self.host_out.send_message(mcu.encode_named_button(_SO_APERTO[name], True))
                return

            alvo = GLOBAL_TO_MCU.get(name)
            if alvo is not None:
                self.host_out.send_message(mcu.encode_named_button(alvo, pressed))
            return

        rotation = c8.decode_vpot_rotation(message)
        if rotation is not None:
            channel, delta = rotation
            self.host_out.send_message(mcu.encode_vpot_rotation(channel, delta))
            return

        touch = c8.decode_fader_touch(message)
        if touch is not None:
            channel, touched = touch
            if touched:
                self._touched.setdefault(channel, self._now())
            else:
                self._touched.pop(channel, None)
            self._render()
            self.host_out.send_message(mcu.encode_fader_touch(channel, touched))
            return

        position = c8.decode_fader_position(message)
        if position is not None:
            channel, value_7bit = position
            # 0-127 (nativo) -> 0-16383 (pitch bend MCU): 127*129 == 16383 exato.
            self.host_out.send_message(mcu.encode_fader_position(channel, value_7bit * 129))
            return

    def _push(self, row: int, strip: int, text: str) -> None:
        """Manda a célula pro hardware só se o que está lá for diferente."""
        if self._display.set(row, strip, text):
            if DEBUG_LCD:
                print(f"[visor] fileira {row} coluna {strip} = {text!r}", flush=True)
            self.hardware_out.send_message(c8.encode_lcd_text(row, strip, text))

    def _render(self) -> None:
        """Calcula o conteúdo de cada célula e manda só as diferenças.

        Enquanto há rótulo transitório, a fileira de valores exibe o rótulo (que
        o host escreveu na linha de nomes) em vez do valor. O nome vem sempre do
        cache, nunca do rótulo.
        """
        for strip in range(lcd_buffer.CELLS_PER_ROW):
            self._push(c8.LCD_ROW_FOR_MCU_LINE[0], strip, self._track_names.get(strip, " " * 7))
            self._push(c8.LCD_ROW_FOR_MCU_LINE[1], strip, self._lcd.cell(1, strip))

    def _learn_names(self, offset: int, text: str) -> None:
        """Atualiza o cache de nomes a partir de uma escrita na linha de cima.

        Nome de verdade chega em escritas de mais de uma célula: o refresh da
        linha inteira (às vezes com o espaço final cortado) ou, quando os canais
        deslizam — troca de banco, pasta abrindo —, uma cabeça em offset 0 e uma
        cauda perto do fim, nenhuma com 50+ caracteres. Rótulo ("Volume",
        "Select") e valor (" -6.0dB") chegam em escritas de uma célula, ou ao lado
        de um rótulo conhecido, e ficam de fora.
        """
        if offset >= mcu.LCD_CHARS_PER_ROW or len(text) <= lcd_buffer.CHARS_PER_CELL:
            return
        if _tem_rotulo(offset, text):
            return
        if offset == 0 and len(text) > mcu.LCD_CHARS_PER_ROW - lcd_buffer.CHARS_PER_CELL:
            text = text.ljust(mcu.LCD_CHARS_PER_ROW)
        self._names.write(offset, text[: mcu.LCD_CHARS_PER_ROW - offset])
        for strip in range(lcd_buffer.CELLS_PER_ROW):
            self._track_names[strip] = self._names.cell(0, strip)

    def handle_host_message(self, message: list[int]) -> None:
        lcd = mcu.decode_lcd_text(message)
        if lcd is not None:
            offset, text = lcd
            if offset >= mcu.LCD_CHARS_PER_ROW:
                text = text.replace(_UNIDADE_REDUNDANTE, "  ")
            if DEBUG_LCD:
                print(f"[logic ] offset {offset:3} len {len(text):3} {text!r}", flush=True)
            self._lcd.write(offset, text)
            self._learn_names(offset, text)
            self._render()
            return

        meter = mcu.decode_meter(message)
        if meter is not None:
            channel, level = meter
            self.hardware_out.send_message(
                c8.encode_meter(channel, c8.meter_level_from_mcu(level))
            )
            return

        ring = mcu.decode_vpot_led_ring(message)
        if ring is not None:
            channel, mode, position = ring
            mask = c8.vpot_ring_mask(mode, position)
            if DEBUG_LCD:
                print(
                    f"[anel  ] canal {channel} modo {mode} posicao {position:2} "
                    f"-> {mask:011b}",
                    flush=True,
                )
            self.hardware_out.send_message(c8.encode_vpot_led_ring(channel, mask))
            return

        transport_led = mcu.decode_transport_button(message)
        if transport_led is not None:
            name, on = transport_led
            self.hardware_out.send_message(c8.encode_transport_led(name, on))
            return

        digit = mcu.decode_timecode_digit(message)
        if digit is not None:
            index, char = digit
            self._timecode.feed(index, char)
            texto = self._timecode.take_render(self._now())
            if texto is not None:
                texto = format_for_display(texto)
                largura = c8.LCD_CHARS_PER_CELL
                for i, strip in enumerate(c8.LCD_TIMECODE_STRIPS):
                    pedaco = texto[i * largura : (i + 1) * largura]
                    self._push(c8.LCD_TIMECODE_ROW, strip, pedaco)
            return

        button = mcu.decode_channel_button(message)
        if button is not None:
            channel, name, on = button
            self.hardware_out.send_message(c8.encode_channel_button_led(channel, name, on))
            return

        position = mcu.decode_fader_position(message)
        if position is not None:
            channel, value_14bit = position
            # Não mexer no motor de um fader que a mão está segurando: a posição
            # sobe pro host, o host devolve, e o motor brigaria com o usuário.
            if channel not in self._touched:
                # 0-16383 (pitch bend MCU) -> 0-127 (nativo): inverso exato de *129.
                self.hardware_out.send_message(
                    c8.encode_fader_motor_position(channel, value_14bit // 129)
                )
            return
