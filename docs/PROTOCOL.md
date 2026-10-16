# Protocolo nativo da Digidesign Command|8 — descobertas da sessão de captura ao vivo

Capturado em 2026-08-26 com o hardware real conectado, usando `tools/midi_sniffer.py`
apontado pra porta `Command8` (entrada). O log bruto completo está salvo em
[`tests/fixtures/raw_capture_2026-08-26.log`](../tests/fixtures/raw_capture_2026-08-26.log).

**⚠️ Nota importante sobre a captura:** O `tools/midi_sniffer.py` utilizado nesta sessão
tinha o mesmo bug que foi posteriormente descoberto em `python-rtmidi`: por padrão,
`rtmidi.MidiIn` chama `ignore_types(sysex=True)`, descartando silenciosamente TODAS as
mensagens SysEx antes mesmo de chegarem no callback. Isso significa que **nenhuma mensagem
SysEx pôde ter sido capturada nesta sessão**, mesmo que o hardware tenha mandado alguma
(ex: atualização de LCD, handshake inicial). A ausência de dados de SysEx neste documento
não prova que o hardware não manda SysEx — apenas que o sniffer não conseguiria vê-las.
**Recomenda-se re-capturar os dados com o sniffer corrigido** (após aplicar
`ignore_types(sysex=False)`) antes de fazer qualquer conclusão definitiva sobre o
suporte a SysEx/LCD na Fase 2.

## Contexto físico confirmado

- Modelo: **Digidesign Command|8** (não Mackie), co-branding "digidesign | Focusrite"
  visível no painel.
- LED **USB** aceso (verde) o tempo todo — a conexão USB está sempre saudável.
- Display LCD mostrando **"Command|8 (Offline)"** durante toda a sessão de captura,
  mesmo com o switch **Stand Alone** desligado. "Offline" é um status de
  reconhecimento de host (nenhum DAW/software fez o handshake), não um problema de
  conexão física — o hardware manda eventos normalmente mesmo "offline".
- Botões físicos por canal (8 canais): **Select**, **Solo**, **Mute** (não há botão
  de Record por canal).
- Fileira de botões globais no topo dos canais: EQ, Dynamics, Insert, Pan/Send/PRE,
  ⟨ Page ⟩, Master Bypass, ESC — não testados nesta sessão.
- Medidores de LED por canal (verde/amarelo/vermelho) — não testados nesta sessão,
  possivelmente refletem nível de áudio analógico local, não MIDI.
- Confirmado: existe botão **Bank** (grupo Bank/Nudge/Zoom), **Flip**, **Master Faders**.
- Seção de transporte tem **6 botões**: RTZ, REW, FWD, STOP, PLAY, REC (a especificação
  pública do MCU assume só 5 — sem RTZ — então isso é uma diferença real da Command|8).
- V-Pots: encoders contínuos, **sem função de clique** (diferente do que a Tarefa 4
  assumiu para o protocolo MCU — lá o clique é uma função do MCU/host, não do hardware
  Command|8 nativo, então não se aplica ao lado nativo mesmo).

## ⚠️ Descoberta importante: os botões de canal usam um esquema DIFERENTE do assumido

O código já escrito em `command8_protocol.py` (Tarefa 7) assumiu, com base em
documentação pública de terceiros (repositório `neyrinckaudio/command8`), que cada
botão de canal teria sua PRÓPRIA nota (blocos de 8 notas por tipo de botão, um
esquema estilo MCU). **A captura ao vivo mostra um esquema diferente:**

- A **nota** identifica o TIPO de botão (fixa, não muda por canal).
- A **velocity** codifica o canal E o estado (apertado/solto):
  - Apertar canal N → velocity = `0x40 + N`
  - Soltar canal N → velocity = `0x00 + N`
  - (N é 0-based: canal 1 físico = N=0, canal 2 físico = N=1, etc.)

### Notas confirmadas por tipo de botão

| Botão | Nota | Exemplo (canal 1, N=0) | Exemplo (canal 2, N=1) |
|---|---|---|---|
| Select | `0x00` | apertar `90 00 40` / soltar `90 00 00` | não testado, mas esperado `90 00 41`/`90 00 01` |
| Solo | `0x02` | apertar `90 02 40` / soltar `90 02 00` | não testado |
| Mute | `0x03` | apertar `90 03 40` / soltar `90 03 00` | apertar `90 03 41` / soltar `90 03 01` ✅ testado |
| Record (transporte, não por canal) | `0x0B` | apertar `90 0B 4E` / soltar `90 0B 0E` | N/A (botão único, não por canal) |

Nota `0x01` nunca foi testada diretamente (não há botão físico entre Select=0x00 e
Solo=0x02 nos canais) — pode ser não utilizada, ou reservada para outra função.

**✅ RESOLVIDO (2026-10-13, engenharia reversa do V-Control Pro):** nota `0x01` é
`C8SelectLED` — LED verde **somente saída** (host→hardware), não botão. Por isso nunca
houve botão físico nessa posição. Mapa completo em [re/00-SINTESE.md](re/00-SINTESE.md).

**✅ Atualização (Fase 2, mesmo dia):** `command8_protocol.py` já foi corrigido pra usar
o esquema nota-fixa + velocity-codifica-canal confirmado acima, e o round trip completo
(hardware → ponte → Logic Pro → ponte → LED físico) foi **validado ao vivo com o Logic
Pro real** para Select, Solo e Mute — funcionando nos dois sentidos, LED acende e apaga
corretamente. Ver seção "Validação ao vivo com Logic Pro" mais abaixo.

Para o botão Record de transporte, o valor de "sub-id" embutido na velocity (`0x0E`)
não corresponde a um canal — é provavelmente um identificador fixo interno daquele
botão específico dentro de uma tabela global de controles do dispositivo.

### ❓ Questão EM ABERTO: anomalias nas velocidades de botão

O log bruto contém uma anomalia não documentada nos botões de canal. Além dos padrões
esperados `90 02 40` (apertado) e `90 02 00` (solto), existem também ocorrências de
`90 02 4C` e `90 02 0C`. Se a regra fosse estritamente "velocity = 0x40+canal" (ou
"velocity = 0x00+canal" para solto), o valor `0x4C` implicaria canal 12 (0x4C - 0x40 = 12),
**fora da faixa de 8 canais físicos** disponíveis no hardware.

Isso sugere que a codificação pode ser mais complexa do que o padrão linear assumido:
- Pode ser uma tabela global de IDs de controle (não uma simples fórmula de offset)
- Pode haver compactação ou múltiplas dimensões de codificação na velocity
- Pode ser ruído ou estado transitório não representativo

**Recomendação:** Investigar com captura controlada (ex: apertar cada botão isoladamente
de forma limpa, uma por vez) antes de confiar na regra "nota fixa + velocity = canal"
para toda a Fase 2. A anomalia precisa ser resolvida para evitar bugs de mapeamento
de canais incorreto.

**⚠️ Atualização (2026-10-13):** a hipótese da "tabela global de IDs de controle" foi
**eliminada**. Essa tabela existe de fato (465 entradas, ids 0-464, em
`/Library/Audio/MIDI Device Scripts/Neyrinck/Command8.device/config.lua`) e **não bate
com o fio**: lá Select=72-79, Solo=24-31, Mute=16-23, Record=306; no fio são `0x00`,
`0x02`, `0x03`, `0x0B`. **A anomalia do `0x4C` continua aberta** — só essa explicação
caiu. Ver [re/00-SINTESE.md](re/00-SINTESE.md).

## V-Pots (encoders) — CONFIRMADO, bate com a documentação pública

A Tarefa 7 já implementou isso corretamente com base na documentação de terceiros, e a
captura ao vivo confirma exatamente:

- Rotação horária (direita) no encoder do canal N (0-based): `B0 (0x40+N) 0x41`
- Rotação anti-horária (esquerda): `B0 (0x40+N) 0x3F`
- Testado no canal 1 (N=0): `B0 40 41` (direita) e `B0 40 3F` (esquerda) ✅
- Sem função de clique físico neste hardware (confirmado pelo usuário).

Nenhuma correção necessária em `command8_protocol.py` para esta parte.

## Fader — toque e posição CONFIRMADOS (sessão 2026-08-27, com V-Control Pro aberto)

Capturado com o sniffer nas duas portas nativas simultaneamente enquanto o V-Control
Pro estava aberto e habilitado (Core MIDI transmite pra todos os listeners, então a
captura crua não depende do V-Control Pro nem é afetada por ele). Dois testes: um
movimento denso/ruidoso (múltiplos faders quase simultâneos) e um teste controlado
(um único fader, toque contínuo, movimento devagar numa direção só).

### Toque (fader touch) — CONFIRMADO, mesmo esquema dos botões de canal

- Nota fixa `0x05` pra TODOS os canais (não muda por canal, como se suspeitava).
- Velocity codifica canal + estado, igual Select/Solo/Mute: apertar canal N →
  `0x40+N`, soltar → `0x00+N`.
- Testado ao vivo nos canais N=0 e N=6: `90 05 46`/`90 05 06` (canal 6),
  `90 05 40`/`90 05 00` (canal 0).

### Posição do fader — CONFIRMADO

Mensagem: `B0 <byte1> <byte2>`.

- **`byte1 % 8` = canal (N)** — confirmado em toda a captura, bate exatamente com o
  canal que está sendo tocado no momento (via a nota `0x05`).
- **`byte2` = posição do fader, 0-127** — sobe/desce de forma limpa e monotônica com
  o movimento físico. Teste controlado (canal 0, subindo devagar): `50→51→...→5B`
  (soltou/tocou de novo, dedo continuou deslizando) `→64→65→...→6E` (soltou/tocou de
  novo) `→75→76→...→7F` (chegou no topo, `0x7F`=127). Os "saltos" entre soltar/tocar
  batem com o dedo continuar deslizando durante o blip de contato perdido, não é
  ruído.
- **Teoria antiga rejeitada**: a hipótese de que `byte1` (sempre múltiplo de 8 mais o
  offset do canal) seria os 3 bits altos de uma posição de 10 bits (3+7, batendo com
  os "1024 posições" da review da Sound on Sound) **não se sustenta** — no teste
  controlado, cada valor de `byte2` chega em duas mensagens com `byte1` alto
  diferente (uma baixa ~1-3, outra alta ~6-7, sempre nesse padrão de par), sem
  relação suave com o movimento. Parece artefato do sensor (duas amostras por
  "tick", possivelmente relacionado a pressão/qualidade de contato), não uma parte
  útil da posição. **Pra implementação: usar `byte2` direto como posição (0-127) e
  ignorar os bits altos de `byte1`** — é suficiente e já é uma leitura limpa.
- A resolução real de 1024 posições do hardware (se existir) pode estar disponível
  só internamente/pro motor, não exposta nessa leitura de toque via MIDI CC de 7
  bits — não é bloqueio pra Fase 2.

### ✅ Validação ao vivo com Logic Pro real (2026-08-27)

Round trip hardware→ponte→Logic confirmado: mover o fader físico do canal 1 move o
fader correspondente na tela do mixer do Logic, e o Logic ecoa de volta a posição
(`E0 <lsb> <msb>`) junto com atualização de texto do LCD (SysEx `0x12`) — prova de
que o Logic aceitou o pitch bend como movimento real de usuário.

**Causa raiz de por que não funcionava antes**: a superfície "Mackie Control"
configurada no Logic (porta "Command8 MCU") tinha sido **removida/apagada** da
sessão em algum momento antes desse teste — nenhuma mensagem chegava em lugar
nenhum. Recriá-la (Preferências → Superfícies de Controle → Configuração → Novo →
Instalar → Mackie Control, portas = "Command8 MCU") resolveu. Não era bug no nosso
código.

De quebra, aproveitando a investigação, corrigimos um problema real de robustez em
`cli.py`: o Device Query (`F0 00 00 66 14 00 F7`) só era mandado **uma vez** no
início do processo, o que pode chegar cedo demais (antes do Logic terminar de
conectar na porta virtual recém-criada) e nunca ser visto. Agora é reenviado a cada
2s até o handshake completar (`cli.py`, loop `while not handshake_done`). O
handshake formal (challenge/response tipo `0x01`/`0x02`) continua nunca completando
mesmo assim — mas, como já era sabido, isso não impede a operação normal (Select,
Solo, Mute, V-Pot e agora Fader confirmados funcionando sem ele).

**⚠️ Motor (host→hardware) ainda NÃO está implementado no nosso código.** O
movimento "vice-versa" (mexer no fader do Logic move o hardware físico) observado
nesta sessão vem do **V-Control Pro**, que estava aberto e conectado nativamente ao
hardware em paralelo — não da nossa ponte. `bridge.py.handle_host_message` só trata
botões (LED) hoje; fader motorizado fica para uma próxima sessão.

## Transporte — parcialmente testado

| Botão | Nota | Velocity apertar | Velocity soltar |
|---|---|---|---|
| Record | `0x0B` | `0x4E` | `0x0E` |
| Rewind | 🔴 não testado | | |
| Forward | 🔴 não testado | | |
| Stop | 🔴 não testado | | |
| Play | 🔴 não testado | | |
| RTZ | 🔴 não testado | | |

## Itens não testados nesta sessão (ficam para a Fase 2, se necessário)

- LCD: não foi possível observar o formato de texto customizado, porque o display
  mostra "Command|8 (Offline)" fixo enquanto nenhum host completa o handshake —
  precisa investigar se existe algum jeito de escrever no LCD sem handshake completo,
  ou se isso realmente depende de implementar a Fase 2 do handshake MCU e testar
  com o Logic Pro real.
- Botão Bank (existe fisicamente, não testado).
- Botões globais do topo (EQ, Dynamics, Insert, Pan/Send/PRE, Page, Master Bypass, ESC).
- Medidores de LED por canal (podem ser controlados via SysEx pelo host, ou podem ser
  só uma leitura analógica local — não testado).
- V-Pot LED ring: a documentação pública (`neyrinckaudio/command8`) descreve o formato
  `F0 13 01 <encoder> <máscara> F7`, já implementado em `command8_protocol.py`
  (Tarefa 7), mas isso é uma mensagem de SAÍDA (host→hardware) — não foi possível
  validar ao vivo nesta sessão porque exigiria já ter a Fase 2 implementada para mandar
  esse SysEx de volta pro hardware e observar o anel de LED acender.

## Resumo do que muda no código já escrito (para a Fase 2)

1. ✅ **`command8_protocol.decode_channel_button` e `encode_channel_button_led`
   corrigidos** (mesmo dia) pro esquema nota-fixa + velocity-codifica-canal. Validado
   ao vivo com Logic Pro para Select/Solo/Mute. Falta ainda: confirmar Record por canal
   (não existe nesta unidade) e resolver a anomalia de velocity (`0x4C`) documentada acima.
2. **`command8_protocol` V-Pot rotation/LED ring: nenhuma mudança necessária** —
   rotação confirmada correta; anel de LED (host→hardware) ainda não testado ao vivo.
3. **Fader touch e posição: implementar do zero na Fase 2**, com testes mais controlados
   pra decodificar a posição com confiança antes de escrever qualquer fórmula.
4. **Transporte nativo: implementar do zero na Fase 2** — só Record foi confirmado.

## Validação ao vivo com Logic Pro (Fase 2, mesmo dia)

Com o CLI (`python -m command8_bridge.cli`) rodando e uma superfície "Mackie Control"
configurada no Logic Pro (Preferências → Superfícies de Controle → Configuração →
Instalar → Novo → Mackie Control, portas de entrada/saída = "Command8 MCU"):

- O handshake formal de challenge-response (SysEx tipo `0x01`/`0x02`) **nunca completou**
  — o Logic manda vários "Device Query" (tipo `0x00`) pra modelos diferentes
  (`F0 00 00 66 10 00 F7`, `...66 11...`, `...66 14...`, `...66 15...`, `...66 17...`,
  cada um representando um device MCU-family diferente: Logic Control, Logic Control XT,
  Mackie Control, Mackie Control XT, etc.) mas **isso não impede o Logic de operar a
  superfície** — assim que o usuário configura manualmente "Mackie Control" apontando
  pra porta certa, o Logic já começa a mandar dados reais (texto de LCD, medidor,
  fader, LED) independente do handshake ter sido reconhecido ou não.
- Confirmado ao vivo, ponta a ponta: apertar **Select**, **Solo** ou **Mute** no
  hardware → Logic reflete o estado (LCD mostra "Mute"/"Muted"/"--", mixer atualiza) →
  Logic manda o LED MCU de volta (`90 10 7F`/`90 10 00` pro Mute canal 0, por exemplo)
  → a ponte traduz pro protocolo nativo e o LED físico do botão acende/apaga
  corretamente.
- O texto de LCD que o Logic manda via SysEx bate exatamente com o formato documentado
  publicamente (`F0 00 00 66 14 12 <offset> <texto...> F7`, offset `0x00` e `0x38` pros
  dois blocos de texto do canal 1) — confirma que a camada MCU pura já implementada em
  `mcu_protocol.py` está correta e pronta pra quando a tradução nativa de LCD existir.

## Investigação de LCD nativo com Pro Tools (Fase 2, mesmo dia) — inconclusiva

> **⚠️ SUPERADO em 2026-10-13.** O veredito está em [re/00-SINTESE.md](re/00-SINTESE.md):
> **o LCD é SysEx sobre MIDI**, e a razão de nenhum `F0` aparecer era **cegueira de
> direção** no sniffer (ele abre só uma entrada; a escrita de LCD é host→hardware, para a
> *destination*, que o Core MIDI não permite observar de outro processo). A hipótese de
> USB cru abaixo está **descartada**. O resto da seção fica como registro histórico.

Com o Pro Tools aberto e a Command|8 configurada em Setup → Peripherals → MIDI
Controllers, a conexão nativa (Pro Tools mode) chegou a funcionar de forma
intermitente — LCD mostrando nome de faixa real e fader motorizado sincronizando
com a faixa selecionada — mas caiu sozinha várias vezes durante a sessão.

Descobertas:

- **Mensagem de "beacon"**: enquanto nenhum host está conectado (ou a conexão cai),
  a Command|8 manda `90 00 7F` repetidamente a cada ~0.5s pela Porta 1. Provavelmente
  um sinal de "presença"/"procurando host", análogo ao Device Query do MCU. Esse
  padrão para assim que o Pro Tools conecta de verdade.
- **Nenhuma mensagem SysEx (`F0`) foi observada em nenhum momento** durante a conexão
  ativa com o Pro Tools, mesmo com o nome real da faixa aparecendo no LCD físico e o
  fader se movendo sozinho (motor) pra refletir a faixa selecionada. Só se observou
  `90` (Note On) e `B0` (Control Change) — os mesmos tipos de mensagem já catalogados
  pra botões/encoders/fader.
- **🔴 Hipótese em aberto**: o texto do LCD pode não trafegar por MIDI de jeito nenhum
  — pode ser atualizado pelo Pro Tools através de um canal USB separado, fora da classe
  MIDI (o que explicaria por que nunca aparece nada de novo no sniffer MIDI mesmo com
  o texto mudando fisicamente no visor). Se essa hipótese estiver certa, decodificar o
  LCD exigiria captura de USB bruto (fora do escopo atual, que deliberadamente evita
  isso) — precisa ser reavaliado antes de investir mais tempo tentando adivinhar SysEx.
- A instabilidade da conexão com o Pro Tools nesta máquina (ela caiu e reconectou
  várias vezes sem ação clara do usuário) sugere que o Pro Tools moderno também tem
  dificuldade com esse hardware antigo — não é só um problema exclusivo do Logic.
- Fader motorizado: confirmado que o motor se move sozinho (comandado pelo host) ao
  trocar de faixa selecionada, e que esse movimento gera o mesmo fluxo `B0` já visto
  em movimentos manuais — reforça que aquele fluxo é mesmo a posição do fader (Fase 2
  ainda precisa decodificar os dois bytes com confiança, ver seção acima).

**Próximo passo recomendado**: antes de tentar mais SysEx às cegas pro LCD, confirmar
se o Pro Tools realmente não usa MIDI pra texto (talvez pesquisando o driver original
da Digidesign ou capturando USB bruto com uma ferramenta como Wireshark com USBPcap/
usbmon) — ou aceitar que o LCD fica fora do escopo da ponte por enquanto e focar em
fader/medidor/transporte, que já são comprovadamente MIDI.

## Varredura de superfícies do Logic (observada em 2026-10-13)

Com Logic Pro X aberto, no instante em que **qualquer** *destination* nova do Core MIDI
aparece, chega esta rajada (capturada com `tools/midi_spy.py` numa porta virtual):

```
F0 00 00 66 10 00 F7        device query  dev 0x10  (Logic Control)
F0 00 00 66 11 00 F7        device query  dev 0x11  (Logic Control XT)
F0 00 00 66 14 00 F7        device query  dev 0x14  (Mackie Control)
F0 00 00 66 15 00 F7        device query  dev 0x15  (Mackie Control XT)
F0 00 00 66 17 00 F7        device query  dev 0x17
F0 00 00 66 <dev> 13 00 F7  version request, para cada dev acima
```

Duas implicações:

1. **Ruído**: toda captura em porta virtual começa com essa rajada. O `midi_spy.py`
   rotula essas linhas como varredura; para captura limpa, fechar o Logic.
2. **Handshake**: o lado do host está ativo e insistente, perguntando por vários device
   IDs. O que falta pro challenge-response completar é a resposta correta do nosso lado,
   não a iniciativa do Logic.

## LCD nativo — DECODIFICADO e VALIDADO AO VIVO (2026-10-14)

```
F0 13 01 40 <célula> 7F 00 <7 × ASCII> F7          15 bytes
             │
             └─ célula = linha × 0x10 + strip
                0x00-0x07 = linha superior, strips 1-8
                0x10-0x17 = linha inferior, strips 1-8
```

`13 01 40` (prefixo Digidesign + opcode de display), `7F` e `00` são constantes em
todos os frames observados. Texto: **7 caracteres ASCII**, preenchido com espaços
(`0x20`) — não 6, como o `numChars:6` do JSON de superfície do V-Control Pro sugeria.
Esse 6 é o campo lógico visível; o fio carrega 7. Como o **MCU também usa 7 por
strip**, a tradução de texto é **1:1, sem truncamento**.

### Como foi obtido

1. `tools/midi_spy.py` espelha as portas reais em portas virtuais
   (`Command8 Spy Porta 1/2/3`) e fica no meio, logando as duas direções.
2. No V-Control Pro, em Controllers → Command|8, trocar MIDI Input e MIDI Output
   para `Command8 Spy Porta 1`. Ele passa a escrever através da ponte.
3. O texto apareceu imediatamente: ele mandou `"Not Lic"` / `"ensed  "` espalhado
   pelas células (a superfície na porta nova não entra na licença dele — irrelevante,
   o frame é o mesmo).

### Validação

Mandamos os frames nós mesmos, direto pra `Command8 Porta 1`, **sem o V-Control Pro
no circuito**, e o texto apareceu no visor físico: `PONTE`/`FUNCIO`/`NANDO`/`SEM VCP`
na linha de cima e `abcdefg`/`LINHA 1`/… na de baixo. Depois a mesma coisa passando
por `Bridge.handle_host_message` com SysEx de LCD do MCU como entrada.

Implementado em `command8_protocol.encode_lcd_text(row, strip, text)` e
`mcu_protocol.split_lcd_text(offset, text)`, ligados em `bridge.py`.

**Limitação conhecida:** `split_lcd_text` só trata offset alinhado ao início de um
strip (o que os hosts mandam na prática). Começar no meio de uma célula exigiria
read-modify-write, e não há como ler o conteúdo atual do visor.

## A velocity codifica REGIÃO, não canal — anomalia do 0x4C resolvida (2026-10-14)

A regra documentada antes ("velocity = 0x40 + canal") era um caso particular. O mapa
de regiões extraído do binário do V-Control Pro (strips 0-7, Mode 10, Top 11, Main 12,
Functions 13, Transport 14, Footswitch 16) mais a captura ao vivo fecham a fórmula real:

```
90 <índice do botão dentro da região> <0x40|0x00 + região>
```

| Evidência | Nota | Velocity | Região | Leitura |
|---|---|---|---|---|
| Select/Solo/Mute (ao vivo) | 0x00/0x02/0x03 | `0x40+0..7` | 0-7 | strips **são** as regiões 0-7 |
| Record (documentado antes) | `0x0B` | `0x4E` | 14 | Transport |
| Capturado 2026-10-14 | `0x0A` | `0x4E` | 14 | outro botão do Transport |
| **Anomalia `90 02 4C`** | `0x02` | `0x4C` | **12** | **Main** — não "canal 12 fora da faixa" |

A nota é o índice do botão **dentro** da região, o que bate com o mapa por strip do
binário (Select 0, SelectLED 1, Solo 2, Mute 3, RecordLED 4, FaderTouch 5) e com todas
as notas já confirmadas ao vivo.

**Consequência:** `decode_channel_button` exige canal 0-7 e por isso **rejeita
silenciosamente todos os botões globais** (transporte, Main, Mode, Top, Functions,
Footswitch). Ainda não corrigido — ver NEXT_SESSION.md.

## Sensor de toque do fader do canal 3 oscila sozinho (2026-10-14)

Com o hardware parado, sem ninguém encostar, a captura mostra:

```
90 05 42   fader canal 3 toque iniciado
90 05 02   fader canal 3 toque solto      ← repetindo a cada ~120-470ms
```

É o sensor capacitivo, não o motor (o "fader engasga" já documentado é mecânico, coisa
diferente). Vai sujar qualquer captura futura, e a ponte provavelmente precisa de
debounce pra não martelar o host com toque/solto várias vezes por segundo.

## Transporte nativo — MAPEADO AO VIVO (2026-10-14)

Bloco consecutivo na região 14, na mesma ordem da fileira física:

| Nota | Botão | MCU |
|---|---|---|
| `0x06` | Return to Zero | **não existe no MCU** |
| `0x07` | Rewind | 91 (`0x5B`) |
| `0x08` | Fast Forward | 92 (`0x5C`) |
| `0x09` | Stop | 93 (`0x5D`) |
| `0x0A` | Play | 94 (`0x5E`) |
| `0x0B` | Record | 95 (`0x5F`) |

Capturado apertando um botão de cada vez com a captura passiva rodando. O Record
(`0x0B`) já estava documentado de uma sessão anterior e bate, o que valida a série.

O RTZ fica decodificado como `"rtz"` mas **não é encaminhado** — o MCU não tem nota
equivalente, e inventar um mapeamento erraria o comportamento. Botão inerte por
enquanto, de propósito.

Implementado em `command8_protocol.decode_transport_button` +
`mcu_protocol.encode_transport_button`, ligado no `bridge.py`.

## Sessão completa sem o V-Control Pro — validada ao vivo (2026-10-14)

Com o V-Control Pro **fechado** e o controlador OSC dele removido do Logic, os cinco
caminhos foram exercitados em sequência e todos funcionaram:

| Teste | Caminho |
|---|---|
| Nome da faixa no visor | Logic → SysEx LCD do MCU → `split_lcd_text` → `encode_lcd_text` → vidro |
| Select / Solo / Mute | round trip nos dois sentidos, com LED |
| Fader físico → Logic | `decode_fader_position` → pitch bend MCU |
| Motor do fader | pitch bend MCU → `encode_fader_motor_position` |
| Play / Stop / Record | `decode_transport_button` → notas de transporte do MCU |

É a primeira vez que o hardware opera no Logic sem o app comercial no circuito.

## Meters, anéis de V-Pot, LEDs de transporte e contador (2026-10-14)

Capturados espelhando o V-Control Pro (`tools/midi_spy.py`) e validados no hardware.

### Meters — `90 <0x40 | barra de 5 bits> <canal>`

A barra preenche do bit 4 pra baixo: nível 0 = `0x40`, 1 = `0x50`, 2 = `0x58`,
3 = `0x5C`, 4 = `0x5E`, 5 = `0x5F`. Bate com o `numBits:5` que o binário do
V-Control Pro declara pra Command|8. O MCU manda `D0 <(canal << 4) | nível>` com
nível 0-12, escalado aqui pros 5 segmentos.

### LEDs de transporte — `90 <nota do botão> <0x40|0x00 + 14>`

Mesma nota e mesma região dos botões; `0x40 + região` acende, `região` apaga.
Confirmado no log (`90 0A 0E` = LED de Play apagando).

### Contador de posição — CC `0x40`-`0x49`, ASCII puro

O Logic manda a posição dígito a dígito, **um caractere ASCII por CC**, sem
codificação de 7 segmentos. `0x49` é o dígito mais à esquerda, `0x40` o mais à
direita. Formato do Logic: `BBB T D TTT` (compasso, tempo, divisão, ticks) —
`663 1 4150` é compasso 663, tempo 1, divisão 4, ticks 150.

São ~100 mensagens por segundo durante o playback; `timecode.TimecodeDisplay`
acumula os dígitos e libera no máximo 10 atualizações por segundo, senão o
SysEx de visor comeria quase metade da banda do MIDI.

### Anel do V-Pot — `F0 13 01 00 <canal> <bitmask de 7 bits> F7`

O opcode é `0x00` (display é `0x40`). **A implementação anterior, vinda de
documentação de terceiros, montava `F0 13 01 <canal> <máscara> F7` — sem o byte
de opcode — e nunca funcionou; só nunca tinha sido testada.**

O último byte é bitmask, um bit por LED: `0x7F` acende 7 LEDs em barra.

**Limitação conhecida, investigada e não resolvida:** o anel físico tem **11
LEDs**, mas um byte de dados MIDI carrega só 7 bits. Os LEDs restantes não se
mostraram alcançáveis por este opcode. Tentado sem sucesso:

- um segundo byte de valor no mesmo frame (`F0 13 01 00 <ch> <b1> <b2> F7`) —
  ignorado;
- endereço `canal + 8` como "metade de cima" — acendeu só mais 2 LEDs;
- inundar os endereços 0-31 com máscara cheia — chegou a ~10 LEDs, nunca aos 11.

A ponte usa a faixa de 7 que funciona, mapeando as 12 posições do MCU nela.
Modo 0 do MCU desenha ponto único (pan), os outros desenham barra. Fechar os
últimos LEDs provavelmente exige capturar o V-Control Pro **girando um pan de
verdade** pela porta espelhada — o método que resolveu o LCD.

### Disposição do visor

Copiando o original: contador em cima à direita (fileira 0, células `0x06`/`0x07`),
nomes de faixa na fileira de baixo (`0x10`-`0x17`), valores na fileira seguinte.
Constantes em `command8_protocol`: `LCD_ROW_FOR_MCU_LINE`, `LCD_TIMECODE_ROW`,
`LCD_TIMECODE_STRIPS`.

## Lacuna descoberta: a ponte não faz o handshake nativo

Reiniciando o hardware com a ponte sozinha, o visor passa a mostrar
**"Command|8 (Offline)"**. Durante toda a sessão de 2026-10-14 o hardware esteve
online por herança — o V-Control Pro o havia conectado antes e nós aproveitamos
esse estado. Há uma peça do protocolo de conexão que ainda não foi decodificada.

**Isso não impede o uso:** mesmo offline, o hardware aceita escrita de visor, LED
e anel normalmente (testado explicitamente — texto escrito com o dispositivo
offline apareceu no vidro). O que o "offline" afeta ainda não é claro.

## Console View — mapeado ao vivo (2026-10-14)

Apertando um botão de cada vez com captura passiva. Três blocos consecutivos,
seguindo a disposição física da mesa:

| Botão | Nota | Região |
|---|---|---|
| Pan | `0x00` | 10 (Mode) |
| Send | `0x01` | 10 |
| Insert | `0x02` | 10 |
| A | `0x03` | 10 |
| B | `0x04` | 10 |
| C | `0x05` | 10 |
| D | `0x06` | 10 |
| E | `0x07` | 10 |
| Default | `0x0C` | 10 |
| Mon/0 | `0x0D` | 10 |
| Display Mode | `0x08` | **11 (Top)** |

O inventário de nomes saiu do JSON de superfície embutido no V-Control Pro
(bloco `consolemode`); os números vieram da captura.

**Armadilha na captura:** a nota `0x05` do botão C é a mesma do toque de fader
nas regiões de strip. Um filtro de ruído que descarte `90 05 ..` sem olhar a
região engole esse botão — aconteceu, e deslocou o mapa inteiro por uma rodada.
A região é que distingue.

**Mapeamento pro MCU** (política da ponte, em `bridge.CONSOLE_TO_MCU`): Pan,
Send e Insert viram os botões de atribuição Pan/Surround, Send e Plug-in; A-E,
Default e Mon/0 viram F1-F7, que o usuário atribui no Logic sem mexer em código.
Display Mode não é encaminhado — reservado pra alternar o visor.

⚠️ **As notas de atribuição e de tecla de função do MCU (`mcu_protocol.ASSIGNMENT_NOTES`
e `FUNCTION_KEY_NOTES`) ainda não foram verificadas contra o Logic real.** Vieram
de conhecimento prévio do protocolo, não de captura.

### Estado da verificação do Console View (2026-10-14)

Confirmado ao vivo que os botões **chegam ao Logic como MIDI e são mapeáveis** por
Atribuições de Controlador (modo Learn).

As notas de atribuição do MCU (`ASSIGNMENT_NOTES`) **seguem sem veredito**: no teste,
Pan/Send/Insert não trocaram a visão do mixer — mas havia **duas pontes rodando**, com
a porta `Command8 MCU` duplicada e o Logic provavelmente ligado à instância antiga, sem
o código novo. O teste foi inconclusivo, não negativo. Refazer com uma ponte só.

## Mapa completo dos botões globais (2026-10-15)

Levantado ao vivo, apertando um bloco de cada vez com captura passiva. **55
botões** em cinco regiões; quatro delas contíguas, sem buraco, seguindo a
disposição física da mesa.

### Região 10 — Mode (`0x00`-`0x0D`)
Pan, Send, Insert, A, B, C, D, E, Shift/Add, Opt/Alt, Ctl/Clutch, Command,
Default, Mon/0.

### Região 11 — Top (`0x00`-`0x08`)
EQ, Dynamics, Insert, Pan/Send/Pre, Page Left, Page Right, Master Bypass, ESC,
Display Mode. Os extremos foram confirmados isoladamente (EQ `0x00`, ESC `0x07`),
e o miolo segue a ordem do JSON de superfície do V-Control Pro.

### Região 12 — Main
Enter `0x00`, Undo `0x01`, **`0x02` ainda desconhecido**, Rec `0x03`,
Pan/Meter `0x04`. O Rec daqui é o que arma gravação na faixa — não é o do
transporte, que fica na região 14.

### Região 13 — Functions (`0x00`-`0x0D`)
Flip, Master Faders, Bank, Nudge, Zoom, Left, Right, Up, Down, F1-F5.

### Região 14 (`0x00`-`0x0C`)
Plug-In, Mix, Edit, Loop Play, Loop Record, Quick Punch, RTZ, Rewind, Fast
Forward, Stop, Play, Record, Mem Loc. **O nome "Transport" herdado do binário é
estreito demais:** a região abriga também os botões de janela (Plug-In, Mix,
Edit) em `0x00`-`0x02`.

### Método, e o que deu errado

Inferir qual botão é qual **pela ordem dos apertos não é confiável**: um aperto
que não registra desloca o mapa inteiro, e isso aconteceu três vezes. O que
funcionou foi confirmar botões isolados como âncora e encaixar o resto entre
elas. Quando um bloco tem ordem conhecida (do JSON do V-Control Pro), duas
âncoras nas pontas bastam.

Armadilha de filtro: o sensor de toque de fader (nota `0x05`) gera ruído
constante em algumas faixas. Filtrar por nota engole o botão C da região Mode,
que também é `0x05`. **Filtrar por região** (velocity ≥ `0x48`) é o correto —
`scratchpad/ler.py` faz isso.

## Nome de faixa preservado durante o toque do fader (2026-10-15)

Comportamento padrão do MCU: ao tocar um fader, o host **sobrescreve a linha de
nomes** com o valor do parâmetro. Na Command|8 isso fazia o nome da faixa sumir
e dar lugar ao volume.

A ponte agora guarda o nome de cada strip e usa o estado de toque (que já
decodifica do hardware) para desviar: enquanto o fader do strip está tocado, o
texto que o host manda na linha 0 vai pra fileira de valores em vez da de nomes;
ao soltar, o nome guardado é reescrito.

**Depende do sensor de toque**, que já se mostrou instável em algumas faixas
(canal 1 e canal 3, em dias diferentes). Sensor oscilando faz o nome piscar — a
correção seria o debounce que segue pendente.

## Separador no contador de posição

O MCU manda os 10 dígitos sem separar divisão de ticks: `684 4 2197` é compasso
684, tempo 4, divisão 2, ticks 197. `timecode.format_for_display` insere o
espaço, resultando em `684 4 2 197`.

### Janela de carência após soltar o fader

O host manda uma **última atualização de valor logo depois da soltura**. Sem
tratamento, essa mensagem chega quando o canal já não consta como tocado, é
tomada por nome de faixa, sobrescreve o visor e ainda **envenena o cache** —
guardando algo como `-6.0dB` como se fosse o nome.

`bridge.TOUCH_GRACE_SECONDS` (0.5s) mantém o texto da linha 0 sendo tratado como
valor durante esse intervalo.

**Risco residual conhecido:** se o sensor perder a mensagem de soltura, o strip
fica marcado como tocado indefinidamente e o nome some até a ponte reiniciar.
Não tratado ainda — depende de ver se acontece na prática.

### O host apaga o nome do strip VIZINHO ao tocar um fader

Capturado com `COMMAND8_DEBUG=1`. Ao tocar o fader do canal 1, o Logic manda:

```
offset  0,  6 chars  'Volume'     ← rótulo do parâmetro no strip tocado
offset  7,  6 chars  '      '     ← APAGA o nome do strip vizinho
offset 56+, ...                   ← o valor em dB, na linha 1
```

O valor em dB vai pra linha 1, como esperado. O que fazia o nome sumir era o
**apagamento do vizinho** na linha 0 — não o valor.

Por isso a proteção vale para **todos os strips** enquanto houver qualquer fader
tocado, não só pro strip tocado: as duas escritas são transitórias e nenhuma
pode ser cacheada como nome de faixa.

Ao soltar, o Logic manda um refresh completo (`offset 0`, 111 chars, as duas
linhas e os oito strips de uma vez) que restaura tudo sozinho.

### Buffer espelho do visor (2026-10-15)

O host escreve em **qualquer posição**, não só no início de uma célula. Capturado
do Logic: as atualizações de valor chegam nos offsets 57, 58 e 59 — no meio da
célula. A implementação anterior (`split_lcd_text`) só tratava offsets alinhados
e **descartava o resto em silêncio**: de 66 atualizações de valor numa captura,
só 5 chegavam ao visor.

`lcd_buffer.LcdBuffer` espelha os 112 caracteres, aceita escrita em qualquer
offset e devolve só as células que mudaram de fato. Isso elimina a limitação de
alinhamento e evita reescrever célula igual.

`split_lcd_text` foi removida — o buffer a substitui por completo.

## Bank como modificador das setas (2026-10-15)

No desenho original da mesa, Bank/Nudge/Zoom modificam as setas. O MCU não tem
Bank modal — só Bank Left e Bank Right como botões próprios — então quem
implementa o modo é a ponte: segurando **Bank**, as setas esquerda/direita
mandam banco de canais em vez de cursor.

Isso dá acesso a todas as faixas do projeto usando botões que a mesa já tem, sem
depender de achar os Page Left/Right do Channel View.

**O LED é responsabilidade nossa.** Como a ponte intercepta o Bank e não o
encaminha, o host nunca vê esse aperto e nunca acende o LED. `encode_global_button_led`
acende e apaga, no mesmo formato do aperto (nota do botão, velocity = `0x40|0x00`
+ região). Vale pra qualquer botão que a ponte venha a interceptar no futuro.

Nudge e Zoom não precisam disso: o MCU tem botões próprios pra eles e o Logic
cuida do modo, então basta encaminhar.

### Rótulos de solo/mute também não podem virar nome

Apertar solo/mute/select faz o host escrever um rótulo ("Mute", "Muted", "Solo")
na linha de nomes — mesmo problema do toque de fader, gatilho diferente.

`BUTTON_LABEL_SECONDS` (1,5 s) abre a mesma janela de proteção a partir do
aperto. Diferente do fader, aqui não há nada a restaurar: como o rótulo é
desviado, o nome nunca chega a sair do visor.

## Render centralizado do visor (2026-10-15)

O visor físico **não é cópia fiel** do visor do MCU: quando há rótulo
transitório, a ponte desvia o conteúdo pra outra fileira pra preservar o nome da
faixa. Com só o espelho do MCU (`LcdBuffer`) decidindo o envio por diferença,
isso produzia células congeladas: o host reescrevia algo com o mesmo conteúdo de
antes, o espelho dizia "não mudou", nada era enviado — mas a célula do hardware
estava exibindo um rótulo desviado de instantes atrás. **Era a causa do visor
"aleatório".**

Agora são dois estados separados:

| Estado | O que guarda |
|---|---|
| `LcdBuffer` | o que o **host** mandou (espelho do MCU, 112 chars) |
| `NativeDisplay` | o que a **ponte desenhou** em cada célula nativa |

A cada evento, `Bridge._render()` calcula o conteúdo desejado de cada célula
(nome do cache, valor ou rótulo desviado) e manda só o que difere do que está no
hardware. Roda também nas transições de estado — toque, soltura e aperto de
botão de canal — não só quando chega texto.

Efeito colateral bom: o nome da faixa deixou de precisar ser "restaurado" ao
soltar o fader. Ele simplesmente nunca sai do visor.

## Motor silenciado durante o toque (2026-10-15)

Sintoma: "agarradinhas" leves ao mover o fader com a mão.

Causa: laço de realimentação. A posição sobe pro host, o host devolve, e a ponte
manda pro motor — que tenta reposicionar o fader que a mão está segurando. Os
dois brigam.

A ponte passa a ignorar comandos de motor para canais com o fader tocado.

**Nota histórica:** na sessão de 2026-08-27 esse "engasgo" foi diagnosticado como
mecânico, por desgaste do hardware. Na época o diagnóstico estava certo — a ponte
**ainda não dirigia o motor**. Quem o movia era o V-Control Pro. O laço só passou
a existir quando `encode_fader_motor_position` foi ligado.

## Anel do V-Pot — FECHADO, 11 LEDs (2026-10-15)

```
F0 13 01 00 <(4 LEDs altos << 3) | canal> <7 LEDs baixos> F7
```

O anel tem 11 LEDs e um byte de dados MIDI carrega 7 bits. Os quatro restantes
viajam nos **bits altos do byte que também leva o canal**: `canal = byte & 0x07`,
`LEDs altos = (byte >> 3) & 0x0F`.

Era por isso que o anel nunca fechava: a implementação usava um byte só e os
quatro LEDs de cima eram inalcançáveis.

### Como foi decodificado

Espelhando as portas com `tools/midi_spy.py`, apontando o V-Control Pro pra
`Command8 Spy Porta 1` e **girando um pan de ponta a ponta no Logic**. A
sequência capturada no canal 1 mostra o padrão na cara:

```
01 20 → 01 30 → 01 3C → 01 3E → 01 3F → 01 60 → 09 60 → 19 60 → 79 60
         └── enchendo os 7 baixos ──┘   └─ enchendo os 4 altos ─┘
```

Todas com `byte & 0x07 == 1` — o canal que estava sendo girado.

**Lição de método:** as sondas manuais anteriores (bit a bit, com o usuário
contando LEDs) custaram muitas rodadas e produziram descrições ambíguas que me
levaram a três modelos errados em sequência — nível 0-127, bitmask de 6 bits,
bitmask de 7. Capturar o app fazendo certo resolveu em uma tentativa, como já
havia acontecido com o LCD. **Quando existe um aplicativo que sabe falar o
protocolo, capturar é sempre mais barato que deduzir.**

## Nome de faixa: só refresh da linha inteira conta (2026-10-15)

As heurísticas anteriores tentavam adivinhar *quando* a linha 0 não era nome,
usando estado de toque, janela pós-soltura e janela de rótulo. Foram crescendo
em camadas e todas falharam de algum jeito, porque dependiam do sensor de toque
— que oscila sozinho em algumas faixas.

Sinal muito mais confiável, visto nas capturas: **nomes de verdade chegam num
refresh da linha inteira** (`offset 0`, 56+ caracteres), enquanto rótulos são
sempre escritas curtas num strip só (`Volume` com 6 chars, `Mute`, o
apagamento do vizinho em `offset 7`).

Regra atual: o cache de nomes só é atualizado por escrita com `offset == 0` e
comprimento ≥ 56. Simples, não depende de sensor nenhum, e permitiu remover toda
a maquinaria de escudo (`_showing_value`, janelas de carência e de rótulo).

Efeito: rótulos como `Volume` e `Mute` não aparecem no visor. Preservar o nome
vale mais — e a fileira livre de baixo está disponível caso se queira exibi-los.

## Duas superfícies no Logic: encadeamento, não duplicata

Com um segundo Mackie Control configurado (no caso, um controlador caseiro em
Pi Pico), o Logic **encadeia** as superfícies e dá offset de 8 à segunda:

```
Mackie Control #1 → porta Pico          offset 0 → canais 1-8
Mackie Control #2 → porta Command8 MCU  offset 8 → canais 9-16
```

A Command|8 mostrando canais 9-16 não é bug, é layout. Bank esquerda/direita
move a cadeia inteira, então a Command|8 fica sempre 8 à frente.

Se algo parecer "preso num banco estranho", esta tela é o primeiro lugar a
olhar — mas **não apague a superfície antes de conferir a porta de cada uma**.

## A oscilação do visor éramos nós (2026-10-15)

Sintoma: o visor alternando sozinho entre volumes, pans e nomes, sem parar, sem
ninguém encostar no hardware.

Diagnóstico, com as duas pontas instrumentadas na mesma linha do tempo
(`COMMAND8_DEBUG_LCD=1` loga o que chega do Logic **e** o que sai pro visor):

```
[logic ] offset  0 len  6 'Pan   '
[logic ] offset  0 len 55 'VX  GTR  BAIXO  TECLAD DRUM  FonAzl 9.0sAb FonVer'
[logic ] offset  0 len  6 'Select'
[logic ] offset  7 len  6 'Volume'
```

O Logic percorria strip por strip reanunciando `Volume`, `Pan`, `Select` e os
valores. Isso é **reinicialização de superfície**, e quem pedia éramos nós:

```python
while not handshake_done:
    host_out.send_message(mcu.encode_device_query())
    time.sleep(2)
```

O handshake formal **nunca completa** contra o Logic (documentado desde agosto),
então esse laço reenviava Device Query a cada 2 segundos para sempre, e cada
envio fazia o Logic reapresentar a superfície inteira. O visor nunca estabilizava
— e o contador de posição sumia junto, afogado na enxurrada.

Mudança feita: parar de insistir assim que o host der qualquer sinal de vida
(ele manda dados reais independente do handshake), com teto de
`MAX_DEVICE_QUERIES` tentativas como rede de segurança.

> **⚠️ CORREÇÃO: o Device Query NÃO era a causa.** A oscilação continuou idêntica
> depois dessa mudança. O teto de tentativas se justifica por si só — não faz
> sentido pedir reapresentação pra sempre — mas não foi ele que resolveu.
>
> **A causa real era o estado da superfície dentro do Logic.** Ao longo da sessão
> a porta virtual `Command8 MCU` apareceu e sumiu umas vinte vezes com os
> reinícios da ponte, e o Logic acumulou estado inconsistente em cima disso.
> **Recriar a superfície e reabrir o Logic resolveu.**
>
> Medições que sustentam isso: Command|8 muda (0 mensagens em 10 s), Pico mudo
> (0 em 8 s), V-Control Pro fechado. Nenhuma fonte MIDI alimentava o laço — o
> Logic girava sozinho.
>
> **Se o visor voltar a oscilar: antes de mexer em código, feche o Logic, suba a
> ponte, e só então abra o Logic.** A ordem importa, porque assim a porta já
> existe quando ele inicializa a superfície.

**Lição:** o sintoma apareceu como "visor aleatório" e eu persegui a causa dentro
da lógica de render por horas, fazendo cinco mudanças em sequência que
degradaram o que funcionava. A instrumentação dos dois lados juntos — que eu
devia ter feito no primeiro relato — apontou a causa em uma leitura. **Quando o
sintoma é "está estranho", instrumentar vem antes de hipotetizar.**

### Desenho do anel: pan cresce do centro

O byte é bitmap de LED, mas **o desenho depende do modo** que o MCU manda:

| Modo MCU | Desenho | Uso |
|---|---|---|
| 0 | ponto único | — |
| 2 (wrap) | barra da esquerda até a posição | nível, send |
| outros | barra **do centro** até a posição | pan |

O centro é o LED 5, o sexto de onze. A varredura capturada do V-Control Pro
girando um pan confirma: todo à esquerda acende os bits 0-5, o centro só o bit
5, todo à direita os bits 5-10.

Antes desta correção, qualquer modo diferente de 0 desenhava barra da esquerda —
e na posição máxima isso acendia os onze LEDs de uma vez, que foi o sintoma
relatado ("pan 2 com todos os LEDs acesos").

## Quando parar de pedir apresentação ao host (2026-10-16)

O host manda a linha de nomes em **eventos** — quando a superfície conecta,
quando se troca de faixa ou de banco. Ele **não reenvia** por conta própria. Se a
ponte sobe depois de o host já ter anunciado, os nomes passaram e o visor fica
sem eles até o usuário mexer em alguma coisa.

Por isso a ponte manda Device Query na subida: o host responde reapresentando a
superfície inteira. O critério de parada importa:

| Critério | Efeito |
|---|---|
| nunca parar | visor nunca estabiliza (bug de 15/10) |
| parar na 1ª mensagem qualquer | medidor chega antes da apresentação → **sem nomes** |
| parar no 1º **texto de visor** | ✅ pega a apresentação e para |

Teto de `MAX_DEVICE_QUERIES` como rede de segurança, caso o host nunca mande
texto.

## A superfície tem MODOS, e um deles custou horas (2026-10-16)

Sintoma: nomes de faixa sumiram do visor, anéis apagados, texto estranho
(`Cr w/o  Create  Delete`) nas últimas colunas. Parecia visor quebrado.

Era o **modo Marcador** do Logic. A linha completa que ele mandava dizia tudo:

```
linha 0: 'Markr1                             Cr w/o Create Delete'
linha 1: 'INSIDE                             Cr w/o Create Delete'
```

`Markr1` = Marker 1, `INSIDE` = nome do marcador, e as três últimas colunas são
as ações de marcador. **Comportamento correto da Mackie Control**, exibido
fielmente pela ponte.

Como entramos: no levantamento dos 55 botões, apertamos **todos** — inclusive o
Mem Loc, que a ponte mapeia pro marcador do MCU. O modo ligou e ficou.

**Como sair:** apagar e recriar a superfície Mackie Control no Logic. Os botões
de atribuição (Pan/Send/Insert) e o Mem Loc não tiraram — provavelmente porque
as notas em `NAMED_NOTES` ainda não foram verificadas contra o Logic real.

### Lição de diagnóstico

O texto estava visível desde a primeira captura, mas eu lia **célula por célula**
(`'Cr w/o '`, `'Create '`) em vez da **linha completa** que o host manda. Lendo a
mensagem inteira, `Markr1` e `INSIDE` apareciam no começo e o diagnóstico era
imediato.

Quando o visor parecer errado: **leia a linha `[logic ]` inteira antes de olhar
as células**. O host manda contexto no começo da mensagem.

