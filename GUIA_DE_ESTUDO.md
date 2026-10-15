# Guia de estudo: entendendo o projeto como um dev sênior

> Leia com o código aberto do lado. A ideia não é decorar. É entender **por que**
> cada decisão foi tomada, porque é isso que o professor vai perguntar e é isso
> que diferencia júnior de pleno numa entrevista.

---

## 0. O mapa do projeto

```
estoque-ti/
├── estoque.py          ← NÚCLEO: regras de negócio (não sabe que existe tela)
├── app.py              ← INTERFACE: Tkinter (só mostra e lê dados)
├── testes/
│   └── test_estoque.py ← 24 testes automáticos do núcleo
├── medicoes/
│   ├── benchmark.py    ← mede DESEMPENHO e gera gráficos
│   └── resultados/     ← CSV + PNG que vão para o relatório
├── usabilidade/
│   ├── ROTEIRO_TESTE.md, QUESTIONARIO_SUS.md
│   ├── respostas_sus.csv, logs/   ← você preenche com dados reais
│   └── analisar_usabilidade.py    ← calcula SUS e gera gráficos
├── dados_estoque.json  ← criado ao usar (é o "banco de dados")
└── uso_log.csv         ← criado ao usar (tempo de cada tarefa)
```

### A decisão mais importante: separar núcleo e interface

**Lição de sênior #1:** regra de negócio não mora na tela.

Imagine que a regra "não pode sair mais do que tem" estivesse dentro do botão
da janela. Para testar, você teria que abrir a janela, clicar e digitar,
sempre na mão. Com `estoque.py` separado:

- os **testes** chamam `estoque.saida(...)` direto, sem janela, e rodam em 0,01 s;
- o **benchmark** mede a busca sem precisar de tela;
- se amanhã você quiser uma versão **web** (FastAPI, que você já estuda), o
  `estoque.py` é reaproveitado inteiro. Só troca o `app.py`.

Isso tem nome: **separação de responsabilidades** (*separation of concerns*).
É a ideia por trás da Clean Architecture do seu job tracker.

---

## 1. `estoque.py` — o núcleo

### 1.1 Registros com `@dataclass`

```python
@dataclass
class Item:
    codigo: str
    nome: str
    categoria: str
    quantidade: int
    minimo: int
    local: str = ""
```

- `@dataclass` é um **decorador**: ele gera sozinho o `__init__`, o `__repr__`
  (como o objeto aparece no print) e o `__eq__` (comparar dois itens com `==`).
- Isso é o "**registro**" da ementa: um tipo que agrupa campos de dados
  diferentes, como o `struct` de C ou o `record` de Pascal.
- `local: str = ""` tem valor padrão, então é opcional ao criar o item.
- **Por que não usar dicionário?** `{"nome": "Mouse"}` aceita qualquer chave.
  Se você digitar `item["nmoe"]`, só descobre o erro rodando. Com dataclass,
  o editor (VS Code) avisa `item.nmoe` na hora. Tipos explícitos = menos bug.

`ErroEstoque(Exception)` é uma **exceção própria**. A regra de negócio "fala"
com quem a chamou levantando esse erro, e a interface decide como mostrar.
O núcleo nunca chama `messagebox`, porque não sabe que existe tela.

### 1.2 `normalizar()` — cadeias de caracteres

```python
sem_acento = unicodedata.normalize("NFKD", texto)
sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
return sem_acento.strip().lower()
```

- Linha 1: "NFKD" **decompõe** letras acentuadas. `"á"` vira `"a"` + `"´"`
  (dois caracteres).
- Linha 2: percorre cada caractere e **descarta os acentos soltos**
  (`combining`). Esse `"".join(... for ...)` é uma *generator expression*,
  um laço compacto que monta uma string nova.
- Linha 3: tira os espaços das pontas e deixa tudo minúsculo.
- **Para quê?** O usuário digita "TECLÁDO", "teclado" ou " Teclado" e a busca acha
  do mesmo jeito. Isso é **usabilidade** implementada no código.

### 1.3 A invariante: lista sempre ordenada por código

**Lição de sênior #2: invariante** é uma regra que precisa ser verdadeira
**o tempo todo**. Aqui: *`self.itens` está sempre ordenada por código*.

Para garanti-la, cada item novo entra direto na posição certa:

```python
self.itens.insert(self._posicao_insercao(item.codigo), item)
```

`_posicao_insercao` é uma busca binária que, em vez de responder "achei / não achei",
responde "**onde** esse código deveria estar". Ao carregar o JSON, o código também
reordena (`ordenar_insercao`) caso alguém tenha editado o arquivo na mão.

**A história real deste projeto (conte isso no relatório):** na primeira versão,
`buscar_por_codigo` fazia `sorted(self.itens)` **a cada busca**. Ordenar custa
O(n log n), e a busca binária custa O(log n). Ou seja, a ordenação comia toda a
vantagem da busca binária. Eu achei isso revisando o código. Com a invariante,
a lista é ordenada uma vez e cada busca custa só O(log n).

### 1.4 Pesquisa binária (iterativa)

```python
inicio, fim = 0, len(ordenados) - 1
while inicio <= fim:
    meio = (inicio + fim) // 2       # // = divisão inteira
    atual = ordenados[meio].codigo
    if atual == codigo:
        return ordenados[meio]       # achou
    if codigo < atual:
        fim = meio - 1               # está na metade ESQUERDA
    else:
        inicio = meio + 1            # está na metade DIREITA
return None                          # intervalo vazio: não existe
```

Pense em procurar um nome na lista de chamada em ordem alfabética: você abre no meio,
vê se o nome vem antes ou depois e joga metade fora. A cada volta o problema
**cai pela metade**. Com 20.000 itens, são no máximo ~15 comparações (2^15 ≈ 32 mil).

Strings em Python são comparadas em ordem alfabética: `"CAB-001" < "PER-001"` é `True`.
Por isso funciona com o código como texto.

**Pergunta clássica de professor:** *"por que a busca por nome não é binária?"*
Porque a busca por nome procura um **pedaço** do texto ("cabo" acha
"Cabo de rede" e "Cabo HDMI"), e a lista está ordenada por código, não por nome.
Busca parcial exige olhar um por um, ou seja, pesquisa **sequencial**, O(n).
O gráfico `grafico_buscas.png` mostra exatamente essa diferença.

### 1.5 Pesquisa binária recursiva

```python
def busca_binaria_recursiva(itens, codigo, inicio=0, fim=None):
    if fim is None:
        fim = len(itens) - 1
    if inicio > fim:          # CASO BASE 1: não achou
        return -1
    meio = (inicio + fim) // 2
    if itens[meio].codigo == codigo:   # CASO BASE 2: achou
        return meio
    if codigo < itens[meio].codigo:
        return busca_binaria_recursiva(itens, codigo, inicio, meio - 1)
    return busca_binaria_recursiva(itens, codigo, meio + 1, fim)
```

Recursão = função que **chama a si mesma** com um problema menor.
Toda recursão precisa de:

1. **Caso base**: quando parar. Sem ele, dá `RecursionError` (estouro de pilha).
2. **Passo recursivo**: a chamada com um problema *menor*. Aqui, metade do intervalo.

`fim=None` como padrão é um truque comum. Não dá para escrever `fim=len(itens)-1`
na assinatura, porque o valor padrão é calculado **uma vez só**, quando a função é
definida, e não a cada chamada.

O teste `test_busca_binaria_recursiva_concorda_com_iterativa` prova que as duas
versões dão o mesmo resultado. **Lição de sênior #3:** quando você tem duas
implementações da mesma coisa, teste uma contra a outra.

### 1.6 `soma_recursiva()`

```python
if not valores:          # lista vazia -> caso base
    return 0
return valores[0] + soma_recursiva(valores[1:])
```

soma([3, 5, 2]) = 3 + soma([5, 2]) = 3 + (5 + soma([2])) = 3 + 5 + 2 + soma([]) = 10.

Seja honesto se o professor perguntar: **em produção ninguém faria isso**.
`sum()` é mais rápido, e `valores[1:]` copia a lista a cada chamada (O(n²)
de memória). Ela existe para cobrir o tópico "funções recursivas" da ementa com um
exemplo didático. Saber dizer *"isso é didático, em produção eu usaria X porque Y"*
mostra maturidade.

### 1.7 Insertion sort (e a otimização)

```python
pares = [(_valor_ordenacao(item, chave), item) for item in itens]
for i in range(1, len(pares)):
    atual = pares[i]
    j = i - 1
    while j >= 0 and _vem_depois(pares[j][0], atual[0], decrescente):
        pares[j + 1] = pares[j]      # empurra para a direita
        j -= 1
    pares[j + 1] = atual             # encaixa no buraco
return [item for _, item in pares]
```

É como organizar cartas de baralho na mão: você pega a próxima carta e vai
deslizando para a esquerda até achar o lugar dela.

- **Pior caso:** O(n²). Lista invertida, cada carta anda até o começo.
- **Melhor caso:** O(n). Lista já ordenada, o `while` nem roda. Por isso, ao
  carregar o JSON (que já foi salvo ordenado), ele é rápido.

**A otimização que o benchmark revelou (é o destaque do seu relatório):**

Na versão 1, `normalizar()` (tirar os acentos, que é cara) era chamada **dentro do
`while`**, a cada comparação. Com 1.000 itens, isso dava ~250 mil chamadas.
O benchmark mediu **421 ms**, acima da meta de 100 ms. Como a tabela da tela
reordena a cada tecla digitada na busca, o programa travaria.

A versão 2 calcula a chave **uma vez por item, antes do laço** (a lista `pares`).
O algoritmo é o mesmo, mas caiu para **~38 ms: 11x mais rápido**
(veja `grafico_otimizacao.png`).

**Lição de sênior #4:** *meça antes de otimizar*. Sem o benchmark, ninguém
teria notado o problema, porque com os 12 itens de exemplo leva 0,5 ms.

**Lição #5:** a otimização não mudou a complexidade (continua O(n²)). Ela mudou a
**constante**. Com 5.000 itens ainda leva ~1 s. Em produção, você usaria `sorted()`
(Timsort, O(n log n): 1,5 ms com 5.000 itens). Isso vai na **conclusão**, como
limitação e trabalho futuro.

**`list(itens)` e "não alterar a original":** a função devolve uma lista **nova**.
Se ela ordenasse `self.itens` no lugar, a ordenação da tela por nome quebraria a
invariante de "ordenada por código" e a busca binária passaria a errar.
O teste `test_ordenar_insercao_nao_altera_original` protege isso.

### 1.8 Acumuladores, contadores, flags — `resumo()`

```python
total_unidades = 0      # ACUMULADOR: soma valores
em_alerta = 0           # CONTADOR: soma 1 a cada ocorrência
maior = menor = None    # maior e menor valor encontrados
for item in self.itens:
    total_unidades += item.quantidade
    if item.quantidade <= item.minimo:
        em_alerta += 1
    if maior is None or item.quantidade > maior.quantidade:
        maior = item
```

É o padrão "maior e menor valor" da ementa. Começar com `None` e checar
`is None` evita o bug clássico de inicializar com `0`: se todos os saldos fossem 0,
o "maior" nunca seria atualizado.

Em `itens_abaixo_do_minimo()`, `precisa_repor = ...` é uma **flag** (sinalizador
booleano), com um nome que explica a intenção.

### 1.9 Matriz — `matriz_saidas_por_dia()`

```python
matriz = [[0] * len(DIAS_SEMANA) for _ in codigos]   # n linhas x 7 colunas
...
linha = codigos.index(mov.codigo)
coluna = datetime.strptime(mov.data, FORMATO_DATA).weekday()  # 0=Seg ... 6=Dom
matriz[linha][coluna] += mov.quantidade
```

⚠️ **Pegadinha famosa:** por que não `[[0] * 7] * n`? Porque isso cria **n
referências para a MESMA linha**. Mudar `matriz[0][0]` mudaria todas as linhas.
A list comprehension cria uma lista nova para cada linha. Isso cai em prova e em
entrevista.

O resultado aparece na aba "Saídas por dia da semana" do relatório. Útil de
verdade: mostra, por exemplo, que mouse sai mais na segunda-feira.

### 1.10 Salvar de forma segura

```python
temporario = destino.with_suffix(".tmp")
temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), ...)
temporario.replace(destino)
```

**Lição de sênior #6: escrita atômica.** Se a luz acabar **no meio** de
`write_text` direto no arquivo final, ele fica pela metade e você perde o estoque
inteiro. Gravando num `.tmp` e depois trocando (`replace` é uma operação atômica
no sistema operacional), o arquivo antigo continua intacto até o novo estar
100% pronto. Num hospital, isso importa.

- `asdict(item)` converte a dataclass em dicionário para virar JSON.
- `ensure_ascii=False` grava "Periférico" legível, não `"Periférico"`.
- `Item(**d)` faz o caminho de volta: o `**` "desempacota" o dicionário em
  argumentos nomeados (`Item(codigo=..., nome=..., ...)`).
- `@classmethod carregar(cls, ...)` é um **construtor alternativo**. Você chama
  `Estoque.carregar("x.json")` em vez de `Estoque()` e depois carregar.

---

## 2. `app.py` — a interface

### 2.1 Estrutura

- `App` monta a janela principal (`Treeview` = tabela, botões, busca).
- `Formulario` é uma **classe base** com o que todo formulário tem: campos,
  Confirmar/Cancelar, Enter/Esc, exibição de erro e medição de tempo.
- `FormCadastro` e `FormMovimento` **herdam** de `Formulario` e só implementam
  `executar()`. É herança usada do jeito certo, para não repetir código
  (princípio **DRY**: *Don't Repeat Yourself*).

### 2.2 O fluxo de um clique (siga com o dedo no código)

1. Usuário clica "↑ Saída" → `App.movimentar("SAIDA")` → cria `FormMovimento`.
2. Usuário preenche e aperta Enter → `Formulario.confirmar()`.
3. `confirmar()` chama `self.executar()` dentro de um `try`.
4. `executar()` chama `self.app.estoque.saida(...)`, que é **o núcleo**.
5. Se o núcleo levantar `ErroEstoque` (ex.: saldo insuficiente), o `except`
   mostra a mensagem em vermelho, soma 1 em `self.erros` e **mantém o formulário aberto**,
   para o usuário corrigir sem perder o que digitou.
6. Se der certo: `app.depois_de_alterar()` → **salva o JSON** → atualiza a tabela
   → mostra "✔ Saída de 3 x Mouse USB" no rodapé.
7. `fechar()` grava no `uso_log.csv` o tempo e os erros, que são **dados de usabilidade**.

### 2.3 Detalhes que valem explicar

- **`self.busca.trace_add("write", ...)`**: um `StringVar` "observado". Cada
  tecla digitada dispara `atualizar_tabela()`. É busca em tempo real, sem botão.
- **`lambda c=col: self.ordenar_por(c)`**: ⚠️ outra pegadinha. Sem o `c=col`,
  todas as lambdas criadas no `for` enxergariam a **última** `col` (a variável é
  lida quando o clique acontece, não quando a lambda é criada). O `c=col`
  "congela" o valor de cada volta. Isso se chama *late binding* de closures.
- **`grab_set()`** deixa o formulário **modal**: a janela de trás não responde
  até fechar.
- **Tags no Treeview** (`"alerta"`, `"zerado"`) pintam a linha de vermelho.
  É feedback visual imediato, um ponto de usabilidade.
- **Atalhos** (Ctrl+N/E/S/R/F) e a dica nos próprios botões: aceleradores
  para quem usa todo dia. É uma das heurísticas de Nielsen (*flexibilidade e
  eficiência de uso*).
- **Duplo clique na linha** abre a saída já com aquele item escolhido.
  É a ação mais comum no dia a dia, então tem o caminho mais curto.

### 2.4 Heurísticas de Nielsen aplicadas (use na discussão do relatório)

| Heurística | Onde aparece no sistema |
|---|---|
| Visibilidade do status | rodapé "✔ Saída de 3 x Mouse...", contadores, cores |
| Prevenção de erros | bloqueia saída maior que o saldo, nome duplicado e número negativo |
| Ajudar a reconhecer e corrigir erros | mensagem diz o saldo real: "há 3 unidade(s)" |
| Reconhecer em vez de lembrar | lista de itens com saldo no formulário; setores prontos |
| Flexibilidade e eficiência | atalhos de teclado, duplo clique, busca em tempo real |
| Controle e liberdade do usuário | Cancelar/Esc em todo formulário; confirmação ao excluir |

---

## 3. Testes (`testes/test_estoque.py`)

```
python -m unittest discover -s testes -v
```

Cada teste segue o padrão **AAA**:

- **Arrange**: monta o cenário (`estoque_exemplo()`);
- **Act**: faz UMA ação (`e.saida("PER-001", 4)`);
- **Assert**: confere (`assertEqual(..., 6)`).

`assertRaises(ErroEstoque)` testa o **caminho triste**: garante que o erro
acontece quando deve. Júnior testa só o caminho feliz. Sênior testa os
dois, porque o bug geralmente mora na borda: quantidade 0, negativa, maior que o saldo.

**Lição de sênior #7:** foram os testes que me deixaram otimizar o insertion
sort com segurança. Mudei o algoritmo, rodei os 24 testes, todos passaram, e eu
**sei** que não quebrei nada. Teste não é burocracia. É o que te dá coragem para mudar código.

---

## 4. Medições

### 4.1 `medicoes/benchmark.py` (desempenho)

- `time.perf_counter()`: o relógio de maior precisão do Python, feito para medir intervalos.
- Repete cada medição várias vezes e usa a **mediana**: se o Windows resolver
  atualizar algo no meio de uma rodada, um valor fica absurdo, e a mediana ignora isso
  (a média não).
- `random.seed(42)`: o "aleatório" passa a ser o mesmo toda vez, então o experimento é
  **reproduzível**. Princípio científico básico, cite na metodologia.
- **Pior caso** na busca sequencial: procura algo que não existe, então
  percorre a lista inteira.
- O insertion sort só roda até 5.000 itens, porque com 20.000 levaria minutos.
  Isso por si só já é um resultado: O(n²) não escala.

### 4.2 `usabilidade/analisar_usabilidade.py` (usabilidade)

- `nota_sus()` implementa a fórmula de Brooke: ímpares `resposta − 1`,
  pares `5 − resposta`, soma × 2,5.
- A validação `if any(r not in (1,...,5))` impede que um erro de digitação
  (um "55") vire uma nota absurda sem você perceber.

---

## 5. Perguntas que o professor pode fazer (treine as respostas)

1. **Por que busca binária no código e sequencial no nome?** → seção 1.4.
2. **Qual a complexidade do insertion sort? Por que não usou sorted()?** →
   O(n²). Usei para cumprir a ementa; o benchmark mostra que `sorted()` é ~700x
   mais rápido com 5.000 itens. Em produção usaria `sorted()`.
3. **O que acontece se a luz acabar na hora de salvar?** → escrita atômica (1.10).
4. **Como você garantiu que o sistema funciona?** → 24 testes automatizados +
   teste com usuários reais.
5. **Qual a diferença entre desempenho e usabilidade na ISO 25010?** →
   desempenho é sobre o *sistema* (tempo, recursos). Usabilidade é sobre a
   *interação com pessoas* (aprender, operar, errar menos, satisfação).
6. **Até quantos itens o sistema atende a meta de 100 ms?** → olhe no seu
   `desempenho.csv`. Na minha máquina: ordenação por nome até ~1.500 itens,
   salvar até ~15.000. O estoque real do hospital tem dezenas a centenas de itens.

---

## 6. Rodando no seu Windows

```bash
# 1. Python 3.10+ instalado (marque "Add to PATH"). O Tkinter já vem junto.
python --version

# 2. Na pasta do projeto:
python app.py                                  # abre o sistema
python -m unittest discover -s testes -v       # roda os testes

# 3. Para os gráficos:
pip install matplotlib
python medicoes/benchmark.py                   # ~1 min; refaça no SEU PC
python usabilidade/analisar_usabilidade.py     # depois do teste com pessoas
```

> Por que refazer o benchmark no seu PC? Os números do relatório precisam vir
> da máquina descrita no relatório (`ambiente.txt`). Os que estão na pasta
> foram medidos no ambiente em que eu desenvolvi, e servem só como referência.
