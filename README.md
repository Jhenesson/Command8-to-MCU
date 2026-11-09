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

## Console View como MIDI CC

Com `--console-cc` (ou `COMMAND8_CONSOLE_CC=1`), os botões do Console View deixam de
virar comandos MCU e saem como Control Change na porta virtual **Command8 CC**
(canal 1, 127 ao apertar, 0 ao soltar), para você mapear à mão (Learn) no DAW:

| Botão | CC | Botão | CC |
|---|---|---|---|
| Pan | 102 | D | 108 |
| Send | 103 | E | 109 |
| Insert | 104 | Default | 110 |
| A | 105 | Mon/0 | 111 |
| B | 106 | Display Mode | 112 |
| C | 107 | | |

```bash
PYTHONPATH=src ./venv/bin/python -u -m command8_bridge.cli --console-cc
```

## Testes

```bash
./venv/bin/pytest
```

## Documentação

- `docs/PROTOCOL.md` — protocolo da Command|8
- `docs/NEXT_SESSION.md` — estado do projeto e como retomar
- `docs/superpowers/` — design e plano de implementação
