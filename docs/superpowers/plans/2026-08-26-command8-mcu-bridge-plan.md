# Ponte Command|8 → MCU (Fase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a infraestrutura completa de MIDI I/O, o protocolo MCU completo, e a
tradução bidirecional das partes do protocolo nativo da Command|8 já conhecidas (botões
Mute/Solo/Select e V-Pots/encoders) — entregando uma ponte parcial já funcional no Logic
Pro — e conduzir a sessão de descoberta guiada que vai gerar os dados para uma Fase 2
(fader, LCD/nome de faixa, transporte).

**Architecture:** Três módulos puros e testáveis sem hardware (`mcu_protocol.py`,
`command8_protocol.py`, `channel_state.py`), um módulo de I/O real (`midi_io.py`) testável
via portas virtuais de loopback, e um orquestrador (`bridge.py`) que os conecta. Um script
`tools/midi_sniffer.py` separado dá suporte à sessão de descoberta.

**Tech Stack:** Python 3.11+, `python-rtmidi` (CoreMIDI), `pytest`.

**Spec:** [docs/superpowers/specs/2026-08-26-command8-mcu-bridge-design.md](../specs/2026-08-26-command8-mcu-bridge-design.md)

## Global Constraints

- Sem acesso USB/HID bruto (libusb) — tudo via MIDI padrão (`python-rtmidi`/CoreMIDI),
  conforme confirmado empiricamente no spec.
- Nenhuma dependência do V-Control Pro ou de qualquer processo Neyrinck em tempo de
  execução — a ponte deve funcionar com o V-Control Pro completamente desinstalado.
- Cabeçalho SysEx MCU: `F0 00 00 66 14 <tipo> ... F7` (fabricante Mackie `00 00 66`,
  modelo MCU `14`).
- Todo módulo de tradução pura (`mcu_protocol.py`, `command8_protocol.py`,
  `channel_state.py`) deve ser 100% testável sem hardware conectado.

---

## Mapeamento de arquivos

```
Command8/
  requirements.txt
  src/command8_bridge/
    __init__.py
    midi_io.py            # wrapper fino sobre rtmidi: listar/abrir/fechar portas
    mcu_protocol.py        # encode/decode puro do protocolo MCU
    command8_protocol.py   # encode/decode puro do protocolo nativo (subconjunto conhecido)
    channel_state.py       # estado por canal + supressão de eco/feedback
    bridge.py              # orquestrador: hardware <-> state <-> porta MCU virtual
    cli.py                 # `python -m command8_bridge` roda a ponte com hardware real
  tools/
    midi_sniffer.py         # logger bruto de MIDI para a sessão de descoberta
  tests/
    test_mcu_protocol.py
    test_command8_protocol.py
    test_channel_state.py
    test_midi_io.py
    test_bridge.py
  docs/
    PROTOCOL.md             # preenchido durante a Tarefa 9
```

---

### Task 1: Scaffolding do projeto

**Files:**
- Create: `requirements.txt`
- Create: `src/command8_bridge/__init__.py`
- Create: `pytest.ini`

**Interfaces:**
- Produces: ambiente virtual `venv/` com `python-rtmidi` e `pytest` instalados;
  `pytest.ini` configurando `pythonpath = src`.

- [ ] **Passo 1: Criar estrutura de pastas**

```bash
cd "/Volumes/arquivos/CLAUDE/Command8"
mkdir -p src/command8_bridge tools tests docs
touch src/command8_bridge/__init__.py
```

- [ ] **Passo 2: Criar `requirements.txt`**

```
python-rtmidi>=1.5.8
pytest>=8.0.0
```

- [ ] **Passo 3: Criar venv e instalar dependências**

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

- [ ] **Passo 4: Criar `pytest.ini`**

```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Passo 5: Rodar pytest vazio para confirmar configuração**

Run: `./venv/bin/pytest`
Expected: `no tests ran` (sem erro de import/config)

- [ ] **Passo 6: Commit**

```bash
git add requirements.txt pytest.ini src/command8_bridge/__init__.py .gitignore
git commit -m "chore: scaffold project structure"
```

(Antes do commit, criar `.gitignore` com `venv/`, `__pycache__/`, `*.pyc`.)

---

### Task 2: Protocolo MCU — faders e toque

**Files:**
- Create: `src/command8_bridge/mcu_protocol.py`
- Test: `tests/test_mcu_protocol.py`

**Interfaces:**
- Produces:
  - `encode_fader_position(channel: int, value_14bit: int) -> list[int]`
  - `decode_fader_position(message: list[int]) -> tuple[int, int] | None`
  - `encode_fader_touch(channel: int, touched: bool) -> list[int]`
  - `FADER_TOUCH_NOTE_BASE = 0x68`

- [ ] **Passo 1: Escrever teste que falha**

```python
# tests/test_mcu_protocol.py
from command8_bridge import mcu_protocol as mcu


def test_encode_fader_position_channel_0_min():
    assert mcu.encode_fader_position(0, 0) == [0xE0, 0x00, 0x00]


def test_encode_fader_position_channel_0_max():
    # 16383 = 0x3FFF -> LSB 0x7F, MSB 0x7F
    assert mcu.encode_fader_position(0, 16383) == [0xE0, 0x7F, 0x7F]


def test_encode_fader_position_channel_7_mid():
    # 8192 = 0x2000 -> LSB 0x00, MSB 0x40
    assert mcu.encode_fader_position(7, 8192) == [0xE7, 0x00, 0x40]


def test_decode_fader_position_roundtrip():
    msg = mcu.encode_fader_position(3, 12000)
    assert mcu.decode_fader_position(msg) == (3, 12000)


def test_decode_fader_position_ignores_non_pitchbend():
    assert mcu.decode_fader_position([0x90, 0x40, 0x7F]) is None


def test_encode_fader_touch_pressed():
    assert mcu.encode_fader_touch(0, True) == [0x90, 0x68, 0x7F]


def test_encode_fader_touch_released_channel_7():
    assert mcu.encode_fader_touch(7, False) == [0x90, 0x6F, 0x00]
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: FAIL (`ModuleNotFoundError` ou `AttributeError`)

- [ ] **Passo 3: Implementar**

```python
# src/command8_bridge/mcu_protocol.py

FADER_TOUCH_NOTE_BASE = 0x68  # G#7, fader 0. Fader 7 = 0x6F, master = 0x70.


def encode_fader_position(channel: int, value_14bit: int) -> list[int]:
    """Pitch Bend de 14 bits por canal. 0 = todo pra baixo, 16383 = todo pra cima."""
    value_14bit = max(0, min(16383, value_14bit))
    lsb = value_14bit & 0x7F
    msb = (value_14bit >> 7) & 0x7F
    return [0xE0 | (channel & 0x0F), lsb, msb]


def decode_fader_position(message: list[int]) -> tuple[int, int] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0xE0:
        return None
    channel = message[0] & 0x0F
    value = message[1] | (message[2] << 7)
    return channel, value


def encode_fader_touch(channel: int, touched: bool) -> list[int]:
    note = FADER_TOUCH_NOTE_BASE + channel
    velocity = 0x7F if touched else 0x00
    return [0x90, note, velocity]
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: PASS (7 testes)

- [ ] **Passo 5: Commit**

```bash
git add src/command8_bridge/mcu_protocol.py tests/test_mcu_protocol.py
git commit -m "feat: MCU fader position and touch encode/decode"
```

---

### Task 3: Protocolo MCU — botões de canal (REC/SOLO/MUTE/SELECT)

**Files:**
- Modify: `src/command8_bridge/mcu_protocol.py`
- Modify: `tests/test_mcu_protocol.py`

**Interfaces:**
- Consumes: nenhuma (módulo independente dentro do mesmo arquivo)
- Produces:
  - `ChannelButton` enum-like constants: `BUTTON_REC`, `BUTTON_SOLO`, `BUTTON_MUTE`, `BUTTON_SELECT`
  - `encode_channel_button_led(channel: int, button: str, on: bool) -> list[int]`
  - `decode_channel_button(message: list[int]) -> tuple[int, str, bool] | None`

- [ ] **Passo 1: Escrever teste que falha**

```python
def test_encode_mute_led_on_channel_0():
    assert mcu.encode_channel_button_led(0, mcu.BUTTON_MUTE, True) == [0x90, 0x10, 0x7F]


def test_encode_select_led_off_channel_7():
    assert mcu.encode_channel_button_led(7, mcu.BUTTON_SELECT, False) == [0x90, 0x1F, 0x00]


def test_decode_rec_button_channel_3():
    assert mcu.decode_channel_button([0x90, 0x03, 0x7F]) == (3, mcu.BUTTON_REC, True)


def test_decode_solo_button_channel_5_release():
    assert mcu.decode_channel_button([0x90, 0x0D, 0x00]) == (5, mcu.BUTTON_SOLO, False)


def test_decode_channel_button_ignores_out_of_range():
    assert mcu.decode_channel_button([0x90, 0x60, 0x7F]) is None
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: FAIL (`AttributeError`)

- [ ] **Passo 3: Implementar**

```python
# adicionar em src/command8_bridge/mcu_protocol.py

BUTTON_REC = "rec"
BUTTON_SOLO = "solo"
BUTTON_MUTE = "mute"
BUTTON_SELECT = "select"

_BUTTON_BASE_NOTE = {
    BUTTON_REC: 0x00,
    BUTTON_SOLO: 0x08,
    BUTTON_MUTE: 0x10,
    BUTTON_SELECT: 0x18,
}
_NOTE_TO_BUTTON = {base: name for name, base in _BUTTON_BASE_NOTE.items()}


def encode_channel_button_led(channel: int, button: str, on: bool) -> list[int]:
    note = _BUTTON_BASE_NOTE[button] + channel
    return [0x90, note, 0x7F if on else 0x00]


def decode_channel_button(message: list[int]) -> tuple[int, str, bool] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0x90:
        return None
    note = message[1]
    if note > 0x1F:
        return None
    base = note & 0xF8
    channel = note & 0x07
    button = _NOTE_TO_BUTTON.get(base)
    if button is None:
        return None
    return channel, button, message[2] > 0
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: PASS

- [ ] **Passo 5: Commit**

```bash
git add src/command8_bridge/mcu_protocol.py tests/test_mcu_protocol.py
git commit -m "feat: MCU channel button encode/decode"
```

---

### Task 4: Protocolo MCU — V-Pot (rotação, clique, anel de LED)

**Files:**
- Modify: `src/command8_bridge/mcu_protocol.py`
- Modify: `tests/test_mcu_protocol.py`

**Interfaces:**
- Produces:
  - `decode_vpot_rotation(message: list[int]) -> tuple[int, int] | None` (retorna canal e delta: +1 ou -1, podendo escalar para giros rápidos)
  - `encode_vpot_click(channel: int, pressed: bool) -> list[int]`
  - `encode_vpot_led_ring(channel: int, led_on: bool, mode: int, value: int) -> list[int]`

- [ ] **Passo 1: Escrever teste que falha**

```python
def test_decode_vpot_rotation_clockwise():
    assert mcu.decode_vpot_rotation([0xB0, 0x10, 0x01]) == (0, 1)


def test_decode_vpot_rotation_counterclockwise_channel_7():
    assert mcu.decode_vpot_rotation([0xB0, 0x17, 0x41]) == (7, -1)


def test_decode_vpot_rotation_ignores_non_cc():
    assert mcu.decode_vpot_rotation([0x90, 0x10, 0x01]) is None


def test_encode_vpot_click_channel_2():
    assert mcu.encode_vpot_click(2, True) == [0x90, 0x22, 0x7F]


def test_encode_vpot_led_ring_channel_0():
    # led_on=True (bit6), mode=0b01, value=0b0101
    result = mcu.encode_vpot_led_ring(0, True, 0b01, 0b0101)
    assert result == [0xB0, 0x30, 0b01010101]


def test_encode_vpot_led_ring_channel_7_off():
    result = mcu.encode_vpot_led_ring(7, False, 0b00, 0b0000)
    assert result == [0xB0, 0x37, 0b00000000]
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: FAIL

- [ ] **Passo 3: Implementar**

```python
# adicionar em src/command8_bridge/mcu_protocol.py

def decode_vpot_rotation(message: list[int]) -> tuple[int, int] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0xB0:
        return None
    cc = message[1]
    if not (0x10 <= cc <= 0x17):
        return None
    channel = cc - 0x10
    value = message[2]
    direction = -1 if value & 0x40 else 1
    magnitude = value & 0x3F
    return channel, direction * max(1, magnitude)


def encode_vpot_click(channel: int, pressed: bool) -> list[int]:
    note = 0x20 + channel
    return [0x90, note, 0x7F if pressed else 0x00]


def encode_vpot_led_ring(channel: int, led_on: bool, mode: int, value: int) -> list[int]:
    cc = 0x30 + channel
    byte = (0x40 if led_on else 0x00) | ((mode & 0x03) << 4) | (value & 0x0F)
    return [0xB0, cc, byte]
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: PASS

- [ ] **Passo 5: Commit**

```bash
git add src/command8_bridge/mcu_protocol.py tests/test_mcu_protocol.py
git commit -m "feat: MCU V-Pot rotation, click and LED ring encode/decode"
```

---

### Task 5: Protocolo MCU — handshake de dispositivo

**Files:**
- Modify: `src/command8_bridge/mcu_protocol.py`
- Modify: `tests/test_mcu_protocol.py`

**Interfaces:**
- Produces:
  - `compute_challenge_response(challenge: list[int]) -> list[int]`
  - `is_host_connection_query(message: list[int]) -> bool`
  - `encode_host_connection_reply(serial: list[int], challenge: list[int]) -> list[int]`
  - `encode_device_query() -> list[int]`

**Nota de risco:** os bytes exatos de tipo de mensagem (`0x00`-`0x04`) seguem a
convenção mais comumente documentada, mas **não foram validados contra uma captura
real do Logic Pro**. A Tarefa 8 (teste manual com hardware) inclui validar/ajustar
esses valores observando o tráfego real via `tools/midi_sniffer.py` na porta virtual.

- [ ] **Passo 1: Escrever teste que falha**

```python
def test_compute_challenge_response_known_vector():
    # Vetor de teste construído a partir da fórmula documentada publicamente
    # (não é uma captura real do Logic — serve para travar o comportamento da função).
    challenge = [0x10, 0x20, 0x30, 0x40]
    response = mcu.compute_challenge_response(challenge)
    assert len(response) == 4
    assert all(0 <= b <= 0x7F for b in response)
    # Determinístico: mesma entrada, mesma saída
    assert mcu.compute_challenge_response(challenge) == response


def test_compute_challenge_response_matches_formula():
    c = [0x01, 0x02, 0x03, 0x04]
    r = mcu.compute_challenge_response(c)
    assert r[0] == (0x7F & (c[0] + (c[1] ^ 0x0A) - c[3]))
    assert r[1] == (0x7F & ((c[2] >> 4) ^ (c[0] + c[3])))
    assert r[2] == (0x7F & (c[3] - (c[2] << 2) ^ (c[0] | c[1])))
    assert r[3] == (0x7F & (c[1] - c[2] + (0xF0 ^ (c[3] << 4))))


def test_is_host_connection_query_true():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x01] + [0] * 7 + [1, 2, 3, 4] + [0xF7]
    assert mcu.is_host_connection_query(msg) is True


def test_is_host_connection_query_false_for_other_sysex():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00, 0xF7]
    assert mcu.is_host_connection_query(msg) is False


def test_encode_host_connection_reply_structure():
    serial = [1, 2, 3, 4, 5, 6, 7]
    challenge = [0x10, 0x20, 0x30, 0x40]
    msg = mcu.encode_host_connection_reply(serial, challenge)
    assert msg[:6] == [0xF0, 0x00, 0x00, 0x66, 0x14, 0x02]
    assert msg[6:13] == serial
    assert msg[13:17] == mcu.compute_challenge_response(challenge)
    assert msg[-1] == 0xF7


def test_encode_device_query():
    assert mcu.encode_device_query() == [0xF0, 0x00, 0x00, 0x66, 0x14, 0x00, 0xF7]
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: FAIL

- [ ] **Passo 3: Implementar**

```python
# adicionar em src/command8_bridge/mcu_protocol.py

MCU_SYSEX_HEADER = [0xF0, 0x00, 0x00, 0x66, 0x14]

MSG_DEVICE_QUERY = 0x00
MSG_HOST_CONNECTION_QUERY = 0x01
MSG_HOST_CONNECTION_REPLY = 0x02


def compute_challenge_response(challenge: list[int]) -> list[int]:
    c = challenge
    r0 = 0x7F & (c[0] + (c[1] ^ 0x0A) - c[3])
    r1 = 0x7F & ((c[2] >> 4) ^ (c[0] + c[3]))
    r2 = 0x7F & (c[3] - (c[2] << 2) ^ (c[0] | c[1]))
    r3 = 0x7F & (c[1] - c[2] + (0xF0 ^ (c[3] << 4)))
    return [r0, r1, r2, r3]


def is_host_connection_query(message: list[int]) -> bool:
    if len(message) < 6:
        return False
    return message[:5] == MCU_SYSEX_HEADER and message[5] == MSG_HOST_CONNECTION_QUERY


def encode_host_connection_reply(serial: list[int], challenge: list[int]) -> list[int]:
    response = compute_challenge_response(challenge)
    return MCU_SYSEX_HEADER + [MSG_HOST_CONNECTION_REPLY] + serial + response + [0xF7]


def encode_device_query() -> list[int]:
    return MCU_SYSEX_HEADER + [MSG_DEVICE_QUERY, 0xF7]
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Passo 5: Commit**

```bash
git add src/command8_bridge/mcu_protocol.py tests/test_mcu_protocol.py
git commit -m "feat: MCU device handshake (challenge-response, device query)"
```

---

### Task 6: Protocolo MCU — LCD (scribble strip) e transporte

**Files:**
- Modify: `src/command8_bridge/mcu_protocol.py`
- Modify: `tests/test_mcu_protocol.py`

**Interfaces:**
- Produces:
  - `decode_lcd_text(message: list[int]) -> tuple[int, str] | None` (offset, texto)
  - `TRANSPORT_NOTES = {"rewind": 91, "forward": 92, "stop": 93, "play": 94, "record": 95}`
  - `decode_transport_button(message: list[int]) -> tuple[str, bool] | None`

- [ ] **Passo 1: Escrever teste que falha**

```python
def test_decode_lcd_text_basic():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00] + [ord(c) for c in "Kick  "] + [0xF7]
    assert mcu.decode_lcd_text(msg) == (0, "Kick  ")


def test_decode_lcd_text_offset_second_channel():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x07] + [ord(c) for c in "Snare "] + [0xF7]
    assert mcu.decode_lcd_text(msg) == (7, "Snare ")


def test_decode_lcd_text_ignores_other_sysex():
    msg = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x00, 0xF7]
    assert mcu.decode_lcd_text(msg) is None


def test_decode_transport_play():
    assert mcu.decode_transport_button([0x90, 94, 0x7F]) == ("play", True)


def test_decode_transport_stop_release():
    assert mcu.decode_transport_button([0x90, 93, 0x00]) == ("stop", False)


def test_decode_transport_ignores_unrelated_note():
    assert mcu.decode_transport_button([0x90, 50, 0x7F]) is None
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: FAIL

- [ ] **Passo 3: Implementar**

```python
# adicionar em src/command8_bridge/mcu_protocol.py

MSG_LCD_TEXT = 0x12

TRANSPORT_NOTES = {
    "rewind": 91,
    "forward": 92,
    "stop": 93,
    "play": 94,
    "record": 95,
}
_NOTE_TO_TRANSPORT = {note: name for name, note in TRANSPORT_NOTES.items()}


def decode_lcd_text(message: list[int]) -> tuple[int, str] | None:
    if len(message) < 8 or message[:5] != MCU_SYSEX_HEADER or message[5] != MSG_LCD_TEXT:
        return None
    offset = message[6]
    text_bytes = message[7:-1]
    return offset, "".join(chr(b) for b in text_bytes)


def decode_transport_button(message: list[int]) -> tuple[str, bool] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0x90:
        return None
    name = _NOTE_TO_TRANSPORT.get(message[1])
    if name is None:
        return None
    return name, message[2] > 0
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_mcu_protocol.py -v`
Expected: PASS

- [ ] **Passo 5: Commit**

```bash
git add src/command8_bridge/mcu_protocol.py tests/test_mcu_protocol.py
git commit -m "feat: MCU LCD text decode and transport buttons"
```

---

### Task 7: Protocolo nativo Command|8 (subconjunto conhecido: botões e V-Pots)

**Files:**
- Create: `src/command8_bridge/command8_protocol.py`
- Test: `tests/test_command8_protocol.py`

**Interfaces:**
- Produces:
  - `decode_channel_button(message: list[int]) -> tuple[int, str, bool] | None` (mesmas
    strings de botão de `mcu_protocol`: `"mute"`, `"solo"`, `"select"`)
  - `encode_channel_button_led(channel: int, button: str, on: bool) -> list[int]`
  - `decode_vpot_rotation(message: list[int]) -> tuple[int, int] | None`
  - `encode_vpot_led_ring(channel: int, mask: int) -> list[int]`

**Nota:** os valores abaixo vêm da documentação pública do repositório
`neyrinckaudio/command8` (testes via WebMIDI feitos pela própria fabricante do
V-Control Pro) — ainda não confirmados fisicamente no hardware do usuário. A Tarefa 8
inclui essa confirmação. Se os testes manuais mostrarem valores diferentes, ajustar
este módulo (é código isolado, uma função por vez).

- [ ] **Passo 1: Escrever teste que falha**

```python
# tests/test_command8_protocol.py
from command8_bridge import command8_protocol as c8


def test_decode_mute_button_note_on():
    # Nota exata a confirmar na Tarefa 8; usamos por ora o mesmo layout MCU
    # (blocos de 8), ponto de partida documentado como "número de nota único por botão"
    assert c8.decode_channel_button([0x90, 0x10, 0x7F]) == (0, "mute", True)


def test_decode_select_button_release():
    assert c8.decode_channel_button([0x90, 0x1F, 0x00]) == (7, "select", False)


def test_encode_channel_button_led_echo():
    # LED liga/desliga via eco da própria nota (confirmado no repositório neyrinckaudio)
    assert c8.encode_channel_button_led(2, "mute", True) == [0x90, 0x12, 0x7F]


def test_decode_vpot_rotation_clockwise():
    # CC 64-71 (0x40-0x47), valor 0x41 (65) = sentido horário
    assert c8.decode_vpot_rotation([0xB0, 0x40, 0x41]) == (0, 1)


def test_decode_vpot_rotation_counterclockwise_channel_3():
    # valor 0x3F (63) = sentido anti-horário
    assert c8.decode_vpot_rotation([0xB0, 0x43, 0x3F]) == (3, -1)


def test_decode_vpot_rotation_ignores_out_of_range_cc():
    assert c8.decode_vpot_rotation([0xB0, 0x10, 0x41]) is None


def test_encode_vpot_led_ring_channel_1():
    assert c8.encode_vpot_led_ring(1, 0b01010101) == [0xF0, 0x13, 0x01, 0x01, 0b01010101, 0xF7]
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_command8_protocol.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Passo 3: Implementar**

```python
# src/command8_bridge/command8_protocol.py

_BUTTON_BASE_NOTE = {
    "mute": 0x10,
    "solo": 0x08,
    "select": 0x18,
}
_NOTE_TO_BUTTON = {base: name for name, base in _BUTTON_BASE_NOTE.items()}


def decode_channel_button(message: list[int]) -> tuple[int, str, bool] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0x90:
        return None
    note = message[1]
    base = note & 0xF8
    channel = note & 0x07
    button = _NOTE_TO_BUTTON.get(base)
    if button is None:
        return None
    return channel, button, message[2] > 0


def encode_channel_button_led(channel: int, button: str, on: bool) -> list[int]:
    note = _BUTTON_BASE_NOTE[button] + channel
    return [0x90, note, 0x7F if on else 0x00]


def decode_vpot_rotation(message: list[int]) -> tuple[int, int] | None:
    if len(message) != 3 or (message[0] & 0xF0) != 0xB0:
        return None
    cc = message[1]
    if not (0x40 <= cc <= 0x47):
        return None
    channel = cc - 0x40
    value = message[2]
    if value == 0x41:
        return channel, 1
    if value == 0x3F:
        return channel, -1
    return None


def encode_vpot_led_ring(channel: int, mask: int) -> list[int]:
    return [0xF0, 0x13, 0x01, channel, mask & 0xFF, 0xF7]
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_command8_protocol.py -v`
Expected: PASS

- [ ] **Passo 5: Commit**

```bash
git add src/command8_bridge/command8_protocol.py tests/test_command8_protocol.py
git commit -m "feat: Command8 native protocol subset (buttons, V-Pot)"
```

---

### Task 8: Estado de canal e supressão de eco

**Files:**
- Create: `src/command8_bridge/channel_state.py`
- Test: `tests/test_channel_state.py`

**Interfaces:**
- Consumes: nenhuma (módulo independente)
- Produces:
  - `class ChannelState` com `num_channels: int`, `set_button_led(channel, button, on)`,
    `get_button_led(channel, button) -> bool`, `should_forward_button(channel, button, on) -> bool`
    (retorna `False` se o estado já é igual, evitando eco infinito hardware→MCU→hardware)

- [ ] **Passo 1: Escrever teste que falha**

```python
# tests/test_channel_state.py
from command8_bridge.channel_state import ChannelState


def test_initial_led_state_is_off():
    state = ChannelState(num_channels=8)
    assert state.get_button_led(0, "mute") is False


def test_set_and_get_button_led():
    state = ChannelState(num_channels=8)
    state.set_button_led(2, "solo", True)
    assert state.get_button_led(2, "solo") is True


def test_should_forward_button_true_on_change():
    state = ChannelState(num_channels=8)
    assert state.should_forward_button(0, "mute", True) is True


def test_should_forward_button_false_when_unchanged():
    state = ChannelState(num_channels=8)
    state.set_button_led(0, "mute", True)
    assert state.should_forward_button(0, "mute", True) is False


def test_should_forward_button_true_after_real_change():
    state = ChannelState(num_channels=8)
    state.set_button_led(0, "mute", True)
    assert state.should_forward_button(0, "mute", False) is True
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_channel_state.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Passo 3: Implementar**

```python
# src/command8_bridge/channel_state.py

class ChannelState:
    def __init__(self, num_channels: int = 8):
        self.num_channels = num_channels
        self._button_leds: dict[tuple[int, str], bool] = {}

    def get_button_led(self, channel: int, button: str) -> bool:
        return self._button_leds.get((channel, button), False)

    def set_button_led(self, channel: int, button: str, on: bool) -> None:
        self._button_leds[(channel, button)] = on

    def should_forward_button(self, channel: int, button: str, on: bool) -> bool:
        current = self.get_button_led(channel, button)
        return current != on
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_channel_state.py -v`
Expected: PASS

- [ ] **Passo 5: Commit**

```bash
git add src/command8_bridge/channel_state.py tests/test_channel_state.py
git commit -m "feat: per-channel state with echo suppression"
```

---

### Task 9: I/O MIDI real (wrapper rtmidi) com teste por loopback virtual

**Files:**
- Create: `src/command8_bridge/midi_io.py`
- Test: `tests/test_midi_io.py`

**Interfaces:**
- Consumes: nenhuma
- Produces:
  - `list_input_ports() -> list[str]`
  - `list_output_ports() -> list[str]`
  - `open_input_by_name(substring: str) -> rtmidi.MidiIn` (lança `ValueError` se não achar)
  - `open_output_by_name(substring: str) -> rtmidi.MidiOut`
  - `open_virtual_output(name: str) -> rtmidi.MidiOut`
  - `open_virtual_input(name: str) -> rtmidi.MidiIn`

**Nota:** este teste depende do CoreMIDI real (portas virtuais), não de hardware físico
— roda em qualquer Mac, sem a Command|8 conectada.

- [ ] **Passo 1: Escrever teste que falha**

```python
# tests/test_midi_io.py
import time
from command8_bridge import midi_io


def test_open_virtual_ports_and_list_them():
    out = midi_io.open_virtual_output("Test Bridge Out")
    try:
        names = midi_io.list_output_ports()
        assert any("Test Bridge Out" in n for n in names)
    finally:
        out.close_port()


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
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_midi_io.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Passo 3: Implementar**

```python
# src/command8_bridge/midi_io.py
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
    midi_in.open_virtual_port(name)
    return midi_in
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_midi_io.py -v`
Expected: PASS (3 testes)

- [ ] **Passo 5: Commit**

```bash
git add src/command8_bridge/midi_io.py tests/test_midi_io.py
git commit -m "feat: rtmidi I/O wrapper with virtual loopback tests"
```

---

### Task 10: Orquestrador (bridge) — botões e V-Pots, ponta a ponta

**Files:**
- Create: `src/command8_bridge/bridge.py`
- Test: `tests/test_bridge.py`

**Interfaces:**
- Consumes:
  - `command8_protocol.decode_channel_button`, `.encode_channel_button_led`,
    `.decode_vpot_rotation`
  - `mcu_protocol.encode_channel_button_led`, `.decode_channel_button`,
    `.encode_vpot_led_ring`
  - `channel_state.ChannelState.should_forward_button`, `.set_button_led`
  - `midi_io.open_virtual_input`, `.open_virtual_output`
- Produces:
  - `class Bridge` com `__init__(self, hardware_in, hardware_out, host_out)` e
    `handle_hardware_message(message: list[int]) -> None`,
    `handle_host_message(message: list[int]) -> None`

- [ ] **Passo 1: Escrever teste que falha**

```python
# tests/test_bridge.py
from command8_bridge.bridge import Bridge
from command8_bridge.channel_state import ChannelState


class FakeMidiOut:
    def __init__(self):
        self.sent: list[list[int]] = []

    def send_message(self, message):
        self.sent.append(list(message))


def test_hardware_mute_button_forwards_to_host_as_mcu():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x10, 0x7F])  # mute channel 0, nativo

    assert host_out.sent == [[0x90, 0x10, 0x7F]]  # mesmo layout de nota no MCU


def test_hardware_mute_button_repeated_does_not_resend():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0x90, 0x10, 0x7F])
    bridge.handle_hardware_message([0x90, 0x10, 0x7F])  # repetido, sem mudança de estado

    assert host_out.sent == [[0x90, 0x10, 0x7F]]


def test_hardware_vpot_rotation_forwards_as_mcu_cc():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_hardware_message([0xB0, 0x40, 0x41])  # encoder 0, horário, nativo

    assert host_out.sent == [[0xB0, 0x10, 0x01]]  # CC MCU equivalente


def test_host_mute_led_forwards_to_hardware():
    hardware_out = FakeMidiOut()
    host_out = FakeMidiOut()
    bridge = Bridge(hardware_out=hardware_out, host_out=host_out, state=ChannelState())

    bridge.handle_host_message([0x90, 0x12, 0x7F])  # Logic liga LED mute canal 2

    assert hardware_out.sent == [[0x90, 0x12, 0x7F]]
```

- [ ] **Passo 2: Rodar e confirmar falha**

Run: `./venv/bin/pytest tests/test_bridge.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Passo 3: Implementar**

```python
# src/command8_bridge/bridge.py
from command8_bridge import command8_protocol as c8
from command8_bridge import mcu_protocol as mcu
from command8_bridge.channel_state import ChannelState


class Bridge:
    def __init__(self, hardware_out, host_out, state: ChannelState | None = None):
        self.hardware_out = hardware_out
        self.host_out = host_out
        self.state = state or ChannelState()

    def handle_hardware_message(self, message: list[int]) -> None:
        button = c8.decode_channel_button(message)
        if button is not None:
            channel, name, on = button
            if self.state.should_forward_button(channel, name, on):
                self.state.set_button_led(channel, name, on)
                self.host_out.send_message(mcu.encode_channel_button_led(channel, name, on))
            return

        rotation = c8.decode_vpot_rotation(message)
        if rotation is not None:
            channel, delta = rotation
            value = 0x01 if delta > 0 else 0x41
            self.host_out.send_message([0xB0, 0x10 + channel, value])
            return

    def handle_host_message(self, message: list[int]) -> None:
        button = mcu.decode_channel_button(message)
        if button is not None:
            channel, name, on = button
            self.hardware_out.send_message(c8.encode_channel_button_led(channel, name, on))
            return
```

- [ ] **Passo 4: Rodar e confirmar sucesso**

Run: `./venv/bin/pytest tests/test_bridge.py -v`
Expected: PASS (4 testes)

- [ ] **Passo 5: Rodar toda a suíte**

Run: `./venv/bin/pytest -v`
Expected: PASS (todos os testes de todas as tarefas anteriores)

- [ ] **Passo 6: Commit**

```bash
git add src/command8_bridge/bridge.py tests/test_bridge.py
git commit -m "feat: bridge orchestrator for buttons and V-Pots"
```

---

### Task 11: CLI para rodar a ponte com hardware real + validação manual do handshake

**Files:**
- Create: `src/command8_bridge/cli.py`

**Interfaces:**
- Consumes: `midi_io.open_input_by_name`, `.open_output_by_name`, `.open_virtual_output`,
  `bridge.Bridge`, `mcu_protocol.is_host_connection_query`, `.encode_host_connection_reply`,
  `.encode_device_query`

- [ ] **Passo 1: Implementar o CLI**

```python
# src/command8_bridge/cli.py
import sys
import time
from command8_bridge import midi_io
from command8_bridge import mcu_protocol as mcu
from command8_bridge.bridge import Bridge

SERIAL = [0x43, 0x38, 0x62, 0x72, 0x64, 0x67, 0x65]  # "C8brdge" arbitrário, 7 bytes


def main():
    hardware_in = midi_io.open_input_by_name("Command8")
    hardware_out = midi_io.open_output_by_name("Command8")
    host_out = midi_io.open_virtual_output("Command8 MCU")
    host_in = midi_io.open_virtual_input("Command8 MCU")

    bridge = Bridge(hardware_out=hardware_out, host_out=host_out)

    def on_hardware_message(event, _data):
        message, _deltatime = event
        print(f"[hardware->] {[hex(b) for b in message]}")
        bridge.handle_hardware_message(message)

    def on_host_message(event, _data):
        message, _deltatime = event
        print(f"[<-logic] {[hex(b) for b in message]}")
        if mcu.is_host_connection_query(message):
            challenge = message[13:17]
            reply = mcu.encode_host_connection_reply(SERIAL, challenge)
            host_out.send_message(reply)
            print(f"[->logic] handshake reply {[hex(b) for b in reply]}")
            return
        bridge.handle_host_message(message)

    hardware_in.set_callback(on_hardware_message)
    host_in.set_callback(on_host_message)

    print("Ponte Command8 <-> MCU rodando. Ctrl+C para sair.")
    host_out.send_message(mcu.encode_device_query())
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrando.")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Passo 2: Teste manual (não automatizado) — smoke test com hardware real**

Com a Command|8 conectada e fora do modo Stand-Alone:

```bash
./venv/bin/python -m command8_bridge.cli
```

Aperte um botão Mute em qualquer canal. Confirme no terminal que aparece a linha
`[hardware->]` com a mensagem, seguida de `[->logic]` seria esperado, mas como ainda
não há tradução de saída pro host visível no terminal, confirme ao menos que a
mensagem `[hardware->]` aparece com os bytes esperados (nota dentro de 0x00-0x1F).

- [ ] **Passo 3: Teste manual — validar handshake com Logic Pro**

1. Abrir Logic Pro → Configurações → Superfícies de Controle → Configuração.
2. Instalar → Novo → Mackie Control.
3. Selecionar porta de entrada/saída "Command8 MCU" (a porta virtual criada pelo CLI).
4. Observar no terminal se aparece `[<-logic]` com uma mensagem SysEx.
5. Se `is_host_connection_query` retornar `False` para essa mensagem (nenhuma linha
   `[->logic] handshake reply` aparecer), copiar os bytes exatos impressos e ajustar
   `MSG_HOST_CONNECTION_QUERY`/`MSG_HOST_CONNECTION_REPLY`/`MSG_DEVICE_QUERY` em
   `mcu_protocol.py` para bater com o que o Logic realmente envia — depois repetir
   os Passos 4-5 da Tarefa 5 (rodar os testes) para confirmar que nada quebrou.
6. Repetir até o Logic mostrar a superfície como conectada (geralmente indicado por
   deixar de mostrar erro/aviso de "sem resposta do dispositivo").

- [ ] **Passo 4: Commit**

```bash
git add src/command8_bridge/cli.py
git commit -m "feat: CLI entry point wiring hardware, bridge and virtual MCU port"
```

---

### Task 12: Sniffer de MIDI bruto para a sessão de descoberta

**Files:**
- Create: `tools/midi_sniffer.py`

**Interfaces:**
- Consumes: `command8_bridge.midi_io.open_input_by_name`, `.list_input_ports`
- Produces: script standalone executável

- [ ] **Passo 1: Implementar**

```python
# tools/midi_sniffer.py
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
        print(f"{timestamp}  {format_message(message)}")

    midi_in.set_callback(on_message)
    print(f"Logando mensagens de '{port_substring}'. Ctrl+C para sair.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrando.")


if __name__ == "__main__":
    main()
```

- [ ] **Passo 2: Teste manual — auto-verificação com loopback**

Em um terminal:
```bash
./venv/bin/python -c "
from command8_bridge import midi_io
import time
out = midi_io.open_virtual_output('Sniffer Test')
time.sleep(2)
out.send_message([0x90, 0x40, 0x7F])
time.sleep(1)
"
```
Em outro terminal, rodando ao mesmo tempo:
```bash
./venv/bin/python tools/midi_sniffer.py "Sniffer Test"
```
Expected: aparece uma linha com `90 40 7F` no segundo terminal.

- [ ] **Passo 3: Commit**

```bash
git add tools/midi_sniffer.py
git commit -m "feat: standalone MIDI sniffer tool for protocol discovery"
```

---

### Task 13: Sessão de descoberta guiada (com o usuário e o hardware real)

**Files:**
- Create: `docs/PROTOCOL.md`

**Interfaces:**
- Consumes: `tools/midi_sniffer.py`
- Produces: `docs/PROTOCOL.md` preenchido + trechos de captura salvos como comentários
  no próprio arquivo (servem de fixture de referência para o plano da Fase 2)

- [ ] **Passo 1: Confirmar o modo do hardware**

Verificar se o LED do switch "Stand-Alone" (ao lado dos Status LEDs) está **apagado**.
Se estiver aceso, apertar o switch para sair do modo Stand-Alone.

- [ ] **Passo 2: Teste de sanidade do modo**

```bash
./venv/bin/python tools/midi_sniffer.py "Command8"
```
Apertar o botão Mute do canal 1 e girar o encoder do canal 1 para a direita.
- Se aparecer algo como `90 10 7F` (nota 0x10, bloco de mute) e `B0 40 41` (CC 0x40,
  valor 0x41) → modo nativo confirmado, prosseguir.
- Se aparecer um CC genérico e fixo tipo `B0 07 7F` sem esse padrão → ainda em modo
  Stand-Alone; revisar o Passo 1 antes de continuar.

- [ ] **Passo 3: Roteiro de captura sistemática**

Com o sniffer rodando, para cada item abaixo, executar a ação e copiar a(s) linha(s)
resultante(s) para `docs/PROTOCOL.md` sob o cabeçalho correspondente:

1. Mover o fader do canal 1 de baixo pra cima lentamente.
2. Tocar (sem mover) o fader do canal 1 e depois soltar.
3. Repetir os itens 1-2 para o fader master (se existir).
4. Apertar e soltar Mute, Solo e Select de dois canais diferentes (para confirmar o
   padrão de blocos de 8 notas).
5. Girar cada um dos 8 encoders para a esquerda e para a direita.
6. Clicar (pressionar) cada encoder.
7. Apertar cada botão de transporte (play, stop, record, rewind, forward).
8. Trocar de banco de canais, se houver esse controle físico.
9. Observar o LCD: anotar o texto exibido por padrão (sem DAW conectado) e se ele
   muda sozinho ao mexer nos controles.

- [ ] **Passo 4: Escrever `docs/PROTOCOL.md`**

Documentar, para cada item do roteiro, os bytes brutos observados e a interpretação.
Marcar claramente com "🔴 não testado" qualquer campo do protocolo que não pôde ser
exercitado (ex: footswitch, se o usuário não tiver um).

- [ ] **Passo 5: Commit**

```bash
git add docs/PROTOCOL.md
git commit -m "docs: raw protocol capture from discovery session"
```

---

## Self-Review

**1. Cobertura do spec:** Handshake MCU (Tarefa 5), fader/toque MCU (Tarefa 2), botões
MCU (Tarefa 3), V-Pot MCU (Tarefa 4), LCD/transporte MCU (Tarefa 6), protocolo nativo
conhecido (Tarefa 7), estado/anti-eco (Tarefa 8), I/O real (Tarefa 9), orquestrador
(Tarefa 10), CLI + validação de handshake ao vivo (Tarefa 11), sniffer (Tarefa 12),
descoberta guiada (Tarefa 13). Os itens "fora de escopo" do spec (outros DAWs, múltiplas
unidades, GUI) permanecem intencionalmente de fora. Fader/LCD/transporte do **lado
nativo** (Command|8 → esses ainda não decodificados) ficam para o plano da Fase 2,
que depende dos dados da Tarefa 13 — está registrado explicitamente no Goal.

**2. Placeholders:** nenhum "TBD"/"implementar depois" — toda tarefa tem código real
ou um roteiro de passos concretos (Tarefas 11 e 13, que são inerentemente manuais).

**3. Consistência de tipos:** `decode_channel_button` retorna `tuple[int, str, bool] | None`
consistentemente em `mcu_protocol.py` e `command8_protocol.py`, usando as mesmas strings
(`"mute"`, `"solo"`, `"select"`) — confirmado usado assim na Tarefa 10 (`bridge.py`).
`ChannelState.should_forward_button`/`set_button_led`/`get_button_led` usam a mesma
assinatura `(channel: int, button: str, ...)` em todas as tarefas que a consomem.

## Fase 2 (plano futuro, após a Tarefa 13)

Tradução de fader/toque e LCD do lado nativo da Command|8 (usando os bytes capturados
em `docs/PROTOCOL.md`), tradução de transporte nativo, app de bandeja (menu bar) com
os três estados visuais, empacotamento como `LaunchAgent`. Será um plano novo, escrito
depois que os dados da Tarefa 13 existirem.
