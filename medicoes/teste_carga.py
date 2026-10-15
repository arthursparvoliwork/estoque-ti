"""
teste_carga.py - TESTE DE CARGA / ESTRESSE com usuários simulados (bots).

Ideia (parecida com um "ataque" de muitos acessos, mas feito no SEU
próprio sistema, que é o que empresas fazem antes de pôr algo em produção):
  - N bots disparam milhares de operações aleatórias, intercaladas,
    imitando um dia de uso muito intenso do estoque;
  - toda operação que altera dados SALVA o arquivo, como a interface faz;
  - medimos o tempo de cada operação (latência) e quantas cabem por
    segundo (vazão);
  - no fim, conferimos se os dados continuam CONSISTENTES (invariantes).

Atenção: fazer isso contra sistema dos outros (DDoS) é crime
(Lei 12.737/2012). Teste de carga é só no que é seu.

Rodar (na pasta do projeto):   python medicoes/teste_carga.py
Saídas em medicoes/resultados/: carga_resumo.csv, carga_operacoes.csv,
grafico_carga_latencia.png, grafico_carga_tempo.png
"""
import csv
import traceback
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from estoque import CATEGORIAS, ErroEstoque, Estoque  # noqa: E402

SAIDA = Path(__file__).resolve().parent / "resultados"
NUM_BOTS = 50                    # "usuários" simultâneos simulados
OPERACOES_POR_BOT = int(sys.argv[1]) if len(sys.argv) > 1 else 200          # 50 x 200 = 10.000 operações
ITENS_INICIAIS = 300             # tamanho realista de um estoque de TI
SETORES = ["Recepção", "UTI", "Farmácia", "Faturamento", "Enfermagem", "TI"]
META_MS = 100
random.seed(2026)                # reprodutível

# Operação -> peso (quanto mais peso, mais vezes os bots escolhem).
# Imita o uso real: consultar é bem mais comum que cadastrar.
OPERACOES = {"buscar_nome": 30, "buscar_codigo": 10, "saida": 25,
             "entrada": 15, "relatorio": 10, "cadastrar": 10}


def percentil(valores: list[float], p: float) -> float:
    """p95 = 95% das operações foram MAIS RÁPIDAS que este valor.
    É a métrica que importa: média esconde os casos lentos."""
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, int(round(p / 100 * (len(ordenados) - 1))))
    return ordenados[indice]


class Bot:
    """Um usuário simulado. Cada bot tem seu nome e escolhe ações ao acaso."""

    def __init__(self, numero: int, estoque: Estoque):
        self.nome = f"bot{numero:02d}"
        self.estoque = estoque
        self.cadastros = 0

    def agir(self) -> tuple[str, str]:
        """Executa UMA operação. Devolve (operação, resultado)."""
        op = random.choices(list(OPERACOES), weights=OPERACOES.values())[0]
        e = self.estoque
        item = random.choice(e.itens)
        try:
            if op == "buscar_nome":
                e.buscar_por_nome(random.choice(["mouse", "cabo", "toner", "xyz"]))
            elif op == "buscar_codigo":
                e.buscar_por_codigo(item.codigo)
            elif op == "relatorio":
                e.resumo()
                e.matriz_saidas_por_dia()
                e.saidas_por_setor()
            elif op == "saida":
                # às vezes pede MAIS do que tem: o sistema TEM que recusar
                e.saida(item.codigo, random.randint(1, 8),
                        random.choice(SETORES), self.nome)
                e.salvar()
            elif op == "entrada":
                e.entrada(item.codigo, random.randint(1, 10), "Fornecedor", self.nome)
                e.salvar()
            elif op == "cadastrar":
                self.cadastros += 1
                e.cadastrar(f"Item do {self.nome} n{self.cadastros}",
                            random.choice(CATEGORIAS), random.randint(0, 20),
                            random.randint(1, 5))
                e.salvar()
            return op, "ok"
        except ErroEstoque:
            return op, "recusada"   # regra de negócio funcionando (não é bug)


def checar_invariantes(estoque: Estoque, arquivo: Path) -> list[str]:
    """Regras que precisam ser verdade SEMPRE, não importa o que os bots fizeram."""
    problemas = []
    # 1. nenhum saldo negativo
    for i in estoque.itens:
        if i.quantidade < 0:
            problemas.append(f"saldo negativo em {i.codigo}")
    # 2. saldo = entradas - saídas (o histórico bate com o saldo)
    saldo_calculado = {}
    for m in estoque.movimentacoes:
        sinal = 1 if m.tipo == "ENTRADA" else -1
        saldo_calculado[m.codigo] = saldo_calculado.get(m.codigo, 0) + sinal * m.quantidade
    for i in estoque.itens:
        if saldo_calculado.get(i.codigo, 0) != i.quantidade:
            problemas.append(f"histórico não bate com o saldo em {i.codigo}")
    # 3. lista continua ordenada por código (invariante da busca binária)
    codigos = [i.codigo for i in estoque.itens]
    if codigos != sorted(codigos):
        problemas.append("lista de itens perdeu a ordenação")
    # 4. códigos únicos
    if len(set(codigos)) != len(codigos):
        problemas.append("código duplicado")
    # 5. o que está no arquivo é igual ao que está na memória
    do_arquivo = Estoque.carregar(arquivo)
    if do_arquivo.itens != estoque.itens or do_arquivo.movimentacoes != estoque.movimentacoes:
        problemas.append("arquivo salvo diferente da memória")
    return problemas


def main():
    SAIDA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / "carga.json"
        estoque = Estoque(arquivo)
        for n in range(ITENS_INICIAIS):
            estoque.cadastrar(f"Item inicial {n}", CATEGORIAS[n % len(CATEGORIAS)],
                              random.randint(0, 30), random.randint(1, 5))
        estoque.salvar()

        bots = [Bot(n + 1, estoque) for n in range(NUM_BOTS)]
        fila = [b for b in bots for _ in range(OPERACOES_POR_BOT)]
        random.shuffle(fila)     # intercala as ações dos bots

        print(f"{NUM_BOTS} bots, {len(fila)} operações, estoque inicial de "
              f"{ITENS_INICIAIS} itens...")
        registros = []           # (ordem, operacao, resultado, ms)
        erros_inesperados = []
        inicio_total = time.perf_counter()
        for ordem, bot in enumerate(fila, start=1):
            inicio = time.perf_counter()
            try:
                op, resultado = bot.agir()
            except Exception as erro:          # qualquer outro erro = BUG
                erros_inesperados.append(traceback.format_exc(limit=3))
                op, resultado = "?", "ERRO"
            registros.append((ordem, op, resultado,
                              (time.perf_counter() - inicio) * 1000))
            if ordem % 2000 == 0:
                print(f"  {ordem} operações...")
        duracao = time.perf_counter() - inicio_total

        problemas = checar_invariantes(estoque, arquivo)
        final_itens, final_movs = len(estoque.itens), len(estoque.movimentacoes)

    # ----- estatísticas por operação -----
    resumo = []
    for op in list(OPERACOES) + ["TODAS"]:
        tempos = [r[3] for r in registros if op == "TODAS" or r[1] == op]
        if not tempos:
            continue
        resumo.append({
            "operacao": op, "quantidade": len(tempos),
            "recusadas_pela_regra": sum(1 for r in registros
                                        if (op == "TODAS" or r[1] == op) and r[2] == "recusada"),
            "media_ms": statistics.mean(tempos), "p50_ms": percentil(tempos, 50),
            "p95_ms": percentil(tempos, 95), "p99_ms": percentil(tempos, 99),
            "max_ms": max(tempos),
            "dentro_meta_%": 100 * sum(t <= META_MS for t in tempos) / len(tempos),
        })

    with (SAIDA / "carga_resumo.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=resumo[0].keys(), delimiter=";")
        w.writeheader()
        for l in resumo:
            w.writerow({k: f"{v:.3f}".replace(".", ",") if isinstance(v, float) else v
                        for k, v in l.items()})
    with (SAIDA / "carga_operacoes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["ordem", "operacao", "resultado", "ms"])
        for r in registros:
            w.writerow([r[0], r[1], r[2], f"{r[3]:.3f}".replace(".", ",")])

    texto = [f"Bots: {NUM_BOTS} | operações: {len(registros)} | "
             f"duração: {duracao:.1f} s | vazão: {len(registros) / duracao:.0f} op/s",
             f"Estoque final: {final_itens} itens, {final_movs} movimentações",
             f"Erros inesperados (bugs): {len(erros_inesperados)}",
             *(["Primeiro erro inesperado:", erros_inesperados[0]] if erros_inesperados else []),
             f"Invariantes violadas: {len(problemas)} {problemas[:3] if problemas else ''}",
             "",
             f"{'operação':<14}{'qtd':>6}{'recus.':>8}{'p50':>9}{'p95':>9}{'p99':>9}"
             f"{'máx':>9}{'≤100ms':>9}"]
    for l in resumo:
        texto.append(f"{l['operacao']:<14}{l['quantidade']:>6}{l['recusadas_pela_regra']:>8}"
                     f"{l['p50_ms']:>9.2f}{l['p95_ms']:>9.2f}{l['p99_ms']:>9.2f}"
                     f"{l['max_ms']:>9.2f}{l['dentro_meta_%']:>8.1f}%")
    print("\n".join(texto))
    (SAIDA / "carga_resumo.txt").write_text("\n".join(texto), encoding="utf-8")
    gerar_graficos(registros)


def gerar_graficos(registros):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("pip install matplotlib para gerar os gráficos")
        return
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False})

    # Histograma: quantas operações levaram cada faixa de tempo
    # (o mesmo tipo de gráfico que o professor mostrou na aula 3)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    tempos = [r[3] for r in registros]
    ax.hist(tempos, bins=40, color="#1f5f9e", edgecolor="white")
    ax.axvline(META_MS, color="#555", linestyle="--", linewidth=1)
    ax.text(META_MS, ax.get_ylim()[1] * 0.9, f" meta: {META_MS} ms", color="#555")
    ax.set_xlabel("Tempo de resposta da operação (ms)")
    ax.set_ylabel("Quantidade de operações")
    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_carga_latencia.png", dpi=200)
    plt.close(fig)

    # Tempo ao longo do teste: as operações que salvam ficam mais lentas
    # conforme o histórico (JSON) cresce?
    fig, ax = plt.subplots(figsize=(8, 4.5))
    blocos = 50
    tam = len(registros) // blocos
    for op, cor, rotulo in (("saida", "#c2410c", "Saída (salva o arquivo)"),
                            ("buscar_nome", "#1f5f9e", "Busca por nome")):
        xs, ys = [], []
        for b in range(blocos):
            fatia = [r[3] for r in registros[b * tam:(b + 1) * tam] if r[1] == op]
            if fatia:
                xs.append((b + 1) * tam)
                ys.append(statistics.median(fatia))
        ax.plot(xs, ys, color=cor, label=rotulo)
    ax.set_xlabel("Operações já executadas pelos bots")
    ax.set_ylabel("Tempo mediano (ms)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_carga_tempo.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
