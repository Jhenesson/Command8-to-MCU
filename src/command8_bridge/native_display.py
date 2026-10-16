"""O que a ponte realmente desenhou em cada célula do visor nativo.

Existe porque o visor físico **não é cópia fiel** do visor do MCU: quando há
rótulo transitório (toque de fader, solo/mute), a ponte desvia o conteúdo pra
outra fileira pra não perder o nome da faixa.

Sem este estado, a ponte só sabia o que o *host* mandou (`LcdBuffer`) e decidia
o envio por diferença ali. Quando o host reescrevia algo com o mesmo conteúdo de
antes, o espelho dizia "não mudou" e nada era enviado — mas aquela célula podia
estar exibindo um rótulo desviado de instantes atrás, e ficava congelada no
conteúdo errado. Era a causa do visor "aleatório".
"""


class NativeDisplay:
    def __init__(self) -> None:
        self._cells: dict[tuple[int, int], str] = {}

    def set(self, row: int, strip: int, text: str) -> bool:
        """Registra o conteúdo da célula. Devolve True se mudou de fato."""
        chave = (row, strip)
        if self._cells.get(chave) == text:
            return False
        self._cells[chave] = text
        return True
