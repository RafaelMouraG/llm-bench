# Mini benchmark exploratório de agentes de programação

Proposta de pesquisa para comparar configurações completas de agentes de IA — modelo, harness e skills — no desenvolvimento de uma API. Este projeto é complementar ao **lab02 obrigatório**, que permanece separado.

**Estado em 24/09/2026:** proposta em elaboração. A GQM orientará a definição do enunciado, dos requisitos, dos critérios de avaliação, do protocolo e dos testes. A coleta oficial ainda não começou.

## Documentação

- [Proposta de pesquisa](docs/proposta-pesquisa.md): contexto, participantes pretendidos, isolamento, avaliação, decisões em aberto e contribuições do material das aulas.
- [GQM e plano de medição](docs/gqm.md): objetivo, perguntas, métricas candidatas, regras de interpretação e ficha operacional de medição.
- [Verificação inicial do ambiente](docs/verificacao-ambiente.md): versões, estado de autenticação no host, identificadores encontrados e checagem básica de isolamento.
- [Contrato candidato do encurtador](docs/contrato-encurtador.md): enunciado, requisitos com verificação e decisões pendentes. Documento privado; somente a Parte A se destina aos participantes.
- [Piloto de infraestrutura](docs/piloto-infraestrutura.md): tentativas sintéticas nos containers, resultados por participante e pendências. O ambiente está em [infra/pilot](infra/pilot/README.md).
- [Imagem multi-linguagem](infra/runtime/README.md): ambiente candidato da coleta, com Python, Node, Go e Java, e o resultado da validação.

O encurtador de URL é a tarefa candidata, com stack livre e contrato HTTP a definir. Identificadores foram encontrados em catálogos e fontes oficiais; as configurações finais e o acesso aos modelos dentro dos containers ainda precisam de validação antes da coleta.

O repositório central deverá permanecer privado durante a coleta. Participantes receberão somente os materiais de sua própria tentativa. Esta documentação de coordenação não deve ser disponibilizada integralmente aos participantes.

## Próxima etapa

Concluir o piloto de infraestrutura: executar o Sol, que também valida a extração de tokens no formato do Codex. Gemini foi substituído por MiMo-V2.6-Flash Free. Em paralelo, refinar as subperguntas e definições operacionais da GQM e depois fechar o escopo e os critérios de avaliação.
