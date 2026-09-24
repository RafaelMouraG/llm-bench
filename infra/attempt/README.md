# Runner da coleta

`scripts/run-attempt.py` executa uma tentativa da tarefa do encurtador: o agente roda inteiro num container novo, a entrega é congelada e o [avaliador](../../docs/avaliador.md) a verifica num ambiente limpo. Nenhuma tentativa é oficial enquanto o protocolo não for congelado; o resumo registra `official_collection: false` e `phase: "piloto"`.

Estado em 24/09/2026: validado só **sem modelo**, com o participante `simulado` e testes de timeout e de registro da configuração (§4). Nenhuma tentativa real com os participantes foi executada.

## 1. Execução

Na raiz do repositório, com Docker, os três CLIs e a imagem `llm-bench-runtime:20260924`:

```sh
python3 scripts/run-attempt.py opus --dry-run    # prompt, rede e comando, sem containers nem credenciais
python3 scripts/run-attempt.py simulado          # ponta a ponta sem modelo: copia a referência
python3 scripts/run-attempt.py opus              # tentativa real; também muse, mimo e sol
python3 scripts/run-attempt.py mimo --timeout 1800 --no-evaluate
```

Cada comando executa uma única tentativa, sem repetição automática. A ordem e o número de repetições são decisões do protocolo. Os parâmetros estão em [config.json](config.json); os marcados "provisório" ainda não foram decididos (§5).

O código de saída é 0 quando a tentativa foi executada, congelada e avaliada sem erro operacional e sem sobras. Não depende de `A_i`: uma entrega rejeitada é um resultado, não uma falha do runner.

## 2. Fluxo

1. **Prompt.** O preâmbulo de `config.json` seguido da Parte A do [contrato](../../docs/contrato-encurtador.md), sem o título de coordenação. O único placeholder, o prazo de prontidão em A2, recebe o valor que o avaliador usa (`evaluator/config.json`, hoje 60 s). O runner recusa enviar o texto se restar `[A DEFINIR]`, `Parte B` ou `reservad`. Registra os SHA-256 do contrato, da Parte A e do prompt e salva `prompt.md`.
2. **Rede.** Rede Docker `--internal` e o proxy da imagem (`/opt/pilot/proxy.py`), liberando CONNECT na porta 443 para os domínios do provedor do participante e os seis registros de pacotes. Nenhuma porta é publicada no host.
3. **Container do agente.** Mesmas restrições do piloto e da validação da imagem:
   - raiz somente leitura, UID 1001, `--cap-drop ALL`, `no-new-privileges` e `--init`;
   - tmpfs **com `exec`** em `/tmp`, `/home/agent` e `/workspace`;
   - `sleep infinity` como processo principal, porque o `sleep 1200` da imagem encerraria o container no meio de uma tentativa longa.
4. **Provisionamento.**
   - O home e o workspace começam vazios, o que é verificado.
   - Recebem só a credencial do próprio participante, pelo mecanismo do piloto: stdin e permissão 0600 no tmpfs.
   - O harness recebe a configuração, e `~/.m2/settings.xml` recebe o proxy, como A2 promete ("O Maven já vem configurado com o proxy").
   - A rede é conferida: `pypi.org` alcançável, `example.com` bloqueado pelo proxy e saída direta a IP bloqueada. Se a verificação falhar, a tentativa não começa.
5. **Tentativa.** O harness roda em `/workspace` sob `timeout` com SIGTERM e, depois da tolerância, SIGKILL. O sinal vai ao grupo de processos do comando.
6. **Congelamento.**
   - Processos remanescentes, como servidores em segundo plano, são encerrados.
   - O `/workspace` inteiro é empacotado em `delivery.tar`, com permissão 0600. Pelo contrato, o conteúdo do diretório é a entrega; home e `/tmp` são descartados.
   - Registra o SHA-256 do tar, o hash da árvore (o mesmo do avaliador), os manifestos e lockfiles e se a entrega contém algum valor de credencial.
7. **Limpeza.** Containers e rede `llmbench-attempt-<run_id>-*` são removidos num `finally`, e a ausência de sobras é conferida.
8. **Avaliação.** `evaluator/evaluate.py` roda sobre `delivery.tar`, depois da limpeza, em containers novos. O resumo da tentativa traz `A_i`, S/V/U e os requisitos V e U.

## 3. Evidências

Ficam em `.pilot/attempts/<run_id>/`, que o Git ignora e que tem permissão 0700:

- `summary.json`;
- `prompt.md`;
- `stdout.jsonl` e `stderr.txt`, com credenciais conhecidas redigidas;
- `proxy.log`;
- `session.json`, quando o harness é OpenCode;
- `delivery.tar`;
- `eval/`.

O `summary.json` registra:

- **Configuração:**
  - participante, modelo solicitado, esforço, imagem e ID, versão do harness, recursos, prazo e comando (com o prompt substituído por referência);
  - arquivo e hash da configuração do runner;
  - skills (nenhuma) e hosts liberados.
- **Configuração efetiva do Claude Code**, em `harness_init`: ferramentas, skills e agentes embutidos, plugins, modo de permissão e versão. Quando as ferramentas efetivas diferem das pedidas, o resumo traz `tools_mismatch`.
- **Tempos (M8):** horários UTC de início, início e fim da tarefa, congelamento e término, além das durações.
- **Consumo (M14):** extraído com as funções validadas do `run-pilot.py`, na semântica de cada harness. Fica `null` quando não é observável.
- **Modelos e variantes informados pelo harness.**
- **Entrega, avaliação, destinos vistos pelo proxy, processos encerrados antes do congelamento e códigos de limpeza.**

Não publicar esses arquivos sem revisão: o stdout do agente e a entrega podem conter trechos inesperados.

## 4. Validação em 24/09/2026

Nenhuma destas execuções chamou modelo ou leu credencial.

| Verificação | Resultado |
|---|---|
| `--dry-run opus` | Prompt com A1–A7, prazo de 60 s preenchido e nada da Parte B; hosts do provedor mais os seis registros |
| `simulado`, ponta a ponta | Preflight e rede OK (`ALLOW pypi.org`, `DENY example.com`); entrega congelada com o mesmo hash de árvore do diretório de referência; avaliação `A_i = 1`, 35 S; limpeza sem sobras; cerca de 9 s |
| Estouro de prazo (harness `shell` de teste, prazo de 60 s) | Código 124; arquivo parcial congelado e arquivo "tarde" ausente; servidor em segundo plano encerrado; limpeza sem sobras |
| Flags do Claude Code 2.1.281, offline | Aceitas. `TodoWrite` e nomes inexistentes são ignorados sem erro, o que motivou o registro de `harness_init` e `tools_mismatch`, testado com um evento `init` sintético |
| Configuração do OpenCode 1.18.32, offline | `opencode debug config` resolve as permissões configuradas |

O harness `shell` só é aceito por um `--config` alternativo; ele não existe na configuração padrão.

## 5. Decisões provisórias e pendentes

Estão em `config.json` e não foram decididas por Rafael:

- **Prazo por tentativa:** 3600 s, com 10 s de tolerância. Calibrar no piloto com a tarefa real (C3).
- **Recursos do container:**
  - 4 GiB de memória, 2 CPUs e 512 processos;
  - tmpfs com home de 2 GiB e `/tmp` e workspace de 1 GiB.
  A memória de tmpfs conta no limite.
- **Texto do preâmbulo do prompt:** idêntico para todos os participantes. Diz que não há interação humana, que `/workspace` é o diretório de trabalho e que seu conteúdo é a entrega.
- **Ferramentas e permissões por harness:**
  - Claude Code: Bash, Read, Write, Edit, Glob e Grep.
  - OpenCode: bash, read, edit, glob, grep, list e as ferramentas de tarefas.
  - Codex: `danger-full-access` dentro do container.
  Sem web, subagentes, skills ou MCP. A paridade entre harnesses é aproximada: por exemplo, o OpenCode tem ferramenta de lista de tarefas, e o Claude Code, nesta configuração, não.
- **Skills:** nenhuma, como no piloto. A seleção continua em aberto na proposta.
- **Prazo de prontidão no enunciado:** usa o valor provisório do avaliador. Se o valor mudar, o prompt muda junto, e o hash registra a mudança.

## 6. Limitações

- **Credenciais:** lidas dos caminhos do computador de Rafael pelo mesmo código do piloto (`scripts/run-pilot.py`). Em outro computador, é preciso ajustá-los.
- **Codex:** o formato de consumo continua sem validação em tentativa real, como no piloto.
- **Entrega grande:** um `/workspace` com `node_modules` ou `.venv` é congelado inteiro, como manda o contrato. O tar pode ficar grande, e o `build.sh` do avaliador reinstala as dependências.
- **Isolamento:** o desenho é o mesmo do piloto. DNS, serviços do host e tentativas adversariais não foram certificados.
- **Rotas gratuitas:** as condições de dados e disponibilidade de Muse e MiMo continuam valendo ([piloto](../pilot/README.md)).
