import time
from command8_bridge import midi_io


def test_open_virtual_ports_and_list_them():
    inp = midi_io.open_virtual_input("Test Bridge In")
    try:
        names = midi_io.list_output_ports()
        assert any("Test Bridge In" in n for n in names)
    finally:
        inp.close_port()


def test_virtual_loopback_send_and_receive():
    received = []
    inp = midi_io.open_virtual_input("Test Bridge In")
    inp.set_callback(lambda msg, data: received.append(msg[0]))

    out_names = midi_io.list_output_ports()
    matching = [n for n in out_names if "Test Bridge In" in n]
    assert matching, f"porta virtual não encontrada em {out_names}"

    out = midi_io.open_output_by_name("Test Bridge In")
    try:
        out.send_message([0x90, 0x40, 0x7F])
        time.sleep(0.2)
    finally:
        out.close_port()
        inp.close_port()

    assert received == [[0x90, 0x40, 0x7F]]


def test_open_input_by_name_raises_when_not_found():
    try:
        midi_io.open_input_by_name("Porta Que Nao Existe XYZ")
        assert False, "deveria ter lançado ValueError"
    except ValueError:
        pass


def test_virtual_loopback_sysex_received():
    """Test that SysEx messages are NOT filtered and are received by callback.

    This validates that ignore_types(sysex=False) is called on MidiIn instances,
    otherwise rtmidi discards all SysEx messages silently.
    """
    received = []
    inp = midi_io.open_virtual_input("Test SysEx In")
    inp.set_callback(lambda msg, data: received.append(msg[0]))

    out_names = midi_io.list_output_ports()
    matching = [n for n in out_names if "Test SysEx In" in n]
    assert matching, f"porta virtual não encontrada em {out_names}"

    out = midi_io.open_output_by_name("Test SysEx In")
    try:
        time.sleep(0.1)  # Allow any initial handshake messages to arrive
        received.clear()  # Clear any setup messages

        # Send a sample SysEx message (Digidesign/MCU header)
        sysex_msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x01, 0xF7]
        out.send_message(sysex_msg)
        time.sleep(0.2)
    finally:
        out.close_port()
        inp.close_port()

    assert len(received) >= 1, f"esperava ao menos 1 SysEx, recebeu {len(received)}: {received}"
    # The sent message should be in the received list
    assert sysex_msg in received, f"SysEx enviada não encontrada em {received}"
