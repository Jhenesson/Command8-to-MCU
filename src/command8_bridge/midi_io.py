import rtmidi


def list_input_ports() -> list[str]:
    return rtmidi.MidiIn().get_ports()


def list_output_ports() -> list[str]:
    return rtmidi.MidiOut().get_ports()


def _find_port_index(names: list[str], substring: str) -> int:
    for i, name in enumerate(names):
        if substring in name:
            return i
    raise ValueError(f"Nenhuma porta contendo '{substring}' encontrada em {names}")


def open_input_by_name(substring: str) -> rtmidi.MidiIn:
    midi_in = rtmidi.MidiIn()
    midi_in.ignore_types(sysex=False)
    index = _find_port_index(midi_in.get_ports(), substring)
    midi_in.open_port(index)
    return midi_in


def open_output_by_name(substring: str) -> rtmidi.MidiOut:
    midi_out = rtmidi.MidiOut()
    index = _find_port_index(midi_out.get_ports(), substring)
    midi_out.open_port(index)
    return midi_out


def open_virtual_output(name: str) -> rtmidi.MidiOut:
    midi_out = rtmidi.MidiOut()
    midi_out.open_virtual_port(name)
    return midi_out


def open_virtual_input(name: str) -> rtmidi.MidiIn:
    midi_in = rtmidi.MidiIn()
    midi_in.ignore_types(sysex=False)
    midi_in.open_virtual_port(name)
    return midi_in
