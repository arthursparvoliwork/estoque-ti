"""
estoque.py - Núcleo (regras de negócio) do Sistema de Estoque de TI.

Este módulo NÃO conhece a interface gráfica. Ele só sabe:
  - guardar itens e movimentações (registros);
  - buscar, ordenar e calcular;
  - salvar e carregar os dados em arquivo JSON.

Separar regra de negócio da interface permite testar tudo isso
sem abrir janela nenhuma (veja testes/test_estoque.py).

Conteúdos da ementa cobertos aqui:
  - registros ........................ dataclasses Item e Movimentacao
  - vetores (listas) e arranjos de registros ... Estoque.itens / Estoque.movimentacoes
  - pesquisa sequencial .............. buscar_por_nome()
  - pesquisa binária ................. buscar_por_codigo()
  - ordenação (métodos básicos) ...... ordenar_insercao()
  - matrizes ......................... matriz_saidas_por_dia()
  - cadeias de caracteres ............ normalizar(), gerar_codigo()
  - funções recursivas ............... soma_recursiva(), busca_binaria_recursiva()
  - acumuladores, contadores, flags .. resumo(), itens_abaixo_do_minimo()
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

# Constantes: valores fixos usados em vários lugares.
CATEGORIAS = ["Periférico", "Cabo", "Computador", "Rede", "Impressão", "Outro"]
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
FORMATO_DATA = "%Y-%m-%d %H:%M"


class ErroEstoque(Exception):
    """Erro de regra de negócio (ex.: saída maior que o saldo)."""


# ---------------------------------------------------------------------------
# REGISTROS
# ---------------------------------------------------------------------------
@dataclass
class Item:
    codigo: str          # ex.: "PER-001"
    nome: str            # ex.: "Mouse USB"
    categoria: str       # uma das CATEGORIAS
    quantidade: int      # saldo atual
    minimo: int          # abaixo disso gera alerta de reposição
    local: str = ""      # ex.: "Almoxarifado TI - Prateleira 2"


@dataclass
class Movimentacao:
    data: str            # texto no FORMATO_DATA
    codigo: str          # código do item movimentado
    tipo: str            # "ENTRADA" ou "SAIDA"
    quantidade: int
    setor: str = ""      # para onde foi / de onde veio (ex.: "Recepção")
    responsavel: str = ""


# ---------------------------------------------------------------------------
# FUNÇÕES DE TEXTO (cadeias de caracteres)
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Deixa o texto em minúsculas e sem acento, para a busca achar
    'teclado' quando o usuário digita 'TECLÁDO' ou 'Teclado'."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.strip().lower()


def gerar_codigo(categoria: str, numero: int) -> str:
    """'Periférico', 7 -> 'PER-007'."""
    prefixo = normalizar(categoria)[:3].upper()
    return f"{prefixo}-{numero:03d}"


# ---------------------------------------------------------------------------
# FUNÇÕES RECURSIVAS
# ---------------------------------------------------------------------------
def soma_recursiva(valores: list[int]) -> int:
    """Soma uma lista sem usar laço: soma(lista) = primeiro + soma(resto).
    Caso base: lista vazia soma 0."""
    if not valores:
        return 0
    return valores[0] + soma_recursiva(valores[1:])


def busca_binaria_recursiva(itens: list[Item], codigo: str,
                            inicio: int = 0, fim: int | None = None) -> int:
    """Versão recursiva da busca binária. Devolve o índice ou -1.
    A lista PRECISA estar ordenada por código."""
    if fim is None:
        fim = len(itens) - 1
    if inicio > fim:                      # caso base: não achou
        return -1
    meio = (inicio + fim) // 2
    if itens[meio].codigo == codigo:      # caso base: achou
        return meio
    if codigo < itens[meio].codigo:       # está na metade esquerda
        return busca_binaria_recursiva(itens, codigo, inicio, meio - 1)
    return busca_binaria_recursiva(itens, codigo, meio + 1, fim)


# ---------------------------------------------------------------------------
# ORDENAÇÃO (método básico implementado à mão)
# ---------------------------------------------------------------------------
def ordenar_insercao(itens: list[Item], chave: str = "codigo",
                     decrescente: bool = False) -> list[Item]:
    """Insertion sort: pega cada elemento e 'insere' na posição certa
    da parte já ordenada à esquerda. Devolve uma NOVA lista.

    Otimização (versão 2): a chave de cada item (ex.: nome sem acento)
    é calculada UMA vez antes do laço, e não a cada comparação.
    Na versão 1, normalizar() rodava dentro do while: com 1.000 itens
    isso eram ~250 mil chamadas e a ordenação levava ~420 ms."""
    # pares (chave já calculada, item)
    pares = [(_valor_ordenacao(item, chave), item) for item in itens]
    for i in range(1, len(pares)):
        atual = pares[i]
        j = i - 1
        # empurra para a direita quem deve vir depois do atual
        while j >= 0 and _vem_depois(pares[j][0], atual[0], decrescente):
            pares[j + 1] = pares[j]
            j -= 1
        pares[j + 1] = atual
    return [item for _, item in pares]


def _valor_ordenacao(item: Item, chave: str):
    valor = getattr(item, chave)
    return normalizar(valor) if isinstance(valor, str) else valor


def _vem_depois(a, b, decrescente: bool) -> bool:
    return a < b if decrescente else a > b


# ---------------------------------------------------------------------------
# O ESTOQUE
# ---------------------------------------------------------------------------
class Estoque:
    def __init__(self, arquivo: str | Path | None = None):
        self.itens: list[Item] = []                 # arranjo de registros
        self.movimentacoes: list[Movimentacao] = []  # histórico
        self.arquivo = Path(arquivo) if arquivo else None

    # ----- cadastro -------------------------------------------------------
    def proximo_codigo(self, categoria: str) -> str:
        prefixo = gerar_codigo(categoria, 0)[:3]
        contador = 0                                 # contador
        for item in self.itens:
            if item.codigo.startswith(prefixo):
                contador += 1
        codigo = gerar_codigo(categoria, contador + 1)
        while self.buscar_por_codigo(codigo) is not None:  # evita repetir
            contador += 1
            codigo = gerar_codigo(categoria, contador + 1)
        return codigo

    def cadastrar(self, nome: str, categoria: str, quantidade: int,
                  minimo: int, local: str = "") -> Item:
        nome = nome.strip()
        if not nome:
            raise ErroEstoque("Informe o nome do item.")
        if categoria not in CATEGORIAS:
            raise ErroEstoque(f"Categoria inválida: {categoria}")
        if quantidade < 0 or minimo < 0:
            raise ErroEstoque("Quantidade e mínimo não podem ser negativos.")
        for item in self.itens:                      # pesquisa sequencial
            if normalizar(item.nome) == normalizar(nome):
                raise ErroEstoque(f"Já existe um item chamado '{item.nome}' "
                                  f"({item.codigo}).")
        item = Item(self.proximo_codigo(categoria), nome, categoria,
                    quantidade, minimo, local.strip())
        # Mantém self.itens SEMPRE ordenada por código (invariante).
        # Assim a busca binária funciona sem precisar reordenar a cada busca.
        self.itens.insert(self._posicao_insercao(item.codigo), item)
        if quantidade > 0:
            self._registrar(item.codigo, "ENTRADA", quantidade,
                            "Cadastro inicial", "")
        return item

    def remover(self, codigo: str) -> None:
        item = self._exigir(codigo)
        self.itens.remove(item)

    # ----- movimentação ---------------------------------------------------
    def entrada(self, codigo: str, quantidade: int, setor: str = "",
                responsavel: str = "") -> Item:
        if quantidade <= 0:
            raise ErroEstoque("A quantidade precisa ser maior que zero.")
        item = self._exigir(codigo)
        item.quantidade += quantidade                # acumulador
        self._registrar(codigo, "ENTRADA", quantidade, setor, responsavel)
        return item

    def saida(self, codigo: str, quantidade: int, setor: str = "",
              responsavel: str = "") -> Item:
        if quantidade <= 0:
            raise ErroEstoque("A quantidade precisa ser maior que zero.")
        item = self._exigir(codigo)
        if quantidade > item.quantidade:
            raise ErroEstoque(f"Saldo insuficiente: há {item.quantidade} "
                              f"unidade(s) de '{item.nome}'.")
        item.quantidade -= quantidade
        self._registrar(codigo, "SAIDA", quantidade, setor, responsavel)
        return item

    def _registrar(self, codigo, tipo, quantidade, setor, responsavel):
        self.movimentacoes.append(Movimentacao(
            datetime.now().strftime(FORMATO_DATA), codigo, tipo,
            quantidade, setor, responsavel))

    # ----- buscas ---------------------------------------------------------
    def buscar_por_nome(self, termo: str) -> list[Item]:
        """PESQUISA SEQUENCIAL: olha item por item, do primeiro ao último.
        Serve para busca por pedaço do nome, que não dá para fazer com
        busca binária. Custo: O(n)."""
        termo = normalizar(termo)
        encontrados = []
        for item in self.itens:
            if termo in normalizar(item.nome) or termo in normalizar(item.codigo):
                encontrados.append(item)
        return encontrados

    def buscar_por_codigo(self, codigo: str) -> Item | None:
        """PESQUISA BINÁRIA: com a lista ordenada por código, olha o meio
        e descarta metade a cada passo. Custo: O(log n)."""
        ordenados = self.itens          # já está ordenada (invariante)
        inicio, fim = 0, len(ordenados) - 1
        while inicio <= fim:
            meio = (inicio + fim) // 2
            atual = ordenados[meio].codigo
            if atual == codigo:
                return ordenados[meio]
            if codigo < atual:
                fim = meio - 1
            else:
                inicio = meio + 1
        return None

    def itens_ordenados_por_codigo(self) -> list[Item]:
        return list(self.itens)         # cópia da lista já ordenada

    def _posicao_insercao(self, codigo: str) -> int:
        """Busca binária que devolve ONDE o código deveria entrar."""
        inicio, fim = 0, len(self.itens)
        while inicio < fim:
            meio = (inicio + fim) // 2
            if self.itens[meio].codigo < codigo:
                inicio = meio + 1
            else:
                fim = meio
        return inicio

    def _exigir(self, codigo: str) -> Item:
        item = self.buscar_por_codigo(codigo)
        if item is None:
            raise ErroEstoque(f"Item {codigo} não encontrado.")
        return item

    # ----- relatórios -----------------------------------------------------
    def itens_abaixo_do_minimo(self) -> list[Item]:
        alerta = []
        for item in self.itens:
            precisa_repor = item.quantidade <= item.minimo   # flag
            if precisa_repor:
                alerta.append(item)
        return ordenar_insercao(alerta, "quantidade")

    def resumo(self) -> dict:
        total_unidades = 0          # acumulador
        em_alerta = 0               # contador
        zerados = 0                 # contador
        maior = menor = None        # maior e menor saldo
        for item in self.itens:
            total_unidades += item.quantidade
            if item.quantidade <= item.minimo:
                em_alerta += 1
            if item.quantidade == 0:
                zerados += 1
            if maior is None or item.quantidade > maior.quantidade:
                maior = item
            if menor is None or item.quantidade < menor.quantidade:
                menor = item
        total_saidas = soma_recursiva(
            [m.quantidade for m in self.movimentacoes if m.tipo == "SAIDA"])
        return {
            "itens_cadastrados": len(self.itens),
            "total_unidades": total_unidades,
            "itens_em_alerta": em_alerta,
            "itens_zerados": zerados,
            "maior_saldo": maior,
            "menor_saldo": menor,
            "total_saidas": total_saidas,
        }

    def matriz_saidas_por_dia(self) -> tuple[list[str], list[list[int]]]:
        """MATRIZ: linha = item, coluna = dia da semana, célula = unidades
        que saíram. Mostra em que dia cada item mais sai."""
        codigos = [item.codigo for item in self.itens_ordenados_por_codigo()]
        matriz = [[0] * len(DIAS_SEMANA) for _ in codigos]   # n x 7 zeros
        for mov in self.movimentacoes:
            if mov.tipo != "SAIDA" or mov.codigo not in codigos:
                continue
            linha = codigos.index(mov.codigo)
            coluna = datetime.strptime(mov.data, FORMATO_DATA).weekday()
            matriz[linha][coluna] += mov.quantidade
        return codigos, matriz

    def saidas_por_setor(self) -> list[tuple[str, int]]:
        totais: dict[str, int] = {}
        for mov in self.movimentacoes:
            if mov.tipo == "SAIDA":
                setor = mov.setor or "(sem setor)"
                totais[setor] = totais.get(setor, 0) + mov.quantidade
        return sorted(totais.items(), key=lambda par: par[1], reverse=True)

    # ----- persistência (arquivo JSON) -----------------------------------
    def salvar(self, arquivo: str | Path | None = None) -> None:
        destino = Path(arquivo) if arquivo else self.arquivo
        if destino is None:
            raise ErroEstoque("Nenhum arquivo definido para salvar.")
        dados = {
            "itens": [asdict(i) for i in self.itens],
            "movimentacoes": [asdict(m) for m in self.movimentacoes],
        }
        # grava num arquivo temporário e depois troca: se o programa cair
        # no meio da gravação, o arquivo antigo não fica corrompido.
        temporario = destino.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        temporario.replace(destino)

    @classmethod
    def carregar(cls, arquivo: str | Path) -> "Estoque":
        estoque = cls(arquivo)
        caminho = Path(arquivo)
        if not caminho.exists():
            return estoque                     # primeira execução: vazio
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        # ordena ao carregar para garantir a invariante mesmo se alguém
        # editou o JSON na mão
        estoque.itens = ordenar_insercao(
            [Item(**d) for d in dados.get("itens", [])], "codigo")
        estoque.movimentacoes = [Movimentacao(**d)
                                 for d in dados.get("movimentacoes", [])]
        return estoque
