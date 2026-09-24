# Imagem multi-linguagem candidata

Imagem única para as tentativas e para o avaliador, escolhida por Rafael em 24/09/2026 para viabilizar a stack livre do [contrato](../../docs/contrato-encurtador.md). Ainda não está congelada para a coleta oficial.

## Build e validação

Na raiz do repositório:

```sh
python3 scripts/build-pilot.py --dockerfile infra/runtime/Dockerfile --image llm-bench-runtime:20260924
python3 scripts/check-runtime-image.py
bash scripts/check-isolation-baseline.sh llm-bench-runtime:20260924
```

O build registra em `.pilot/images/llm-bench-runtime_20260924.json`, arquivo ignorado pelo Git, o ID da imagem, o hash do Dockerfile e os hashes dos binários dos harnesses.

## Conteúdo

| Componente | Versão | Origem |
|---|---|---|
| Base | Debian 12 (bookworm-slim) | Fixada por digest |
| Python | 3.11.2, com `pip` 23.0.1 e `venv`; SQLite 3.40.1 | Pacotes Debian |
| Node.js | 24.21.0 LTS, npm 11.19.0; inclui `node:sqlite` | nodejs.org, SHA-256 verificado |
| Go | 1.27.1, com `GOTOOLCHAIN=local` | go.dev, SHA-256 verificado |
| Java | Temurin JDK 25.0.4.1 LTS | Adoptium, SHA-256 verificado |
| Maven | 3.9.16 | Maven Central, SHA-512 verificado |
| Compilação nativa | `build-essential` (gcc) e `python3-dev` | Pacotes Debian |
| Harnesses | Claude Code, Codex e OpenCode, copiados do host | Hashes no manifesto do build |

As toolchains oficiais têm versão e checksum fixos no Dockerfile. Os pacotes Debian vêm do espelho no momento do build. O que fica congelado, portanto, é a imagem construída, identificada pelo ID. Reconstruir mais tarde pode produzir pacotes Debian diferentes.

Gradle não está incluído. Um projeto com Gradle Wrapper exigiria liberar `services.gradle.org` e os repositórios de plugins.

## Resultado da validação em 24/09/2026

Imagem `sha256:aa1c6322f54a7b9d01d2663992f2563251bccb26226e7eeba2f43ddc969839eb`, com 2,84 GB.

**Fase 1, sem rede.** Nas mesmas restrições do agente (raiz somente leitura, UID 1001, capabilities removidas, tmpfs), todas as verificações passaram:

- versões das quatro linguagens;
- criação de venv;
- SQLite em Python e em Node;
- `go run`;
- um servidor HTTP com biblioteca padrão respondendo 200 em cada linguagem.

**Fase 2, com proxy.** A lista de destinos liberados continha somente `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`, `proxy.golang.org`, `sum.golang.org` e `repo.maven.apache.org`.

- Passaram: `pip install`, `npm install`, `go get` e `mvn dependency:get`.
- Um acesso a `github.com` foi bloqueado.
- O proxy registrou somente os seis registros e a tentativa bloqueada.

O check básico de isolamento também passou sobre esta imagem.

## Requisitos que esta imagem impõe ao runner da coleta

Os pontos abaixo foram observados na validação. O runner do piloto sintético não os implementa. O [runner da coleta](../attempt/README.md) implementa os três primeiros e usa tmpfs de 2 GiB no home:

- **Montagens executáveis.** `/tmp`, `/home/agent` e `/workspace` precisam ser montados com `exec`. Com o padrão `noexec` do Docker, `go run` falhou com `permission denied`, e binários compilados no workspace e módulos nativos do npm também não executariam.
- **Proxy do Maven.** O Maven 3.9 ignora `HTTPS_PROXY` e `-Dhttps.proxyHost`. É preciso provisionar `~/.m2/settings.xml` com o proxy, como fez a validação.
- **Lista de rede.** Os registros de pacotes entram junto com os domínios do provedor de cada participante.
- **Tamanho dos tmpfs.** Caches do Go, npm e Maven e builds Java ocupam o home. A validação usou 1 GiB para o home, contra 512 MiB no piloto. Como a memória de tmpfs conta no limite do container, os limites finais precisam considerar os dois.
