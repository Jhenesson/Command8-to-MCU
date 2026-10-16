# Command8 to MCU

Ponte que traduz o protocolo nativo da controladora **Digidesign Command|8** para o
protocolo **Mackie Control Universal (MCU)**, permitindo usá-la no Logic Pro sem o
V-Control Pro.

## Como funciona

A ponte abre a porta MIDI "Command8" do hardware e publica uma porta virtual
**Command8 MCU**. No Logic Pro, adicione uma superfície *Mackie Control* usando
essa porta como entrada e saída.

Validado ao vivo: nomes de faixa no visor, Select/Solo/Mute, faders motorizados e
transporte (Play/Stop/Record).

## Instalação

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Uso

```bash
PYTHONPATH=src ./venv/bin/python -u -m command8_bridge.cli
```

Defina `COMMAND8_DEBUG=1` para logar cada mensagem MIDI.

## Testes

```bash
./venv/bin/pytest
```

## Documentação

- `docs/PROTOCOL.md` — protocolo da Command|8
- `docs/NEXT_SESSION.md` — estado do projeto e como retomar
- `docs/superpowers/` — design e plano de implementação
