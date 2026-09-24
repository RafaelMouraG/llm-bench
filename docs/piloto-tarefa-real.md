# Piloto com a tarefa real — resultados parciais

Data: 24/09/2026. Registro das primeiras tentativas da tarefa do encurtador ([contrato](contrato-encurtador.md), Parte A) executadas com o [runner da coleta](../infra/attempt/README.md) e avaliadas pelo [avaliador](avaliador.md) 0.2.0. **Nenhuma tentativa é oficial nem entra na análise do benchmark.** Os resumos registram `official_collection: false` e `phase: "piloto"`.

O piloto está **incompleto**: foram executados MiMo (duas vezes; a segunda a pedido de Rafael, com o runner corrigido) e Muse. **Rafael retirou o MiMo** depois das duas entregas vazias (§3.1), sem substituto: a coleta segue com Opus, Sol e Muse. Opus e Sol não foram executados para preservar a cota do plano Pro e do Codex (§7).

Rafael autorizou em 24/09/2026 enviar a Parte A do contrato às rotas gratuitas Muse e MiMo, sabendo que os dados podem ser usados para treino ([condições das rotas](../infra/pilot/README.md)). Só a Parte A foi enviada. A Parte B e os checks não saíram do computador.

## 1. Configuração comum

| Item | Valor observado |
|---|---|
| Imagem | `llm-bench-runtime:20260924`, ID `sha256:aa1c6322f54a…39eb`, a mesma nas três tentativas e nas avaliações |
| Harness | OpenCode 1.18.32 nas três tentativas |
| Configuração do runner | `infra/attempt/config.json`, SHA-256 `15781e13…908e` nas três. O código do runner mudou antes da repetição do MiMo (§4.1 e §4.2), sem alterar configuração, prompt, rede ou recursos; o resumo não registra o hash do script. Depois das três, a entrada `mimo` foi removida da configuração, e o hash mudou para as próximas tentativas |
| Prompt | Preâmbulo + Parte A; contrato `21d9aa5a…91c7`, Parte A `f2dfdada…2910`, prompt `5ae1536c…c147`. Único placeholder: prazo de prontidão = 60 s |
| Prazo por tentativa | 3600 s, com 10 s de tolerância (provisório) |
| Recursos | 4 GiB, 2 CPUs, 512 processos; tmpfs com home de 2 GiB e `/tmp` e workspace de 1 GiB (provisório) |
| Skills | Nenhuma |
| Avaliador | 0.2.0, parâmetros provisórios de `evaluator/config.json` (prontidão 60 s, expiração 4 s, n/m/p = 50/20/50) |

Nas três tentativas, a preparação confirmou home e workspace vazios, UID 1001, ausência do home do host e do socket Docker. A rede confirmou `pypi.org` alcançável, `example.com` bloqueado pelo proxy e saída direta a IP bloqueada. Nenhuma credencial foi provisionada (as rotas gratuitas não usam credencial), e `contains_credentials` ficou `false`.

## 2. Tentativas executadas

Executadas uma de cada vez, na ordem MiMo, Muse e, depois das correções do runner, a repetição do MiMo. Horários em UTC. "Tarefa" é o `docker exec` do harness; "total" inclui preparação, congelamento, limpeza e avaliação.

| Tentativa | Participante | Prazo | Saída | Tarefa (s) | Total (s) | Entrega | A_i | S/V/U |
|---|---|---|---|---|---|---|---|---|
| `20260924T173254Z-mimo-1c9c89` | MiMo, `opencode/mimo-v2.6-flash-free`, sem variante | 3600 s | 0 | 254,5 | 257,0 | **vazia**: 0 entradas | **0** | 0 / 1 / 34 |
| `20260924T173758Z-muse-f55ab6` | Muse, `opencode/muse-spark-1.3-contributor-free`, xhigh | 3600 s | 0 | 602,5 | 611,5 | 4 arquivos, tar de 30 KiB | **1** | 35 / 0 / 0 |
| `20260924T180503Z-mimo-393380` | MiMo, repetição com o runner corrigido | 3600 s | 0 | 958,1 | 960,3 | **vazia**: 0 arquivos | **0** | 0 / 1 / 34 |
| — | Opus, `claude-opus-5-5`, high | — | — | — | — | — | — | **Não executado** |
| — | Sol, `gpt-6-sol`, high | — | — | — | — | — | — | **Não executado** |

Nas três tentativas:

- `timed_out: false`, nenhum processo remanescente antes do congelamento e `errors: []` no resumo.
- Destinos no proxy: `ALLOW` só para `opencode.ai`, `models.opencode.ai`, `registry.npmjs.org` (dependências do próprio OpenCode) e `pypi.org` (verificação de rede do runner). O único `DENY` é `example.com:443`, da verificação de rede do runner. O agente não tentou nenhum destino bloqueado. Na repetição do MiMo houve um `CONNECT_FAILED registry.npmjs.org` entre 27 `ALLOW`, numa conexão do próprio OpenCode ao baixar dependências; não afetou a tentativa.
- A limpeza da tentativa e da avaliação retornou 0 em todos os containers e redes, sem sobras.
- Nas duas primeiras, `session_exported: false` e `reported_models: []`: o modelo servido não ficou registrado (§4.1). Na repetição do MiMo, com o runner corrigido, a sessão foi exportada (142.965 bytes, acima do limite de 128 KiB que truncava o método antigo) e o harness informou `mimo-v2.6-flash-free`, variante `default`.

### 2.1 Consumo informado pelo harness (M14)

Soma dos eventos `step_finish` do OpenCode. `input_includes_cache` continua `null` (não verificado). Custo informado 0 nas duas rotas gratuitas; a estimativa de M9 fica ausente, não zero, como no [piloto de infraestrutura](piloto-infraestrutura.md) §5.

| Tentativa | Passos | Entrada | Saída | Raciocínio | Cache lido | Cache escrito | Custo informado |
|---|---|---|---|---|---|---|---|
| MiMo | 2 | 6.334 | 121 | 32.019 | 9.664 | 0 | US$ 0 |
| Muse | 45 | 110.239 | 19.435 | 26.845 | 1.993.693 | 0 | US$ 0 |
| MiMo (repetição) | 2 | 557 | 103 | 32.010 | 15.232 | 0 | US$ 0 |

## 3. Resultados e diagnóstico

### 3.1 MiMo: entrega vazia nas duas tentativas

**V: RNF01.** `./build.sh` terminou com código 127 (`No such file or directory`). O `delivery.tar` tem só a entrada `./`, e o hash da árvore é o SHA-256 da entrada vazia (`e3b0c442…b855`). Os outros 34 requisitos ficaram **U** pela pré-condição do build, conforme a regra do avaliador (§3). **Diagnóstico: falha real da entrega.** O avaliador está correto: não havia `build.sh`.

Causa, pelo `stdout.jsonl`:

1. **Primeiro passo (+3 s):** duas chamadas `bash` de reconhecimento (versões das ferramentas e variáveis de ambiente), terminado com `reason: tool-calls`.
2. **Segundo passo:** durou cerca de 249 s e terminou com **`reason: length`**, com 32.005 tokens de raciocínio e **0 de saída**. É o teto de saída de 32 mil tokens do modelo no catálogo. O modelo consumiu o limite inteiro raciocinando antes de emitir qualquer chamada de ferramenta.
3. **Fim:** o `opencode run` encerrou com código 0 depois desse passo, sem continuar e sem escrever arquivo algum.

Classificação: o provedor respondeu e a infraestrutura funcionou (rede, runner, congelamento, avaliação e limpeza). Não é falha operacional da infraestrutura. É um resultado observado da configuração participante: um passo de raciocínio do modelo esbarrou no limite de saída, e o harness trata `length` como término. A GQM (§4) manda registrar entrega vazia como resultado observado, e não como exclusão automática. Se esse caso conta como falha da entrega ou como problema operacional do harness/provedor (§6) é decisão do protocolo. A primeira tentativa não foi repetida automaticamente. Rafael pediu a repetição depois das correções do runner.

**Repetição (`20260924T180503Z-mimo-393380`).** Mesmo prompt (`5ae1536c…`), configuração e imagem. O resultado foi idêntico: RNF01 V pela ausência de `build.sh` e 34 U. O runner corrigido registrou os dois avisos novos: entrega sem arquivos e término por limite de saída (`harness_end.last_reason: length`).

- **Primeiro passo:** duas chamadas `bash` de reconhecimento em menos de 2 s.
- **Segundo passo:** começou aos +29 s e terminou aos +931 s, com `reason: length`, 32.001 tokens de raciocínio e 0 de saída. Mesmo número de tokens da primeira tentativa, em cerca de 3,6 vezes o tempo; a vazão do provedor variou.
- A sessão exportada confirma: o modelo `mimo-v2.6-flash-free`, provedor `opencode`, `finish: length`, sem `error`, e um único bloco de raciocínio de 122.603 caracteres, sem nenhuma parte `tool` no segundo passo.

**O que o modelo fez no raciocínio.** Contagem sobre o texto da sessão, tratado como dado:

- O raciocínio começa decidindo pela stack: Python com a biblioteca padrão, `ThreadingHTTPServer` e SQLite, a mesma do Muse.
- Em seguida, escreve a implementação dentro do próprio raciocínio: 178 delimitadores de bloco de código, 96 `def`, 35 `class` e trechos repetidos, como o `CREATE TABLE`, sinal de versões sucessivas.
- Revisa detalhes sem parar: 55 "Hmm", 45 "Actually" e 19 "Wait".
- O limite o interrompe numa dúvida sobre `server_close` e `block_on_close` do `ThreadingHTTPServer`, sem ter chamado a ferramenta de escrita.

**Leitura.** Em duas de duas tentativas, o MiMo tentou resolver a tarefa inteira num único passo de raciocínio, em vez de escrever arquivos e iterar com as ferramentas, e esgotou o teto de 32 mil tokens de saída. Não é falta de contexto: o passo usou cerca de 8 mil tokens de entrada, e a janela é de 200 mil. Também não é falta de tempo: a tentativa usou 7% e 27% do prazo. Com o catálogo sem variantes de esforço, a configuração atual não oferece como limitar esse raciocínio. Duas tentativas não medem a frequência, mas indicam que o padrão não é ocasional.

### 3.2 Muse: 35 S

**Sem V nem U.** `A_i = 1`, M3 = 35/35. RN13 conferiu 55 respostas de erro, o mesmo número da referência. RNF06 contou 50 visitas simultâneas. Não houve erro interno do avaliador.

Entrega e stack (M15):

- **Arquivos:** `README.md`, `build.sh`, `start.sh` e `server.py` (cerca de 20 KB).
- **Stack:** Python 3.11 só com a biblioteca padrão: `ThreadingHTTPServer`, SQLite em `DATA_DIR/links.db` com WAL e `synchronous=FULL`, e um `threading.Lock` global. É a mesma stack da referência do avaliador.
- **Dependências:** nenhuma. Sem manifestos nem lockfiles (`has_lock: false`, `manifests: []`). O lock não se aplica.
- **`build.sh`:** só `python3 -m py_compile server.py`. **`start.sh`:** usa `exec python3 server.py`.

Diagnóstico da avaliação:

| Item | Valor |
|---|---|
| Build | código 0 em 0,06 s, sem destinos no proxy |
| Prontidão (RNF02) | 0,07 s nos três inícios |
| SIGTERM (RNF10, diagnóstico) | processo e grupo encerrados em 0,05 s nos três inícios |
| Arquivos alterados fora de `DATA_DIR` | 0 |
| Isolamento | três sondas bloqueadas |
| Avaliação | 7,5 s |

Linha do tempo do agente, contada do início da tarefa:

- **+116 s:** primeira chamada de ferramenta.
- **+238 s:** primeiro arquivo escrito (`server.py`).
- **+255 s:** entrega completa pela primeira vez, com os quatro arquivos; o build passa aos +259 s.
- **+259 s a +567 s:** testes locais, três correções no parser de RFC 3339 e remoção dos scripts de teste e dados temporários.
- **+603 s:** mensagem final. Usou cerca de 17% do prazo.

Para a revisão qualitativa, não para a aceitação: os scripts de teste `run_tests.py`, `run_tests2.py` e `finalcheck_script.py` foram apagados antes do fim. A seção "Testes automatizados" do README traz só um script para colar no terminal, com o servidor rodando.

## 4. Problemas do instrumento encontrados

O avaliador e o contrato não foram alterados. Os problemas de §4.1 e §4.2 foram corrigidos no runner depois das duas primeiras tentativas, a pedido de Rafael. Os `summary.json` delas continuam como foram gravados. A repetição do MiMo é uma tentativa nova, registrada ao lado da primeira, que ela não substitui.

### 4.1 Runner: exportação da sessão do OpenCode falhou nas duas primeiras tentativas (corrigido)

`session_exported: false` e `reported_models: []` nas duas. Havia uma única sessão em cada `stdout.jsonl`, então o runner chamou `opencode --pure export <id>`, e a saída não foi JSON válido. Os eventos `--format json` do OpenCode não trazem o identificador do modelo, então **o modelo e a variante efetivamente usados não ficaram registrados**. No piloto de infraestrutura, o mesmo código registrou `mimo-v2.6-flash-free`/`default` e `muse-spark-1.3-contributor-free`/`xhigh`.

**Causa, reproduzida sem modelo:** no OpenCode 1.18.32, a saída do `export` escrita num pipe, como a do `docker exec`, é truncada em 128 KiB, e o processo sai com código 0.

Reprodução, num container da mesma imagem e sem rede, com sessões importadas de 9 KB, 62 KB, 206 KB e 820 KB:

- escrito num arquivo, o `export` saiu completo em todos os tamanhos;
- pelo stdout do `docker exec`, as sessões de 206 KB e 820 KB saíram com 163.840 e 131.072 bytes e JSON inválido.

Isso explica por que funcionava no piloto de infraestrutura: as sessões sintéticas eram pequenas. As sessões desta tarefa passam do limite: o prompt tem 6 KB, e só o raciocínio do MiMo foi de 32 mil tokens. Os primeiros testes, com sessões vazias, não reproduziram a falha.

**Correção em `scripts/run-attempt.py`:**

- O `export` grava num arquivo em `/tmp` do container, lido em seguida com `cat`.
- `session_export` registra o código de saída, o stderr, o tamanho e o erro.
- A falha vira aviso (§4.2).

O `scripts/run-pilot.py` tem o mesmo padrão de exportação e não foi alterado.

**As duas primeiras tentativas continuam sem o modelo servido registrado:** a sessão só existia no container descartado.

### 4.2 Runner: término por limite de saída não fica visível (corrigido)

A tentativa do MiMo terminou com `exit_code: 0`, `ok: true` e `errors: []`, embora o harness tenha parado por `reason: length` e a entrega esteja vazia. É o comportamento definido: `ok` descreve a execução, não o resultado. Mas o resumo não registra o motivo do último passo nem destaca `entries: 0`. **Correção:**

- `summary.json` passa a ter `harness_end`: o `reason` dos `step_finish` no OpenCode, `subtype` e `stop_reason` no Claude Code, e os tipos de evento no Codex, este não validado. O campo `output_limit_hit` indica término por limite de saída.
- `delivery.files` conta só arquivos.
- Nova lista `warnings`: entrega sem arquivos, término por limite de saída, sessão não exportada e última linha do stdout que não é JSON.
- Os avisos não mudam `ok`, o código de saída nem o veredito.

Aplicado ao `stdout.jsonl` salvo do MiMo, `harness_end` dá `last_reason: length` e `output_limit_hit: true`. O formato do Claude Code foi testado só com eventos sintéticos.

### 4.3 Configuração do OpenCode: `external_directory` bloqueia `/tmp`

Com `permission: {"*": "deny", …}`, a regra padrão `external_directory` do OpenCode fica em `ask`, e no `opencode run` não interativo isso vira recusa. Aos +261 s e +266 s, o Muse tentou usar `/tmp/testdata` e `/tmp/opencode/data1` e recebeu "The user has specified a rule which prevents you from using this specific tool call". Ele passou a gravar os dados de teste em `/workspace/testdata` e os apagou antes do fim.

Efeitos:

- Diferença de paridade com o Claude Code, que pode usar `/tmp`.
- Risco de dados de teste ou `DATA_DIR` locais ficarem na entrega.
- Comandos que referenciem `~/.m2`, `~/.cache` ou `/tmp` explicitamente também seriam recusados.

A configuração de permissões está marcada "provisório — decidir". Sugestão: decidir se `external_directory` deve ser `allow` para `/tmp/**` e `/home/agent/**`, e registrar a decisão.

### 4.4 Observação do harness: bash espera processo em background

Aos +275 s, o Muse iniciou o servidor com `nohup … &` na ferramenta bash. A chamada só voltou depois de 120 s, o timeout padrão da ferramenta no OpenCode, porque o processo herdou a saída. É comportamento do harness, não do runner, mas consome prazo e pesa no tempo (M8) de agentes que testam servidores. Fica registrado para interpretar M8.

### 4.5 Avaliador

Nenhum problema encontrado. O único V (RNF01 do MiMo) corresponde à entrega vazia, e os 35 S do Muse não mostram check suspeito: a evidência de RN13 e RNF06 bate com a da referência. As avaliações sobre a entrega do Muse não exercitaram nada além do que os controles já cobrem, porque a stack é a mesma da referência.

## 5. Implicações para os parâmetros provisórios

Duas tentativas, uma delas sem entrega, não bastam para calibrar. O que elas indicam:

| Parâmetro | Observação | Sugestão |
|---|---|---|
| Prazo por tentativa (3600 s) | MiMo terminou em 255 s, por limite de saída e não por prazo. Muse terminou por conta própria em 602 s (17%) e tinha a entrega completa, com build passando, aos 259 s | Manter 3600 s até observar Opus e Sol. Nada indica que o prazo limita; reduzir exige mais tentativas e stacks mais pesadas |
| Prazo de prontidão (60 s) | Python da biblioteca padrão: 0,07 s | Sem informação para JVM, Node ou Go; o dado que falta continua sendo a partida da JVM |
| Expiração (4 s) e n/m/p (50/20/50) | Muse passou em RF09 e RNF06–RNF08 sem U por relógio | Nenhum ajuste indicado |
| Recursos do container | Nenhum erro de memória ou processos. O runner não mede o pico de memória nem o uso dos tmpfs | Registrar o pico de memória do cgroup e o uso dos tmpfs antes de calibrar |
| Tamanho da entrega | 30 KiB (Muse); tmpfs de 1 GiB muito folgado para esta stack | Sem ajuste antes de uma entrega com `node_modules`, `.venv` ou cache Maven |
| Lockfile (C5) | Muse não tem dependências; `has_lock: false` não significa lock ausente | Registrar à parte "sem dependências" e "dependências sem lock" |
| Permissões do OpenCode | `external_directory` recusado (§4.3) | Decidir antes da coleta |

## 6. Limpeza

Ao final, `docker ps -a` e `docker network ls` com o filtro `llmbench-` não listaram nada. Os containers de diagnóstico e de teste da correção da §4.1 (`llmbench-diag-export*`) rodaram sem rede e sem modelo, e foram removidos. As verificações da correção (`simulado` e harness `shell`) também não deixaram sobras. Evidências locais em `.pilot/attempts/<run_id>/`, ignorado pelo Git: `summary.json`, `prompt.md`, `stdout.jsonl`, `stderr.txt` (vazio nas duas), `proxy.log`, `delivery.tar` e `eval/`. Não publicar sem revisão.

## 7. O que falta

- **Opus** (`claude-opus-5-5`, high): depois da renovação da cota do plano Pro. Primeira tentativa real com o Claude Code no runner da coleta: `harness_init`, `tools_mismatch` e consumo no formato do Claude Code.
- **Sol** (`gpt-6-sol`, high): por último, para preservar a cota do Codex. Valida também a extração de consumo no formato do Codex.
- **MiMo:** retirado por Rafael em 24/09/2026, depois das duas entregas vazias (§3.1), sem substituto. As tentativas continuam neste registro. Continua em aberto como o protocolo classifica o término por limite de saída, que pode ocorrer com outros participantes.
- **Runner corrigido em tentativa real:** a repetição do MiMo confirmou a exportação da sessão (143 KB) e os avisos de §4.2 no OpenCode. Falta confirmar `harness_end` no Claude Code e no Codex.
- **Stack diferente de Python:** nenhuma entrega exercitou JVM, Node ou Go. A calibração do prazo de prontidão continua pendente.
