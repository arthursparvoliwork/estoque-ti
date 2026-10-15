"""
benchmark.py - Mede o DESEMPENHO do sistema (ISO/IEC 25010:
"eficiência de desempenho > comportamento em relação ao tempo").

O que é medido, para estoques de vários tamanhos (n itens):
  1. busca por código  (pesquisa BINÁRIA)    -> esperado O(log n)
  2. busca por nome    (pesquisa SEQUENCIAL) -> esperado O(n)
  3. ordenação por nome: insertion sort (feito à mão, O(n²))
     comparado com sorted() do Python (Timsort, O(n log n))
  4. salvar + carregar o arquivo JSON

Meta usada no relatório: toda ação do usuário deve responder em menos
de 100 ms (0,1 s), limite em que a resposta parece "instantânea"
(NIELSEN, 1993).

Rodar (na pasta do projeto):
    pip install matplotlib
    python medicoes/benchmark.py

Saídas em medicoes/resultados/: desempenho.csv, ambiente.txt e gráficos .png
IMPORTANTE: rode no SEU computador. Os números do relatório devem vir da
máquina descrita em ambiente.txt.
"""
import csv
import platform
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA_PROJETO))

from estoque import (CATEGORIAS, Estoque, Item, gerar_codigo,  # noqa: E402
                     ordenar_insercao, _valor_ordenacao, _vem_depois)


def ordenar_insercao_v1(itens, chave="codigo", decrescente=False):
    """Cópia da VERSÃO 1 (antes da otimização), mantida aqui só para o
    gráfico 'antes x depois' ser medido na mesma máquina e execução.
    Problema: _valor_ordenacao (que chama normalizar) roda a cada comparação."""
    resultado = list(itens)
    for i in range(1, len(resultado)):
        atual = resultado[i]
        valor_atual = _valor_ordenacao(atual, chave)
        j = i - 1
        while j >= 0 and _vem_depois(_valor_ordenacao(resultado[j], chave),
                                     valor_atual, decrescente):
            resultado[j + 1] = resultado[j]
            j -= 1
        resultado[j + 1] = atual
    return resultado

SAIDA = Path(__file__).resolve().parent / "resultados"
TAMANHOS = [100, 500, 1_000, 5_000, 10_000, 20_000]
LIMITE_INSERCAO = 5_000          # acima disso o insertion sort demora demais
META_MS = 100
random.seed(42)                  # mesma "sorte" sempre: resultado reproduzível

PALAVRAS = ["Mouse", "Teclado", "Cabo", "Monitor", "Toner", "Switch",
            "Leitor", "Headset", "Webcam", "Nobreak", "Hub", "Adaptador"]


def gerar_estoque(n: int) -> Estoque:
    """Cria n itens já ordenados por código (respeitando a invariante),
    sem passar por cadastrar() para a geração ficar rápida."""
    e = Estoque()
    por_categoria = {c: 0 for c in CATEGORIAS}
    itens = []
    for i in range(n):
        cat = random.choice(CATEGORIAS)
        por_categoria[cat] += 1
        nome = f"{random.choice(PALAVRAS)} modelo {i}"
        qtd = random.randint(0, 50)
        itens.append(Item(gerar_codigo(cat, por_categoria[cat]), nome, cat,
                          qtd, random.randint(1, 10), "Almoxarifado"))
    e.itens = sorted(itens, key=lambda it: it.codigo)
    return e


def medir_ms(funcao, repeticoes: int) -> float:
    """Executa a função várias vezes e devolve a MEDIANA em milissegundos.
    Mediana em vez de média: um soluço do sistema operacional não distorce."""
    tempos = []
    for _ in range(repeticoes):
        inicio = time.perf_counter()
        funcao()
        tempos.append((time.perf_counter() - inicio) * 1000)
    return statistics.median(tempos)


def medir_tamanho(n: int) -> dict:
    e = gerar_estoque(n)
    codigos = [it.codigo for it in e.itens]
    alvos = [random.choice(codigos) for _ in range(200)]

    busca_bin = medir_ms(lambda: [e.buscar_por_codigo(c) for c in alvos], 5) / len(alvos)
    busca_seq = medir_ms(lambda: e.buscar_por_nome("modelo 99999"), 7)  # pior caso: não acha
    ord_python = medir_ms(lambda: sorted(e.itens, key=lambda it: it.nome.lower()), 5)
    ord_insercao = (medir_ms(lambda: ordenar_insercao(e.itens, "nome"), 3)
                    if n <= LIMITE_INSERCAO else None)
    ord_insercao_v1 = (medir_ms(lambda: ordenar_insercao_v1(e.itens, "nome"), 1)
                       if n <= LIMITE_INSERCAO else None)

    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / "dados.json"
        salvar = medir_ms(lambda: e.salvar(arquivo), 5)
        carregar = medir_ms(lambda: Estoque.carregar(arquivo), 5)

    return {"n_itens": n, "busca_binaria_ms": busca_bin,
            "busca_sequencial_ms": busca_seq, "ordenacao_sorted_ms": ord_python,
            "ordenacao_insercao_ms": ord_insercao,
            "ordenacao_insercao_v1_ms": ord_insercao_v1,
            "salvar_ms": salvar, "carregar_ms": carregar}


def salvar_ambiente():
    texto = (f"Sistema operacional: {platform.system()} {platform.release()}\n"
             f"Processador: {platform.processor() or platform.machine()}\n"
             f"Python: {platform.python_version()}\n"
             f"Data: {time.strftime('%d/%m/%Y %H:%M')}\n")
    (SAIDA / "ambiente.txt").write_text(texto, encoding="utf-8")
    return texto


def gerar_graficos(linhas: list[dict]):
    try:
        import matplotlib
        matplotlib.use("Agg")                    # gera PNG sem abrir janela
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib não instalado: rode 'pip install matplotlib' "
              "para gerar os gráficos.")
        return

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False})
    n = [l["n_itens"] for l in linhas]

    # Gráfico 1: busca sequencial x binária
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(n, [l["busca_sequencial_ms"] for l in linhas], marker="o",
            color="#c2410c", label="Pesquisa sequencial (por nome)")
    ax.plot(n, [l["busca_binaria_ms"] for l in linhas], marker="s",
            color="#1f5f9e", label="Pesquisa binária (por código)")
    ax.set_xlabel("Quantidade de itens no estoque")
    ax.set_ylabel("Tempo por busca (ms)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_buscas.png", dpi=200)
    plt.close(fig)

    # Gráfico 2: ordenação (escala log, porque a diferença é enorme)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    com_ins = [l for l in linhas if l["ordenacao_insercao_ms"] is not None]
    ax.plot([l["n_itens"] for l in com_ins],
            [l["ordenacao_insercao_ms"] for l in com_ins], marker="o",
            color="#c2410c", label="Insertion sort (implementado à mão)")
    ax.plot(n, [l["ordenacao_sorted_ms"] for l in linhas], marker="s",
            color="#1f5f9e", label="sorted() do Python (Timsort)")
    ax.axhline(META_MS, color="#555", linestyle="--", linewidth=1)
    ax.text(n[0], META_MS * 1.15, f"meta: {META_MS} ms", color="#555")
    ax.set_yscale("log")
    ax.set_xlabel("Quantidade de itens no estoque")
    ax.set_ylabel("Tempo para ordenar (ms, escala log)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_ordenacao.png", dpi=200)
    plt.close(fig)

    # Gráfico extra: antes x depois da otimização do insertion sort
    if com_ins:
        antes = com_ins
        fig, ax = plt.subplots(figsize=(8, 4.5))
        largura = 0.38
        posicoes = list(range(len(antes)))
        val_antes = [l["ordenacao_insercao_v1_ms"] for l in antes]
        val_depois = [l["ordenacao_insercao_ms"] for l in antes]
        b1 = ax.bar([p - largura / 2 for p in posicoes], val_antes, largura,
                    color="#c2410c", label="Versão 1 (normaliza a cada comparação)")
        b2 = ax.bar([p + largura / 2 for p in posicoes], val_depois, largura,
                    color="#1f5f9e", label="Versão 2 (chave calculada uma vez)")
        ax.bar_label(b1, fmt="%.0f", fontsize=9)
        ax.bar_label(b2, fmt="%.0f", fontsize=9)
        ax.set_yscale("log")
        ax.set_xticks(posicoes, [l["n_itens"] for l in antes])
        ax.set_xlabel("Quantidade de itens no estoque")
        ax.set_ylabel("Tempo para ordenar por nome (ms, log)")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(SAIDA / "grafico_otimizacao.png", dpi=200)
        plt.close(fig)

    # Gráfico 3: salvar e carregar
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(n, [l["salvar_ms"] for l in linhas], marker="o", color="#1f5f9e",
            label="Salvar (JSON)")
    ax.plot(n, [l["carregar_ms"] for l in linhas], marker="s", color="#15803d",
            label="Carregar (JSON)")
    ax.axhline(META_MS, color="#555", linestyle="--", linewidth=1)
    ax.text(n[0], META_MS * 1.03, f"meta: {META_MS} ms", color="#555")
    ax.set_xlabel("Quantidade de itens no estoque")
    ax.set_ylabel("Tempo (ms)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_arquivo.png", dpi=200)
    plt.close(fig)


def main():
    SAIDA.mkdir(exist_ok=True)
    print(salvar_ambiente())
    linhas = []
    for n in TAMANHOS:
        print(f"Medindo com {n:>6} itens...", end=" ", flush=True)
        linhas.append(medir_tamanho(n))
        print("ok")

    with (SAIDA / "desempenho.csv").open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=linhas[0].keys(), delimiter=";")
        escritor.writeheader()
        for l in linhas:
            escritor.writerow({k: (f"{v:.4f}".replace(".", ",") if isinstance(v, float)
                                   else ("" if v is None else v)) for k, v in l.items()})

    print(f"\n{'itens':>7} | {'binária':>9} | {'sequenc.':>9} | {'insertion':>10} | "
          f"{'sorted':>8} | {'salvar':>8} | {'carregar':>8}   (ms)")
    for l in linhas:
        ins = f"{l['ordenacao_insercao_ms']:10.2f}" if l["ordenacao_insercao_ms"] else f"{'-':>10}"
        print(f"{l['n_itens']:>7} | {l['busca_binaria_ms']:9.4f} | "
              f"{l['busca_sequencial_ms']:9.2f} | {ins} | {l['ordenacao_sorted_ms']:8.2f} | "
              f"{l['salvar_ms']:8.2f} | {l['carregar_ms']:8.2f}")

    gerar_graficos(linhas)
    print(f"\nArquivos gerados em: {SAIDA}")


if __name__ == "__main__":
    main()
