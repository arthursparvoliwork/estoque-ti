"""
analisar_usabilidade.py - Calcula os resultados do teste de usabilidade.

Entradas (preenchidas por você, com dados REAIS dos participantes):
  usabilidade/respostas_sus.csv   -> respostas do questionário SUS
  usabilidade/logs/P01.csv, ...   -> uso_log.csv de cada participante

Saídas em usabilidade/resultados/:
  sus_por_participante.csv, tarefas.csv, resumo.txt
  grafico_sus.png, grafico_tempo_tarefas.png, grafico_sucesso_tarefas.png

Rodar (na pasta do projeto):  python usabilidade/analisar_usabilidade.py
"""
import csv
import statistics
import sys
from pathlib import Path

PASTA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
SAIDA = PASTA / "resultados"
MEDIA_REFERENCIA_SUS = 68          # BANGOR; KORTUM; MILLER (2009)

# tarefa do roteiro -> nome gravado no uso_log.csv
TAREFAS_COM_LOG = {"T1 Cadastrar item": "cadastrar",
                   "T2 Registrar saída": "saida",
                   "T4 Registrar entrada": "entrada"}


def nota_sus(respostas: list[int]) -> float:
    """Fórmula de Brooke (1996)."""
    if len(respostas) != 10 or any(r not in (1, 2, 3, 4, 5) for r in respostas):
        raise ValueError(f"Respostas SUS inválidas: {respostas}")
    soma = 0
    for numero, resposta in enumerate(respostas, start=1):
        soma += (resposta - 1) if numero % 2 == 1 else (5 - resposta)
    return soma * 2.5


def classificar_sus(nota: float) -> str:
    # faixas adjetivas aproximadas de Bangor, Kortum e Miller (2009)
    if nota >= 85:
        return "Excelente"
    if nota >= 72:
        return "Bom"
    if nota >= 52:
        return "Aceitável (OK)"
    if nota >= 38:
        return "Ruim"
    return "Inaceitável"


def ler_sus() -> list[dict]:
    arquivo = PASTA / "respostas_sus.csv"
    with arquivo.open(encoding="utf-8") as f:
        linhas = [l for l in csv.DictReader(f, delimiter=";") if l["participante"].strip()]
    for l in linhas:
        l["nota"] = nota_sus([int(l[f"q{i}"]) for i in range(1, 11)])
    return linhas


def ler_logs() -> dict[str, dict]:
    """Para cada participante e tarefa: sucesso (alguma tentativa concluída),
    tempo total gasto até concluir (somando tentativas) e erros de validação."""
    resultado = {}
    for arquivo in sorted((PASTA / "logs").glob("P*.csv")):
        participante = arquivo.stem
        por_tarefa = {}
        with arquivo.open(encoding="utf-8") as f:
            for linha in csv.DictReader(f, delimiter=";"):
                t = por_tarefa.setdefault(linha["tarefa"],
                                          {"sucesso": False, "segundos": 0.0, "erros": 0})
                if t["sucesso"]:
                    continue                     # só conta até a 1ª conclusão
                t["segundos"] += float(linha["segundos"])
                t["erros"] += int(linha["erros_validacao"])
                t["sucesso"] = linha["sucesso"] == "1"
        resultado[participante] = por_tarefa
    return resultado


def main():
    SAIDA.mkdir(exist_ok=True)
    sus = ler_sus()
    logs = ler_logs()
    if not sus:
        print("respostas_sus.csv está vazio: aplique o teste primeiro "
              "(veja ROTEIRO_TESTE.md).")
        return

    notas = [l["nota"] for l in sus]
    media = statistics.mean(notas)
    desvio = statistics.stdev(notas) if len(notas) > 1 else 0.0

    with (SAIDA / "sus_por_participante.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["participante", "perfil", "nota_sus", "classificacao"])
        for l in sus:
            w.writerow([l["participante"], l["perfil"],
                        f"{l['nota']:.1f}".replace(".", ","), classificar_sus(l["nota"])])

    # tarefas: com log (T1, T2, T4) + observadas (T3, T5)
    tarefas = []
    for rotulo, nome_log in TAREFAS_COM_LOG.items():
        registros = [p[nome_log] for p in logs.values() if nome_log in p]
        if not registros:
            continue
        concluidas = [r for r in registros if r["sucesso"]]
        tarefas.append({
            "tarefa": rotulo,
            "participantes": len(registros),
            "taxa_sucesso_%": 100 * len(concluidas) / len(registros),
            "tempo_medio_s": statistics.mean(r["segundos"] for r in concluidas) if concluidas else None,
            "tempo_mediano_s": statistics.median(r["segundos"] for r in concluidas) if concluidas else None,
            "erros_total": sum(r["erros"] for r in registros),
        })
    for rotulo, coluna in (("T3 Consultar saldo", "t3_acertou"),
                           ("T5 Ler relatório", "t5_acertou")):
        respostas = [l[coluna].strip().upper() for l in sus if l.get(coluna, "").strip()]
        if respostas:
            tarefas.append({"tarefa": rotulo, "participantes": len(respostas),
                            "taxa_sucesso_%": 100 * respostas.count("S") / len(respostas),
                            "tempo_medio_s": None, "tempo_mediano_s": None,
                            "erros_total": None})
    tarefas.sort(key=lambda t: t["tarefa"])

    with (SAIDA / "tarefas.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=tarefas[0].keys() if tarefas else ["tarefa"],
                           delimiter=";")
        w.writeheader()
        for t in tarefas:
            w.writerow({k: (f"{v:.1f}".replace(".", ",") if isinstance(v, float) else
                            ("" if v is None else v)) for k, v in t.items()})

    resumo = [f"Participantes: {len(sus)}",
              f"SUS médio: {media:.1f} (desvio padrão {desvio:.1f}) -> {classificar_sus(media)}",
              f"SUS mínimo / máximo: {min(notas):.1f} / {max(notas):.1f}",
              f"Referência de mercado: {MEDIA_REFERENCIA_SUS} -> "
              f"{'ACIMA' if media > MEDIA_REFERENCIA_SUS else 'ABAIXO'} da média", ""]
    for t in tarefas:
        tempo = f", tempo médio {t['tempo_medio_s']:.1f} s" if t["tempo_medio_s"] else ""
        erros = f", {t['erros_total']} erro(s) de validação" if t["erros_total"] is not None else ""
        resumo.append(f"{t['tarefa']}: {t['taxa_sucesso_%']:.0f}% de sucesso{tempo}{erros}")
    texto = "\n".join(resumo)
    (SAIDA / "resumo.txt").write_text(texto, encoding="utf-8")
    print(texto)

    gerar_graficos(sus, media, tarefas)
    print(f"\nArquivos em: {SAIDA}")


def gerar_graficos(sus, media, tarefas):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Instale o matplotlib (pip install matplotlib) para gerar os gráficos.")
        return
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False})

    fig, ax = plt.subplots(figsize=(8, 4.5))
    nomes = [l["participante"] for l in sus]
    barras = ax.bar(nomes, [l["nota"] for l in sus], color="#1f5f9e")
    ax.bar_label(barras, fmt="%.0f", fontsize=9)
    ax.axhline(media, color="#15803d", linewidth=2, label=f"Média do sistema: {media:.1f}")
    ax.axhline(MEDIA_REFERENCIA_SUS, color="#555", linestyle="--", linewidth=1,
               label=f"Referência SUS: {MEDIA_REFERENCIA_SUS}")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Nota SUS (0 a 100)")
    ax.set_xlabel("Participante")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_sus.png", dpi=200)
    plt.close(fig)

    com_tempo = [t for t in tarefas if t["tempo_medio_s"]]
    if com_tempo:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        barras = ax.barh([t["tarefa"] for t in com_tempo],
                         [t["tempo_medio_s"] for t in com_tempo], color="#1f5f9e")
        ax.bar_label(barras, fmt="%.1f s", padding=4, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel("Tempo médio para concluir (segundos)")
        fig.tight_layout()
        fig.savefig(SAIDA / "grafico_tempo_tarefas.png", dpi=200)
        plt.close(fig)

    if tarefas:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        barras = ax.barh([t["tarefa"] for t in tarefas],
                         [t["taxa_sucesso_%"] for t in tarefas], color="#15803d")
        ax.bar_label(barras, fmt="%.0f%%", padding=4, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlim(0, 110)
        ax.set_xlabel("Participantes que concluíram a tarefa (%)")
        fig.tight_layout()
        fig.savefig(SAIDA / "grafico_sucesso_tarefas.png", dpi=200)
        plt.close(fig)


if __name__ == "__main__":
    main()
