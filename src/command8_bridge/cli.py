import os
import sys
import time
from command8_bridge import midi_io
from command8_bridge import mcu_protocol as mcu
from command8_bridge.bridge import Bridge

SERIAL = [0x43, 0x38, 0x62, 0x72, 0x64, 0x67, 0x65]  # "C8brdge" arbitrário, 7 bytes

# O Logic manda mensagens de meter/status em alta frequência (várias por segundo,
# contínuas). Logar cada uma por padrão sobrecarrega o processo e atrasa o
# processamento MIDI em tempo real. Ative com COMMAND8_DEBUG=1 quando precisar
# depurar mensagem por mensagem.
DEBUG = os.environ.get("COMMAND8_DEBUG") == "1"

# Teto de insistência do Device Query. Ver comentário no laço principal.
MAX_DEVICE_QUERIES = 10


def main():
    # Abrir portas MIDI com tratamento de erros
    try:
        hardware_in = midi_io.open_input_by_name("Command8")
    except ValueError as e:
        print(f"Erro ao abrir porta de entrada do hardware: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        hardware_out = midi_io.open_output_by_name("Command8")
    except ValueError as e:
        print(f"Erro ao abrir porta de saída do hardware: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        host_out = midi_io.open_virtual_output("Command8 MCU")
    except Exception as e:
        print(f"Erro ao criar porta virtual de saída: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        host_in = midi_io.open_virtual_input("Command8 MCU")
    except Exception as e:
        print(f"Erro ao criar porta virtual de entrada: {e}", file=sys.stderr)
        sys.exit(1)

    bridge = Bridge(hardware_out=hardware_out, host_out=host_out)
    handshake_done = False
    host_respondeu = False

    def on_hardware_message(event, _data):
        message, _deltatime = event
        if DEBUG:
            print(f"[hardware->] {[hex(b) for b in message]}")
        bridge.handle_hardware_message(message)

    def on_host_message(event, _data):
        nonlocal handshake_done, host_respondeu
        message, _deltatime = event
        # Só o texto de visor conta como "o host se apresentou". Qualquer
        # mensagem não serve: medidor chega antes da apresentação, e parar ali
        # faz a ponte perder os nomes de faixa — o host só os reenvia quando
        # algo muda (troca de faixa, de banco), então ficam ausentes até você
        # mexer em alguma coisa.
        if mcu.decode_lcd_text(message) is not None:
            host_respondeu = True
        if DEBUG:
            print(f"[<-logic] {[hex(b) for b in message]}")
        if mcu.is_host_connection_query(message):
            if len(message) < 17:
                if DEBUG:
                    print("[error] handshake query muito curta, ignorando")
                return
            challenge = message[13:17]
            reply = mcu.encode_host_connection_reply(SERIAL, challenge)
            host_out.send_message(reply)
            handshake_done = True
            if DEBUG:
                print(f"[->logic] handshake reply {[hex(b) for b in reply]}")
            return
        bridge.handle_host_message(message)

    hardware_in.set_callback(on_hardware_message)
    host_in.set_callback(on_host_message)

    print("Ponte Command8 <-> MCU rodando. Ctrl+C para sair.")
    try:
        # O Device Query precisa ser mandado pela SUPERFÍCIE (nós) repetidamente até
        # o host dar sinal de vida — um envio único no início pode chegar antes do
        # Logic terminar de conectar na porta virtual recém-criada (ver PROTOCOL.md).
        #
        # Mas NÃO pode insistir pra sempre: o handshake formal nunca completa contra
        # o Logic, e cada Device Query faz ele reapresentar a superfície inteira
        # (Volume, Pan, Select, nomes, valores, strip por strip). Insistindo a cada
        # 2s, o visor nunca estabiliza — foi a causa da "oscilação aleatória" que
        # custou uma tarde de caça. Qualquer mensagem do host já prova que a conexão
        # existe, então paramos aí.
        tentativas = 0
        while not handshake_done and not host_respondeu and tentativas < MAX_DEVICE_QUERIES:
            host_out.send_message(mcu.encode_device_query())
            tentativas += 1
            time.sleep(2)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrando.")
        hardware_in.close_port()
        hardware_out.close_port()
        host_in.close_port()
        host_out.close_port()
        sys.exit(0)


if __name__ == "__main__":
    main()
