"""Sniffer bidirecional (MITM) do protocolo nativo da Command|8.

Por que existe: `tools/midi_sniffer.py` abre só uma ENTRADA, e uma *source* do
Core MIDI carrega apenas hardware→host. O que o host manda PRO hardware (texto de
LCD, LED, motor de fader) vai pra *destination*, e o Core MIDI não deixa nenhum
processo observar a saída de outro. Era por isso que nenhum SysEx aparecia nas
capturas antigas. Ver docs/re/00-SINTESE.md.

O tool espelha o dispositivo real em portas virtuais, uma perna por porta, e fica
no meio do caminho:

    host (V-Control Pro / Pro Tools)                      Command|8
      saída  ──► "Command8 Spy Porta N" ──► log ──► porta real N ──► hardware
      entrada ◄─ "Command8 Spy Porta N" ◄── log ◄── porta real N ◄── hardware

O espelho é fiel: só cria entrada virtual pra perna que tem entrada real (a
Porta 3 da Command|8 existe só como saída). Isso aumenta a chance do host adotar
as portas virtuais no automap.

Uso:
    # espelha as 3 portas (padrão)
    PYTHONPATH=src ./venv/bin/python -u tools/midi_spy.py --log captura.txt

    # só uma porta, nome virtual customizado
    PYTHONPATH=src ./venv/bin/python -u tools/midi_spy.py "Command8 Porta 1" \
        --virtual-prefix "C8 Spy Porta"

    # sem portas virtuais, só escuta hardware→host (comportamento do sniffer antigo)
    PYTHONPATH=src ./venv/bin/python -u tools/midi_spy.py --passive

No host, aponte entrada E saída pras portas "Command8 Spy Porta N". Depois
renomeie uma faixa e procure linhas `host→HW` com SysEx.
"""

import argparse
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, "src")
from command8_bridge import midi_io, spy

PORTAS_PADRAO = ["Command8 Porta 1", "Command8 Porta 2", "Command8 Porta 3"]
PREFIXO_VIRTUAL_PADRAO = "Command8 Spy Porta"


class Logger:
    def __init__(self, path: str | None):
        self._lock = threading.Lock()
        self._file = open(path, "a", encoding="utf-8") if path else None

    def line(self, text: str) -> None:
        with self._lock:
            print(text, flush=True)
            if self._file:
                self._file.write(text + "\n")
                self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()


def make_handler(rotulo: str, logger: Logger, forward_to=None):
    collapser = spy.RepeatCollapser()

    def handle(event, _data):
        message, _deltatime = event

        if forward_to is not None:
            forward_to.send_message(message)

        result = collapser.feed(message)
        if not result.emit:
            return
        if result.suppressed:
            logger.line(f"{'':12}  {'':<16}  ⟲ {result.suppressed}× repetida (suprimida)")

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        raw = spy.format_bytes(message)
        logger.line(f"{timestamp}  {rotulo:<16}  {raw:<52}  {spy.describe(message)}")

    return handle


def _tentar(abrir, nome):
    try:
        return abrir(nome)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("portas", nargs="*", default=PORTAS_PADRAO,
                        help=f"portas reais a espelhar (padrão: {', '.join(PORTAS_PADRAO)})")
    parser.add_argument("--virtual-prefix", default=PREFIXO_VIRTUAL_PADRAO,
                        help=f'prefixo dos nomes virtuais (padrão: "{PREFIXO_VIRTUAL_PADRAO}")')
    parser.add_argument("--passive", action="store_true",
                        help="só escuta hardware→host, não cria portas virtuais")
    parser.add_argument("--log", metavar="ARQUIVO", help="também grava a captura neste arquivo")
    args = parser.parse_args()

    portas = args.portas or PORTAS_PADRAO
    logger = Logger(args.log)
    abertas: list = []
    pernas = 0

    for indice, nome_real in enumerate(portas, start=1):
        curto = nome_real.split()[-1] if nome_real.split() else nome_real
        real_in = _tentar(midi_io.open_input_by_name, nome_real)
        real_out = _tentar(midi_io.open_output_by_name, nome_real)

        if real_in is None and real_out is None:
            logger.line(f"# '{nome_real}': não existe (nem entrada nem saída) — ignorada")
            continue

        if args.passive:
            if real_in is None:
                logger.line(f"# '{nome_real}': só saída, nada a escutar no modo passivo")
                if real_out:
                    real_out.close_port()
                continue
            real_in.set_callback(make_handler(f"HW→host {curto}", logger))
            abertas.append(real_in)
            if real_out:
                real_out.close_port()
            pernas += 1
            continue

        nome_virtual = f"{args.virtual_prefix} {indice}"

        if real_out is not None:
            virtual_in = midi_io.open_virtual_input(nome_virtual)
            virtual_in.set_callback(make_handler(f"host→HW {curto}", logger, forward_to=real_out))
            abertas += [real_out, virtual_in]

        if real_in is not None:
            virtual_out = midi_io.open_virtual_output(nome_virtual)
            real_in.set_callback(make_handler(f"HW→host {curto}", logger, forward_to=virtual_out))
            abertas += [real_in, virtual_out]

        direcoes = []
        if real_out is not None:
            direcoes.append("host→HW")
        if real_in is not None:
            direcoes.append("HW→host")
        logger.line(f"# perna: '{nome_real}' ⇄ '{nome_virtual}'  ({', '.join(direcoes)})")
        pernas += 1

    if pernas == 0:
        print("Erro: nenhuma porta encontrada.", file=sys.stderr)
        print(f"Entradas: {midi_io.list_input_ports()}", file=sys.stderr)
        print(f"Saídas:   {midi_io.list_output_ports()}", file=sys.stderr)
        logger.close()
        return 1

    if args.passive:
        logger.line("# modo passivo — só hardware→host. Ctrl+C pra sair.")
    else:
        logger.line(f"# No host, aponte entrada E saída pras portas '{args.virtual_prefix} N'.")
        logger.line("# Depois renomeie uma faixa e procure linhas 'host→HW' com SysEx.")
        logger.line("# Ctrl+C pra sair.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.line("# encerrando.")
    finally:
        for porta in abertas:
            porta.close_port()
        logger.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
