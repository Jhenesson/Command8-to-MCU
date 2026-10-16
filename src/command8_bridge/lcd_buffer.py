"""Espelho dos 112 caracteres do visor do MCU.

Existe porque o host escreve em **qualquer posição**, não só no início de uma
célula: capturado do Logic, as atualizações de valor chegam nos offsets 57, 58 e
59 — no meio da célula. Sem um espelho não há como saber o que já estava lá, e a
implementação anterior simplesmente descartava essas escritas (das 66
atualizações de valor de uma captura, só 5 chegavam ao visor).

O buffer guarda o estado, aceita escrita em qualquer offset e devolve só as
células que mudaram de fato — o que também evita reescrever célula igual.
"""

CHARS_PER_CELL = 7
CELLS_PER_ROW = 8
CHARS_PER_ROW = CHARS_PER_CELL * CELLS_PER_ROW
ROWS = 2
SIZE = CHARS_PER_ROW * ROWS


class LcdBuffer:
    def __init__(self) -> None:
        self._chars = [" "] * SIZE

    def write(self, offset: int, text: str) -> list[tuple[int, int, str]]:
        """Aplica a escrita e devolve as células alteradas como (linha, strip, texto)."""
        alteradas = set()
        for i, char in enumerate(text):
            posicao = offset + i
            if posicao >= SIZE:
                break
            if self._chars[posicao] != char:
                self._chars[posicao] = char
                alteradas.add(posicao // CHARS_PER_CELL)

        celulas = []
        for indice in sorted(alteradas):
            row, strip = divmod(indice, CELLS_PER_ROW)
            inicio = indice * CHARS_PER_CELL
            celulas.append((row, strip, "".join(self._chars[inicio : inicio + CHARS_PER_CELL])))
        return celulas

    def cell(self, row: int, strip: int) -> str:
        inicio = (row * CELLS_PER_ROW + strip) * CHARS_PER_CELL
        return "".join(self._chars[inicio : inicio + CHARS_PER_CELL])
