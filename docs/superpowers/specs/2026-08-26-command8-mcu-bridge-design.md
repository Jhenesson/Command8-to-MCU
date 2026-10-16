# Design: Ponte Command|8 → Mackie Control Universal (MCU) para Logic Pro

## Contexto e motivação

A controladora **Digidesign Command|8** (não é a Mackie Command|8 — vendor USB `0x0dba`,
"Digidesign Inc") não se comunica nativamente com o Logic Pro. Existem três modos de
operação conhecidos do hardware:

- **Pro Tools mode**: protocolo nativo rico da Digidesign (variante do HUI), com feedback
  completo (LEDs, motor dos faders, texto no LCD). É o modo que o Pro Tools e o
  **Neyrinck V-Control Pro** (app comercial de US$300) sabem interpretar.
- **Avid mode**: mapeamento específico para produtos Avid (Media Composer).
- **Stand-Alone mode**: a Command|8 vira um controlador MIDI genérico simples. Funciona
  "out of the box" com qualquer DAW, mas exige mapear cada controle manualmente nas
  Controller Assignments do Logic, sem feedback (sem fader motorizado seguindo automação,
  sem LEDs sincronizados, sem nome de faixa).

O usuário testou o trial do V-Control Pro, confirmou que funciona (tradução completa
Command|8 → MCU), mas não considera o preço (US$300) compatível com o valor da própria
mesa. O objetivo deste projeto é construir uma ponte própria, gratuita, que faça a mesma
tradução: **protocolo nativo da Command|8 (Pro Tools mode) → Mackie Control Universal**,
para que o Logic Pro reconheça a Command|8 usando seu suporte nativo a "Mackie Control"
nas preferências de Control Surfaces — sem precisar de nenhum script dentro do Logic.

## Descobertas técnicas já validadas

Estas descobertas foram confirmadas empiricamente nesta máquina (macOS 13.7.8) ou por
fontes públicas cruzadas — não são suposições:

1. **A Command|8 é um dispositivo USB MIDI classe-padrão.** Confirmado ao vivo: com
   *zero* processos ou daemons do Neyrinck rodando (`ps aux` e `launchctl list` limpos),
   o CoreMIDI ainda expõe `Command8 Porta 1`, `Command8 Porta 2` (entrada) e
   `Command8 Porta 1/2/3` (saída) via `python-rtmidi`. Isso significa que **não
   precisamos de acesso USB/HID bruto (libusb) nem de nenhum driver de terceiros** — o
   bridge pode ler/escrever MIDI padrão diretamente nessas portas.
   - As portas `V-Control`, `V-Control XT2/XT3/XT4`, `V-Pan 1/2`, `V-Control MA Keyboard`
     e `V-Control MIDI Mode` são virtuais, criadas somente pelo processo do V-Control Pro
     (desaparecem quando ele fecha). Não são relevantes para o nosso bridge.
2. **Hardware físico**: 8 canais bankáveis, cada um com fader motorizado sensível ao
   toque (resolução ~1024 posições), encoder rotativo contínuo com anel de 11 LEDs,
   e botões Mute/Solo/Select. Display LCD de **2 linhas, ~6-7 caracteres por canal
   (110 caracteres no total)**. Seção de transporte à parte, com jack de footswitch.
   Fonte: cruzamento de Sound on Sound e Sweetwater (concordam no número: display de
   110 caracteres / 2×55).
3. **Correspondência com o protocolo MCU**: o protocolo Mackie Control Universal usa
   exatamente um buffer de "scribble strip" de 110 caracteres exibidos (2×56, com 2
   caracteres ocultos de wrap) via SysEx `F0 00 00 66 14 12 <offset> <texto...> F7`.
   O tamanho bater quase exatamente com o display físico da Command|8 é um forte indício
   de que a tradução de texto será direta, sem precisar de heurísticas de truncamento.
4. **Protocolo nativo parcialmente documentado** (fonte: repositório público
   `neyrinckaudio/command8`, da própria fabricante do V-Control Pro, com testes via
   WebMIDI): botões com LED enviam nota refletida (note-on liga o LED, note-off desliga);
   encoders enviam Control Change 64-71, valor `0x3F` (63) = giro à esquerda, `0x41` (65)
   = giro à direita; os anéis de LED dos encoders são controlados por SysEx no formato
   `F0 13 01 <byte-endereço-do-encoder> <máscara-de-bits> F7`. Isso ainda não cobre:
   posição/toque dos faders, texto do LCD, e botões de transporte — precisam ser
   descobertos na fase de engenharia reversa deste projeto.
5. **Especificação do protocolo MCU** (fonte cruzada: documentação pública do projeto
   TouchMCU e conhecimento próprio confirmado): fader = Pitch Bend de 14 bits, um canal
   MIDI por fader (0 a 7 canais + 8 = master), 0 = todo pra baixo, 16383 = todo pra cima;
   toque do fader = Note On/Off nas notas 0x68-0x70 (G#7 a E8); botões de canal REC/SOLO/
   MUTE/SELECT = blocos de 8 notas cada, 0x00-0x07 / 0x08-0x0F / 0x10-0x17 / 0x18-0x1F;
   V-Pot: rotação relativa via CC 0x10-0x17, clique via nota 0x20-0x27, anel de LED via
   CC 0x30-0x37 (bit 6 = LED ligado, bits 5-4 = modo, bits 3-0 = valor); transporte via
   notas fixas (rewind 91, forward 92, stop 93, play 94, record 95); handshake de
   dispositivo via SysEx de query/challenge-response.

> **Nota de rigor**: durante a pesquisa, uma busca por um possível projeto open-source
> equivalente (`alphonsom/command8-cpp`) retornou detalhes tecnicamente inconsistentes
> entre chamadas sucessivas da ferramenta de busca (inclusive uma alegação — refutada
> ao vivo nesta máquina — de que "o CoreMIDI não vê o dispositivo"). Tratamos essa fonte
> como não confiável (provável alucinação da sumarização) e **não a usamos como base**
> para nenhuma decisão deste design.

## Arquitetura

Três camadas, um processo Python rodando como app de bandeja (menu bar):

```
┌─────────────────┐     MIDI bruto      ┌──────────────┐     MIDI MCU      ┌───────────┐
│  Command|8       │ ───────────────────▶│  Tradutor     │──────────────────▶│  Logic    │
│  (Porta 1/2/3)   │◀─────────────────── │  (protocol.py)│◀───────────────── │  Pro      │
└─────────────────┘                      └──────────────┘                   └───────────┘
                                          app de bandeja
                                          (start/stop, status)
```

- **Lado hardware**: abre `Command8 Porta 1`/`Porta 2` como entrada e `Command8 Porta 1`
  (ou a porta correta identificada na fase de descoberta) como saída, via `python-rtmidi`.
- **Tradutor**: mantém o estado dos 8 canais (posição de fader, texto de nome de faixa,
  estados de LED) e faz a conversão bidirecional entre o formato nativo da Command|8 e o
  formato MCU.
- **Lado Logic**: cria uma porta MIDI virtual (via `rtmidi` virtual port do CoreMIDI,
  ex. "Command8 MCU") que o usuário configura uma única vez em Logic Pro → Configurações
  → Superfícies de Controle → Instalar → Mackie Control, apontando pra essa porta virtual.

## Plano de descoberta do protocolo nativo

1. Confirmar como colocar a Command|8 em **Pro Tools mode** sem o Pro Tools aberto
   (verificar se o modo persiste do último uso, ou se existe um switch físico "Stand-Alone"
   perto dos LEDs de status que alterna os modos).
2. Escrever um script de logging (`tools/midi_sniffer.py`) que imprime toda mensagem MIDI
   bruta recebida nas portas da Command|8, com timestamp e formatação hexadecimal.
3. Percorrer um roteiro sistemático com o usuário operando o hardware fisicamente:
   cada um dos 8 faders (subir/descer/tocar/soltar), cada botão Mute/Solo/Select de cada
   canal, giro e clique de cada um dos 8 encoders, todos os botões de transporte, troca
   de banco (se existir), footswitch (se o usuário tiver um).
4. Registrar tudo em `docs/PROTOCOL.md`, cruzando com o que já sabemos do repositório
   `neyrinckaudio/command8` e completando as lacunas (LCD, fader, transporte).

## Camada de tradução MCU

Implementa o subconjunto do protocolo MCU necessário para: handshake de dispositivo,
faders motorizados com sensor de toque, botões Mute/Solo/Select/Record com LED, V-Pots
com anel de LED, texto de nome de faixa no LCD, transporte (play/stop/record/rewind/
forward), meter de nível (se o tempo permitir — não é bloqueante para a primeira versão
funcional). Testado com mensagens de fixture capturadas na fase de descoberta.

## App de bandeja (menu bar)

- Três estados visuais: desconectado (Command|8 não plugada), conectado sem Logic
  (bridge ativo, porta MCU virtual criada, mas Logic ainda não fez handshake), ativo
  (Logic conectado via MCU).
- Menu: iniciar/parar bridge, abrir log de debug, recarregar (para replug do hardware).
- Sobe como `LaunchAgent` do usuário (não `LaunchDaemon` root), iniciando no login.

## Testes

- Testes automatizados (`pytest`) cobrindo só a camada pura de tradução: dada uma
  mensagem bruta conhecida da Command|8 (capturada e congelada como fixture), verificar
  que o tradutor gera a mensagem MCU esperada — e vice-versa (mensagem MCU vinda do
  Logic → mensagem nativa esperada de volta pro hardware).
- A camada de I/O real (hardware ↔ MIDI ↔ Logic) só é validável na prática, com o
  usuário testando ao vivo no Logic Pro.

## Riscos conhecidos

- Alguma função do protocolo nativo pode só aparecer em combinações de botões não óbvias
  (ex: troca de banco, undo, footswitch) — mitigado documentando incrementalmente.
- O Logic pode exigir a resposta correta do challenge-response do handshake MCU para
  aceitar o dispositivo — a fórmula já está documentada neste spec e será implementada
  e testada cedo no processo, antes de depender dela para o resto do fluxo.
- Sem outra unidade Command|8 disponível para comparar, todo o trabalho de descoberta
  depende do hardware único do usuário — qualquer suposição não testada ao vivo deve ser
  marcada como tal em `docs/PROTOCOL.md`.

## Fora de escopo (por agora)

- Suporte a outros DAWs além do Logic Pro (Reaper, Cubase, Ableton) — a arquitetura não
  impede isso no futuro (a camada MCU já seria compatível com qualquer DAW que suporte
  Mackie Control), mas não é o foco da primeira versão.
- Suporte a mais de uma Command|8 simultânea (extenders).
- Interface gráfica além do ícone de bandeja (sem janela de configuração visual por
  enquanto — configuração via arquivo, se necessário).
