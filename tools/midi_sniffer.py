import sys
import time
from datetime import datetime

sys.path.insert(0, "src")
from command8_bridge import midi_io


def format_message(message: list[int]) -> str:
    return " ".join(f"{b:02X}" for b in message)


def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/midi_sniffer.py <trecho-do-nome-da-porta>")
        print("Portas disponíveis:", midi_io.list_input_ports())
        sys.exit(1)

    port_substring = sys.argv[1]
    midi_in = midi_io.open_input_by_name(port_substring)

    def on_message(event, _data):
        message, _deltatime = event
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"{timestamp}  {format_message(message)}", flush=True)

    midi_in.set_callback(on_message)
    print(f"Logando mensagens de '{port_substring}'. Ctrl+C para sair.", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrando.", flush=True)


if __name__ == "__main__":
    main()
