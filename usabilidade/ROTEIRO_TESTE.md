# Roteiro do teste de usabilidade

**Objetivo:** medir a usabilidade do sistema (ISO/IEC 25010 → *usabilidade*)
com pessoas reais, combinando:

| O que medir | Subcaracterística ISO 25010 | Como |
|---|---|---|
| % de tarefas concluídas | Eficácia / operabilidade | log automático (`uso_log.csv`) |
| Tempo por tarefa | Eficiência | log automático (`uso_log.csv`) |
| Erros de validação | Proteção contra erros do usuário | log automático (`uso_log.csv`) |
| Satisfação percebida | Satisfação / aprendizagem | questionário SUS (BROOKE, 1996) |

## Participantes

- **8 a 10 pessoas.** Estudos de usabilidade mostram que ~5 usuários já revelam
  a maior parte dos problemas (NIELSEN; LANDAUER, 1993); com 8+ a média do SUS fica mais estável.
- Perfil ideal: quem lida com o estoque de TI ou seria usuário dele
  (equipe de TI, almoxarifado, administrativo). Anote o perfil de cada um.
- **Ética:** não colete nome completo, CPF ou dado de saúde. Use códigos
  P01, P02... Peça consentimento verbal e explique que o teste é do
  *sistema*, não da pessoa.

## Preparação (uma vez)

1. Apague `dados_estoque.json` e `uso_log.csv` (se existirem) da pasta do projeto.
2. Abra o programa (`python app.py`) e aceite os **dados de exemplo**. Feche.
3. Faça uma **cópia** de `dados_estoque.json` chamada `dados_inicio.json`.

## Para CADA participante

1. Copie `dados_inicio.json` por cima de `dados_estoque.json` (todos começam igual).
2. Apague `uso_log.csv`.
3. Abra o programa e leia para a pessoa: *"Vou te pedir 5 tarefas. Faça do
   jeito que achar melhor, sem pressa. Não posso te ajudar durante as tarefas."*
4. Entregue as tarefas (uma por vez, impressas ou ditadas):

   | # | Tarefa |
   |---|---|
   | T1 | Cadastre um novo item: **Headset USB**, categoria Periférico, 4 unidades, mínimo 2. |
   | T2 | A Recepção pediu **2 mouses USB**. Registre essa saída, responsável: seu primeiro nome. |
   | T3 | Descubra **quantos cabos HDMI** há no estoque e me fale o número. |
   | T4 | Chegaram **5 toners HP 85A** do fornecedor. Registre a entrada. |
   | T5 | Abra o relatório e me diga **qual item precisa ser comprado com mais urgência**. |

5. Anote na planilha de observação (abaixo) se a pessoa concluiu T3 e T5
   (essas duas não passam por formulário, então o log não registra o acerto).
6. Feche o programa e **copie `uso_log.csv` para `usabilidade/logs/P01.csv`**
   (P02.csv, P03.csv... para os próximos).
7. Peça para a pessoa responder o **questionário SUS** (`QUESTIONARIO_SUS.md`)
   e digite as notas em `respostas_sus.csv`.

## Planilha de observação (copie para o caderno)

| Participante | Perfil | T3 acertou? | T5 acertou? | Comentários / dificuldades observadas |
|---|---|---|---|---|
| P01 | | S / N | S / N | |
| P02 | | S / N | S / N | |

As dificuldades observadas são ouro para a seção **Resultados** e
para "melhorias futuras" na **Conclusão**.

## Depois de todos os participantes

```
python usabilidade/analisar_usabilidade.py
```

Gera em `usabilidade/resultados/`: a nota SUS de cada pessoa, a média,
gráficos e uma tabela de tempo/sucesso por tarefa, prontos para o relatório.
