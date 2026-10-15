"""
bot_e2e.py - TESTE PONTA A PONTA (E2E) com um bot usando a JANELA.

Diferente dos testes unitários (que chamam o núcleo direto), aqui o bot
abre a interface de verdade e executa as 5 tarefas do roteiro de
usabilidade, preenchendo os mesmos campos e acionando os mesmos botões
que uma pessoa usaria. No fim, confere se o resultado está certo.

Ele prova que o sistema FUNCIONA de ponta a ponta. Ele NÃO mede
usabilidade (bot não acha nada fácil ou difícil): isso exige pessoas.

Rodar (na pasta do projeto):
    python testes/bot_e2e.py          -> você assiste o bot trabalhando
    python testes/bot_e2e.py rapido   -> sem pausas
Não mexe nos seus dados: usa uma pasta temporária.
"""
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app as appmod  # noqa: E402

PAUSA_MS = 0 if "rapido" in sys.argv else 700   # pausa para dar para ver
pasta = Path(tempfile.mkdtemp())
appmod.ARQUIVO_LOG = pasta / "uso_log.csv"
messagebox.askyesno = lambda *a, **k: True       # "Sim" para dados de exemplo

resultados = []      # (tarefa, passou?, detalhe)


def checar(tarefa: str, condicao: bool, detalhe: str):
    resultados.append((tarefa, condicao, detalhe))
    print(f"[{'PASSOU' if condicao else 'FALHOU'}] {tarefa}: {detalhe}")


def formulario_aberto(app, classe):
    return [w for w in app.raiz.winfo_children() if isinstance(w, classe)][-1]


def digitar(campo, texto):
    campo.delete(0, "end")
    campo.insert(0, texto)


def roteiro(app):
    """Gerador: cada 'yield' devolve o controle para a janela se redesenhar."""
    e = app.estoque

    # T1 - cadastrar Headset USB, Periférico, 4 unidades, mínimo 2
    app.novo_item()
    f = formulario_aberto(app, appmod.FormCadastro)
    digitar(f.nome, "Headset USB"); yield
    f.categoria.set("Periférico")
    f.quantidade.set(4); f.minimo.set(2); yield
    f.confirmar(); yield
    novo = [i for i in e.itens if i.nome == "Headset USB"]
    checar("T1 Cadastrar item", len(novo) == 1 and novo[0].quantidade == 4,
           f"cadastrado como {novo[0].codigo if novo else '-'}")

    # T2 - saída de 2 mouses USB para a Recepção
    mouse = e.buscar_por_nome("mouse usb")[0]
    antes = mouse.quantidade
    app.tabela.selection_set(mouse.codigo); yield
    app.movimentar("SAIDA")
    f = formulario_aberto(app, appmod.FormMovimento)
    f.quantidade.set(2); f.setor.set("Recepção")
    digitar(f.responsavel, "Bot"); yield
    f.confirmar(); yield
    checar("T2 Registrar saída", mouse.quantidade == antes - 2,
           f"saldo do mouse {antes} -> {mouse.quantidade}")

    # T3 - descobrir quantos cabos HDMI existem (usando a busca da tela)
    app.busca.set("hdmi"); yield
    linhas = app.tabela.get_children()
    saldo_tela = app.tabela.item(linhas[0], "values")[3] if linhas else None
    real = e.buscar_por_nome("hdmi")[0].quantidade
    checar("T3 Consultar saldo", len(linhas) == 1 and int(saldo_tela) == real,
           f"tela mostra {saldo_tela}, núcleo tem {real}")
    app.busca.set(""); yield

    # T4 - entrada de 5 toners HP 85A
    toner = e.buscar_por_nome("toner")[0]
    antes = toner.quantidade
    app.tabela.selection_set(toner.codigo); yield
    app.movimentar("ENTRADA")
    f = formulario_aberto(app, appmod.FormMovimento)
    f.quantidade.set(5); f.setor.set("Fornecedor"); yield
    f.confirmar(); yield
    checar("T4 Registrar entrada", toner.quantidade == antes + 5,
           f"saldo do toner {antes} -> {toner.quantidade}")

    # T5 - relatório: qual item comprar com mais urgência?
    app.relatorio(); yield
    janela = formulario_aberto(app, appmod.JanelaRelatorio)
    tabelas = []
    pilha = [janela]
    while pilha:                       # procura as tabelas dentro do relatório
        w = pilha.pop()
        if isinstance(w, tk.ttk.Treeview):
            tabelas.append(w)
        pilha.extend(w.winfo_children())
    repor = next(t for t in tabelas if t["columns"][-1] == "Comprar")
    primeiro = repor.item(repor.get_children()[0], "values")
    esperado = e.itens_abaixo_do_minimo()[0]
    checar("T5 Ler relatório", primeiro[0] == esperado.codigo,
           f"primeiro da lista de compra: {primeiro[1]} (saldo {primeiro[2]})")
    yield
    janela.destroy()

    # Extra - prevenção de erro: saída maior que o saldo tem que ser barrada
    app.tabela.selection_set(mouse.codigo)
    app.movimentar("SAIDA")
    f = formulario_aberto(app, appmod.FormMovimento)
    f.quantidade.set(9999); f.confirmar(); yield
    barrou = f.winfo_exists() and "insuficiente" in f.msg_erro.cget("text")
    checar("Extra Prevenção de erro", barrou, f.msg_erro.cget("text"))
    f.cancelar()

    # Extra - o que foi salvo no arquivo é o que está na tela?
    do_arquivo = appmod.Estoque.carregar(pasta / "dados.json")
    checar("Extra Persistência", do_arquivo.itens == e.itens,
           f"{len(do_arquivo.itens)} itens no arquivo")


def main():
    raiz = tk.Tk()
    app = appmod.App(raiz, pasta / "dados.json")
    passos = roteiro(app)
    inicio = time.perf_counter()

    def proximo():
        try:
            next(passos)
            raiz.after(PAUSA_MS, proximo)
        except StopIteration:
            raiz.after(PAUSA_MS, raiz.destroy)
        except Exception as erro:      # qualquer erro = teste falhou
            checar("Execução", False, repr(erro))
            raiz.destroy()

    raiz.after(300, proximo)
    raiz.mainloop()

    passou = sum(1 for r in resultados if r[1])
    print(f"\n{passou}/{len(resultados)} verificações passaram "
          f"em {time.perf_counter() - inicio:.1f} s")
    sys.exit(0 if passou == len(resultados) else 1)


if __name__ == "__main__":
    main()
