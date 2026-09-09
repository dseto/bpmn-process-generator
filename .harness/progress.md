# Claude Progress

Contrato: `bpmn-skill-upgrade`

_Demanda ENCERRADA por `harness finish`._

## Features

| id | desc | status |
| --- | --- | --- |
| T-01 | Descrever um processo num spec JSON simples gera um arquivo BPMN com ids legíveis e referências de fluxo sempre coerentes | done |
| T-02 | Eventos tipados, prazos anexados a tarefas, condições de decisão e raias completas saem corretos do spec | done |
| T-03 | Um único comando entrega o diagrama pronto: gera, posiciona, valida e deixa o editor na pasta do projeto | done |
| T-04 | Um diagrama existente pode ser reconvertido em spec e regerado sem perder informação do processo | done |
| T-05 | Cada checagem do validador vira uma regra identificável com gravidade própria (erro, aviso, informação) | done |
| T-06 | O validador acusa erros estruturais que hoje passam despercebidos e reprovam o diagrama | done |
| T-07 | O validador aponta problemas de qualidade de modelagem como aviso, sem reprovar o diagrama | done |
| T-08 | O resultado da validação pode ser lido em JSON pelo assistente e endurecido para tratar avisos como falha | done |
| T-09 | Problemas mecânicos do arquivo são corrigidos automaticamente, com prévia do que muda e sem inventar conteúdo do processo | done |
| T-10 | Os seis diagramas de exemplo da skill passam no modo mais rigoroso, virando padrão de qualidade | done |
| T-11 | O manual da skill instrui a perguntar o que falta e a gerar pelo spec, não escrevendo XML à mão | done |
| T-12 | No editor é possível alterar nome, documentação, tipo do elemento e a condição de cada fluxo por um painel | done |
| T-13 | O editor mostra os problemas do diagrama numa lista clicável que leva ao elemento com defeito | done |
| T-14 | O editor entregue num projeto se atualiza sozinho quando a skill evolui, sem apagar ajustes locais | done |
| T-15 | O editor permite alinhar e distribuir elementos selecionados e gerar um PDF do diagrama | done |
| T-16 | O editor abre e renderiza o diagrama em máquina sem internet | done |

## Última atualização

_(vazio — demanda encerrada; o próximo `compile-session` regenera este arquivo a partir do contrato novo. A prova do que foi entregue está em `.harness/evidence/`.)_
