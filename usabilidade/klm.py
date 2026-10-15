"""
klm.py - Estimativa de tempo das tarefas pelo KLM (Keystroke-Level Model).

O KLM (CARD; MORAN; NEWELL, 1980) é um método de avaliação de usabilidade
que NÃO precisa de usuários: descreve-se cada tarefa como uma sequência de
operadores elementares e soma-se o tempo-padrão de cada um. O resultado é
o tempo que um usuário EXPERIENTE levaria, sem erros. Serve para comparar
caminhos e achar tarefas que exigem passos demais.

Operadores e tempos-padrão (CARD; MORAN; NEWELL, 1980):
  K = 0,28 s  apertar uma tecla (digitador médio, ~40 palavras/min)
  P = 1,10 s  apontar o mouse para um alvo na tela
  B = 0,10 s  apertar OU soltar o botão do mouse (um clique = BB)
  H = 0,40 s  levar a mão do mouse para o teclado (ou o contrário)
  M = 1,35 s  preparação mental (decidir / localizar o próximo passo)

Rodar:  python usabilidade/klm.py
"""
from pathlib import Path

TEMPOS = {"K": 0.28, "P": 1.10, "B": 0.10, "H": 0.40, "M": 1.35}

# Cada tarefa do ROTEIRO_TESTE.md, pelo caminho mais curto do sistema.
# Formato: lista de (descrição do passo, operadores).
TAREFAS = {
    "T1 Cadastrar item": [
        ("decidir onde cadastrar", "M"),
        ("clicar em '+ Novo item'", "PBB"),
        ("mão no teclado", "H"),
        ("pensar no nome", "M"),
        ("digitar 'Headset USB' (11 teclas)", "K" * 11),
        ("Tab até categoria (Periférico já vem marcado)", "K"),
        ("Tab até quantidade", "K"),
        ("lembrar a quantidade", "M"),
        ("digitar '4'", "K"),
        ("Tab até mínimo e digitar '2'", "KK"),
        ("conferir e confirmar com Enter", "MK"),
    ],
    "T2 Registrar saída": [
        ("localizar 'Mouse USB' na tabela", "M"),
        ("duplo clique na linha (abre a saída já com o item)", "PBBBB"),
        ("mão no teclado", "H"),
        ("apagar o '1' e digitar '2'", "KK"),
        ("Recepção já é o setor padrão; Tab, Tab até responsável", "MKK"),
        ("digitar o próprio nome (6 letras)", "K" * 6),
        ("conferir e confirmar com Enter", "MK"),
    ],
    "T3 Consultar saldo": [
        ("decidir usar a busca", "M"),
        ("clicar no campo de busca", "PBB"),
        ("mão no teclado e digitar 'hdmi'", "H" + "K" * 4),
        ("ler o saldo na coluna Saldo", "M"),
    ],
    "T4 Registrar entrada": [
        ("localizar o toner na tabela", "M"),
        ("clicar na linha", "PBB"),
        ("clicar em '↓ Entrada'", "PBB"),
        ("mão no teclado, apagar o '1' e digitar '5'", "HKK"),
        ("conferir e confirmar com Enter", "MK"),
    ],
    "T5 Ler relatório": [
        ("decidir abrir o relatório", "M"),
        ("clicar em 'Relatório'", "PBB"),
        ("ler o 1º item da lista 'Itens para repor'", "M"),
    ],
}


def tempo(operadores: str) -> float:
    return sum(TEMPOS[op] for op in operadores)


def main():
    saida = Path(__file__).resolve().parent / "resultados"
    saida.mkdir(exist_ok=True)
    linhas = ["tarefa;operadores;n_teclas;n_cliques;n_mentais;tempo_estimado_s"]
    totais = {}
    for tarefa, passos in TAREFAS.items():
        ops = "".join(o for _, o in passos)
        totais[tarefa] = tempo(ops)
        print(f"\n{tarefa}: {totais[tarefa]:.1f} s")
        for descricao, o in passos:
            print(f"   {o:<14} {tempo(o):5.2f} s  {descricao}")
        linhas.append(f"{tarefa};{ops};{ops.count('K')};{ops.count('B') // 2};"
                      f"{ops.count('M')};{totais[tarefa]:.2f}".replace(".", ","))
    (saida / "klm_tarefas.csv").write_text("\n".join(linhas), encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(8, 4.2))
    barras = ax.barh(list(totais), list(totais.values()), color="#1f5f9e")
    ax.bar_label(barras, fmt="%.1f s", padding=4, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Tempo estimado para usuário experiente (s) - modelo KLM")
    ax.set_xlim(0, max(totais.values()) * 1.2)
    fig.tight_layout()
    fig.savefig(saida / "grafico_klm.png", dpi=200)
    plt.close(fig)
    print(f"\nArquivos em: {saida}")


if __name__ == "__main__":
    main()
