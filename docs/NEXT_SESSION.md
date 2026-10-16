# Command8 → MCU Bridge — retomar numa próxima sessão

Projeto: ponte que traduz o protocolo nativo da controladora **Digidesign Command|8**
pro protocolo **Mackie Control Universal (MCU)**, pra funcionar no Logic Pro sem
precisar do app comercial V-Control Pro (US$300).

Repositório: `~/Documents/Command8` (branch `main`, sem worktree pendente).
Venv: `./venv` (python-rtmidi, pytest — `PYTHONPATH=src` necessário pra rodar scripts soltos).

## Status atual — SESSÃO COMPLETA SEM O V-CONTROL PRO, validada ao vivo (2026-10-14)

**O objetivo do projeto foi atingido.** Com o V-Control Pro **fechado**, a Command|8
funciona no Logic Pro pela ponte, com estes cinco testes confirmados ao vivo, em
sequência, na mesma sessão:

1. Clicar numa faixa no Logic → **o nome aparece no visor da Command|8**
2. Select / Solo / Mute na superfície → Logic responde, LED físico acende
3. Mover o fader físico → o fader do Logic acompanha
4. Trocar de faixa no Logic → o motor do fader se move sozinho
5. Play / Stop / Record na superfície → o Logic transporta

Setup usado: ponte rodando (`python -u -m command8_bridge.cli`, publica a porta
virtual `Command8 MCU`), Logic com superfície **Mackie Control** (Mackie Designs /
Logic Control 2.59r0) apontando entrada e saída pra `Command8 MCU`, V-Control Pro
encerrado e o controlador OSC "Command8" dele removido do Logic.

109 testes automatizados passando (`./venv/bin/pytest`).

### Detalhes do que já estava validado antes


- **Select, Solo e Mute**: round trip completo confirmado ao vivo. Apertar o botão físico
  no hardware → ponte traduz → Logic reflete o estado (LED, mixer) → Logic manda o LED de
  volta → ponte traduz pro nativo → LED físico acende/apaga certo.
- **V-Pots (encoders)**: rotação (esquerda/direita) confirmada e funcionando.
- **Handshake MCU**: o challenge-response formal (SysEx tipo 0x01/0x02) nunca completa
  contra o Logic real, mas **isso não impede nada** — assim que você configura manualmente
  "Mackie Control" no Logic apontando pra porta "Command8 MCU", ele já começa a mandar
  dados reais (LCD, meter, fader, LED) independente do handshake.

## Como rodar a ponte de novo

```bash
cd ~/Documents/Command8
PYTHONPATH=src ./venv/bin/python -u -m command8_bridge.cli
```

No Logic Pro: Preferências → Superfícies de Controle → Configuração → Instalar → Novo
→ Mackie Control → portas de entrada/saída = **"Command8 MCU"**.

Por padrão o CLI não loga cada mensagem (senão trava com o volume de dados que o Logic
manda continuamente — meter/status). Pra depurar mensagem por mensagem:

```bash
COMMAND8_DEBUG=1 PYTHONPATH=src ./venv/bin/python -u -m command8_bridge.cli
```

Captura **bidirecional** (MITM) — é esta que vê o LCD, porque pega host→hardware:

```bash
PYTHONPATH=src ./venv/bin/python -u tools/midi_spy.py                      # porta "Command8"
PYTHONPATH=src ./venv/bin/python -u tools/midi_spy.py --log captura.txt
PYTHONPATH=src ./venv/bin/python -u tools/midi_spy.py --passive            # só hardware→host
```

Com o tool rodando, aponte no host: **saída = "C8 Spy In"**, **entrada = "C8 Spy Out"**.
Depois renomeie uma faixa e procure linhas `host→HW` com SysEx. Para captura limpa,
feche o Logic (ele varre toda porta virtual nova com device queries — ver armadilhas).

Sniffer antigo, unidirecional (só hardware→host, **não vê LCD**):

```bash
PYTHONPATH=src ./venv/bin/python tools/midi_sniffer.py "Command8"        # porta 1 (padrão)
PYTHONPATH=src ./venv/bin/python tools/midi_sniffer.py "Command8 Porta 2"  # se precisar da porta 2
```

## O que falta (em ordem de prioridade sugerida)

1. ✅ **Fader (toque + posição) — DECODIFICADO, IMPLEMENTADO e VALIDADO AO VIVO**
   (sessão 2026-08-27). Toque: nota `0x05` fixa pra todos os canais, velocity =
   `0x40+N`/`0x00+N` igual aos botões. Posição: mensagem `B0 <byte1> <byte2>`, canal
   = `byte1 % 8`, posição 0-127 = `byte2` direto. `command8_protocol.decode_fader_touch`/
   `decode_fader_position` implementados via TDD, `bridge.py` encaminha hardware→host
   (pitch bend MCU escalado 0-127→0-16383). **Confirmado ao vivo com Logic Pro real:
   mover o fader físico move o fader na tela do mixer**, com eco de volta do Logic
   (posição + texto de LCD). Ver `docs/PROTOCOL.md` seção "Validação ao vivo".
   Bônus: corrigido bug real em `cli.py` — Device Query só era mandado uma vez no
   início (podia chegar cedo demais); agora reenvia a cada 2s até o handshake
   completar.
   Falta ainda: **motor (host→hardware)** — hoje quem move o fader físico quando
   você mexe no Logic é o **V-Control Pro** (aberto em paralelo), não a nossa ponte;
   `bridge.py` ainda não trata pitch bend vindo do host. E confirmar toque com nota
   `0x05` em mais canais além de N=0, N=6 e N=7 (já testados).
2. ✅ **LCD nativo — DECODIFICADO, IMPLEMENTADO e VALIDADO AO VIVO** (2026-10-14).

   ```
   F0 13 01 40 <célula> 7F 00 <7 × ASCII> F7
                célula = linha × 0x10 + strip  (0x00-0x07 cima, 0x10-0x17 baixo)
   ```

   São **7 caracteres** no fio (o `numChars:6` do JSON era o campo lógico), igual ao
   MCU — tradução 1:1, sem truncamento. Implementado em
   `command8_protocol.encode_lcd_text` + `mcu_protocol.split_lcd_text`, ligado no
   `bridge.py`. Validado mandando os frames direto pro hardware **sem o V-Control Pro
   no circuito**: o texto aparece no visor físico. Ver `docs/PROTOCOL.md`.

   Como foi obtido: `tools/midi_spy.py` espelhando as portas + trocar, no V-Control
   Pro (Controllers → Command|8), MIDI Input/Output para `Command8 Spy Porta 1`.

   Falta ainda: ver o texto de uma faixa real passando ponta a ponta com o Logic
   configurado em Mackie Control apontando pra ponte (até agora o LCD foi exercitado
   com texto nosso e com o `"Not Licensed"` do V-Control Pro).

3. 🔴 **A velocity codifica REGIÃO, não canal — corrigir o decoder.** Fórmula real:
   `90 <índice do botão na região> <0x40|0x00 + região>`, regiões: strips 0-7,
   Mode 10, Top 11, Main 12, Functions 13, Transport 14, Footswitch 16. Isso resolve
   a velha anomalia do `0x4C` (= região 12, Main) e explica o `0x4E` do Record
   (= região 14, Transport). **`decode_channel_button` exige canal 0-7 e por isso
   descarta em silêncio todos os botões globais** — transporte, Main, Mode, Top,
   Functions, Footswitch. É a maior lacuna aberta agora. Ver `docs/PROTOCOL.md`.

4. 🔴 **Anel do V-Pot: só 7 dos 11 LEDs.** O frame está certo
   (`F0 13 01 00 <canal> <bitmask 7 bits> F7`, opcode `0x00`), mas um byte MIDI
   tem 7 bits e o anel tem 11 LEDs. Já tentado sem sucesso: segundo byte de
   valor, endereço `canal+8`, inundar endereços 0-31 (chegou a ~10 LEDs).
   **Próximo passo:** espelhar o V-Control Pro e girar um pan de verdade,
   lendo a sequência exata — foi o método que resolveu o LCD.

5. 🔴 **Handshake nativo não implementado.** Reiniciando o hardware com a ponte
   sozinha, o visor mostra "Command|8 (Offline)". A sessão de 2026-10-14 inteira
   rodou online por herança do V-Control Pro. Escrita de visor/LED/anel funciona
   mesmo offline (testado), então não bloqueia — mas é peça faltante do protocolo.

6. **Debounce do toque de fader.** O sensor capacitivo do canal 3 oscila sozinho
   (toque/solto a cada ~120-470ms com o hardware parado). Sem debounce a ponte vai
   martelar o host.
7. ✅ **Transporte nativo — MAPEADO e LIGADO** (2026-10-14). Bloco consecutivo na
   região 14: `0x06` RTZ, `0x07` Rewind, `0x08` Forward, `0x09` Stop, `0x0A` Play,
   `0x0B` Record. Encaminhado pro MCU, menos o RTZ (o MCU não tem nota equivalente —
   fica decodificado e inerte de propósito). Falta: LEDs de transporte no sentido
   host→hardware.
8. ✅ **Anomalia de velocity `0x4C` — RESOLVIDA**: era região 12 (Main), não canal 12.
   Ver item 3.
9. **App de bandeja (menu bar)** — ainda não construído. Só faz sentido depois do
   protocolo estar mais completo.

**Nota sobre usar o V-Control Pro como fonte de captura**: confirmado que dá pra
sniffar o tráfego nativo cru do Command8 com o V-Control Pro aberto ao mesmo tempo
(Core MIDI manda a mesma mensagem pra todo mundo escutando a porta) — isso NÃO é a
mesma coisa que pedir/usar outro trial (o app já estava aberto/habilitado); é só
mais uma fonte de tráfego real pra engenharia reversa própria, igual já foi feito
com Logic e Pro Tools. Continua valendo a decisão de não depender do app nem pedir
trial novo.

## Descobertas/armadilhas importantes (não repetir o mesmo caminho)

- **A superfície tem modos, e dá pra entrar neles sem perceber.** O Mem Loc liga o
  **modo Marcador** do Logic: os nomes de faixa somem, o visor passa a mostrar
  `Markr1` / nome do marcador / `Cr w/o  Create  Delete`, e os anéis apagam. Não é
  bug — é a Mackie Control funcionando. **Sair: apagar e recriar a superfície no
  Logic** (os botões de atribuição não tiraram). Entramos nisso sem querer ao
  apertar os 55 botões pro mapeamento.
- **Leia a linha `[logic ]` INTEIRA antes de olhar célula por célula.** O host
  manda o contexto no começo da mensagem; olhando só as células recortadas, o
  `Markr1` que explicava tudo passou despercebido por horas.

- **Reiniciar a ponte muitas vezes corrompe o estado da superfície no Logic.** A
  porta virtual aparece e some a cada reinício, e o Logic acumula estado ruim: o
  visor começa a oscilar sozinho, percorrendo os strips e trocando atribuição de
  V-Pot em laço, **sem nenhuma fonte MIDI alimentando** (medido: hardware mudo,
  Pico mudo, V-Control Pro fechado). Custou uma tarde inteira de caça dentro do
  código, com cinco mudanças que degradaram um visor que funcionava.
  **Conserto: feche o Logic, suba a ponte, só então abra o Logic** — a ordem
  importa. Se não bastar, apague e recrie a superfície da Command|8.
- **Quando o sintoma for "está estranho", instrumentar vem ANTES de hipotetizar.**
  `COMMAND8_DEBUG_LCD=1` loga, na mesma linha do tempo, o que chega do Logic e o
  que a ponte escreve em cada célula. Uma leitura disso vale mais que três
  hipóteses.

- **Duas pontes rodando = porta `Command8 MCU` duplicada.** Se o Ctrl+C não matar a
  instância antiga, a nova publica uma segunda porta com o mesmo nome e o Logic
  continua ligado na antiga — tudo parece não funcionar, inclusive código novo que
  está correto. Custou tempo em 2026-10-14. Conferir sempre:
  `pgrep -fl command8_bridge.cli` deve listar **uma** linha, e a lista de portas deve
  ter **um** `Command8 MCU`.
- **Botões do Console View são mapeáveis no Logic por Atribuições de Controlador**
  (modo Learn), confirmado em 2026-10-14 — não dependem de acertar as notas de
  atribuição do MCU.

- **O Logic varre toda *destination* nova** com uma rajada de device queries MCU
  (`F0 00 00 66 <10|11|14|15|17> 00 F7` + `… 13 00 F7` de version request) no instante
  em que a porta aparece. Polui a captura (o `midi_spy.py` já rotula) e mostra que o
  lado do host está ativo — o que falta no handshake é a nossa resposta, não a pergunta.

- **O sniffer só vê hardware→host.** Uma *source* do Core MIDI carrega apenas o que o
  hardware manda; o que o host manda **pro** hardware vai pra *destination*, e o Core MIDI
  **não tem API pra observar a saída de outro processo**. Foi isso que fez a caça ao LCD
  perder 2 sessões. Pra ver host→hardware: porta virtual no meio (MITM) ou um driver de
  spy (é por isso que o MIDI Monitor da Snoize instala um driver separado). Não é
  `ignore_types` — esse já está certo em `midi_io.py`.
- **Toque de V-Pot nunca foi testado** — `/Command8/knob_touch/1..9` existe na superfície
  da Neyrinck, então provavelmente existe no fio. Procurar nota fixa perto de `0x04`/`0x06`
  com velocity codificando canal, igual ao fader.
- **Nota `0x01` = `C8SelectLED`** (LED verde, somente saída). Não é botão.

- **A Command|8 manda um "beacon" (`90 00 7F` repetido a cada ~0.5s)** enquanto nenhum
  host está conectado de verdade — para assim que um host (Logic ou Pro Tools) conecta
  de fato. Útil pra saber se a conexão nativa está ativa sem olhar o visor físico.
- **O motor do fader "engasga" ao empurrar na mão** — testado e confirmado que não vem
  do nosso software (0% CPU, zero mensagens passando pela ponte no momento). É
  característica mecânica do hardware (~20 anos de uso), não um bug de código.
- **V-Control Pro tem uma integração OSC separada** com um módulo "Command8" nativo que
  aparece no Logic (não é o Mackie Control genérico) — mas só funciona com o V-Control
  Pro aberto rodando seu próprio servidor OSC local. Não ajuda o projeto (continuaria
  dependendo do app pago); ignorado de propósito.
- **Não pedir/usar outro trial do V-Control Pro** — decisão tomada de propósito, é
  contornar a limitação de licença deles. Seguir só com engenharia reversa própria.
- **Pro Tools no mesmo Mac também teve dificuldade** de conectar de forma estável com
  esse hardware (caiu e reconectou várias vezes sem ação clara) — não é só o Logic que
  tem essa dificuldade com hardware desse tipo em macOS moderno.
- **O repositório já mora no HD local** (`~/Documents/Command8`), não mais no
  compartilhamento de rede — isso resolveu travamentos de `git log`/`git status`/`merge`
  com erro de memória (SIGBUS) que aconteciam quando o projeto vivia em
  `/Volumes/arquivos/...`. Se algum dia mover de novo pra rede, esperar esse problema
  voltar.
