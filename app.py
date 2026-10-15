"""
app.py - Interface gráfica (Tkinter) do Sistema de Estoque de TI.

Esta camada só cuida de TELA: mostrar dados, ler o que o usuário digitou
e chamar o núcleo (estoque.py). Nenhuma regra de negócio mora aqui.

Rodar:  python app.py
"""
import csv
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from estoque import (CATEGORIAS, DIAS_SEMANA, ErroEstoque, Estoque,
                     ordenar_insercao)

PASTA = Path(__file__).resolve().parent
ARQUIVO_DADOS = PASTA / "dados_estoque.json"
ARQUIVO_LOG = PASTA / "uso_log.csv"      # usado no teste de usabilidade

SETORES = ["Recepção", "Consultórios", "Centro Cirúrgico", "Enfermagem",
           "Farmácia", "Faturamento", "Administração", "TI"]

COR_ALERTA = "#fde2e1"      # vermelho claro: abaixo do mínimo
COR_ZERADO = "#f8b4b0"      # vermelho mais forte: sem estoque


# ---------------------------------------------------------------------------
# Log de uso: grava quanto tempo cada tarefa levou e se deu erro.
# ---------------------------------------------------------------------------
def registrar_uso(tarefa: str, segundos: float, sucesso: bool, erros: int):
    novo = not ARQUIVO_LOG.exists()
    with ARQUIVO_LOG.open("a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f, delimiter=";")
        if novo:
            escritor.writerow(["data_hora", "tarefa", "segundos",
                               "sucesso", "erros_validacao"])
        escritor.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           tarefa, f"{segundos:.2f}", int(sucesso), erros])


def dados_de_exemplo(estoque: Estoque) -> None:
    exemplos = [
        ("Mouse USB", "Periférico", 12, 4, "Almoxarifado TI - P1"),
        ("Teclado ABNT2 USB", "Periférico", 3, 4, "Almoxarifado TI - P1"),
        ("Monitor 21,5\"", "Periférico", 2, 1, "Almoxarifado TI - P3"),
        ("Leitor de código de barras", "Periférico", 1, 2, "Almoxarifado TI - P2"),
        ("Cabo de rede Cat6 2m", "Cabo", 30, 10, "Almoxarifado TI - Gaveta 1"),
        ("Cabo HDMI 1,5m", "Cabo", 6, 3, "Almoxarifado TI - Gaveta 1"),
        ("Cabo de força tripolar", "Cabo", 9, 5, "Almoxarifado TI - Gaveta 2"),
        ("Mini PC Desktop", "Computador", 2, 1, "Sala TI"),
        ("Switch 8 portas", "Rede", 1, 1, "Sala TI - Rack"),
        ("Conector RJ45 (un.)", "Rede", 80, 30, "Almoxarifado TI - Gaveta 3"),
        ("Toner HP 85A", "Impressão", 0, 2, "Almoxarifado TI - P4"),
        ("Etiqueta térmica (rolo)", "Impressão", 15, 6, "Almoxarifado TI - P4"),
    ]
    for nome, cat, qtd, minimo, local in exemplos:
        estoque.cadastrar(nome, cat, qtd, minimo, local)


# ---------------------------------------------------------------------------
# Janela base para os formulários (cadastro, entrada, saída)
# ---------------------------------------------------------------------------
class Formulario(tk.Toplevel):
    """Janela modal com campos, botão Confirmar/Cancelar, Enter e Esc.
    Mede o tempo entre abrir e concluir para o log de usabilidade."""

    def __init__(self, pai, titulo: str, nome_tarefa: str):
        super().__init__(pai)
        self.title(titulo)
        self.resizable(False, False)
        self.transient(pai)          # fica na frente da janela principal
        self.nome_tarefa = nome_tarefa
        self.inicio = time.perf_counter()
        self.erros = 0
        self.concluido = False

        self.corpo = ttk.Frame(self, padding=16)
        self.corpo.pack(fill="both", expand=True)
        self.corpo.columnconfigure(1, weight=1)
        self.linha = 0

        self.msg_erro = ttk.Label(self, foreground="#b42318", padding=(16, 0))
        self.msg_erro.pack(fill="x")

        botoes = ttk.Frame(self, padding=(16, 8, 16, 16))
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Cancelar (Esc)",
                   command=self.cancelar).pack(side="right")
        ttk.Button(botoes, text="Confirmar (Enter)", style="Destaque.TButton",
                   command=self.confirmar).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self.confirmar())
        self.bind("<Escape>", lambda _e: self.cancelar())
        self.protocol("WM_DELETE_WINDOW", self.cancelar)

    def campo(self, rotulo: str, widget):
        ttk.Label(self.corpo, text=rotulo).grid(row=self.linha, column=0,
                                                sticky="w", pady=4, padx=(0, 10))
        widget.grid(row=self.linha, column=1, sticky="ew", pady=4)
        self.linha += 1
        return widget

    def entrada_texto(self, rotulo: str, largura: int = 32):
        return self.campo(rotulo, ttk.Entry(self.corpo, width=largura))

    def entrada_numero(self, rotulo: str, inicial: int = 1):
        caixa = ttk.Spinbox(self.corpo, from_=0, to=99999, width=10)
        caixa.set(inicial)
        return self.campo(rotulo, caixa)

    def lista(self, rotulo: str, opcoes, editavel: bool = False):
        caixa = ttk.Combobox(self.corpo, values=opcoes,
                             state="normal" if editavel else "readonly")
        if opcoes:
            caixa.current(0)
        return self.campo(rotulo, caixa)

    def ler_inteiro(self, caixa, nome_campo: str) -> int:
        texto = caixa.get().strip()
        if not texto.lstrip("-").isdigit():
            raise ErroEstoque(f"'{nome_campo}' precisa ser um número inteiro.")
        return int(texto)

    def mostrar_pronto(self, primeiro_campo):
        # centraliza o formulário sobre a janela principal
        self.update_idletasks()
        pai = self.master
        x = pai.winfo_rootx() + (pai.winfo_width() - self.winfo_width()) // 2
        y = pai.winfo_rooty() + (pai.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()              # bloqueia a janela de trás (modal)
        primeiro_campo.focus_set()

    def confirmar(self):
        try:
            self.executar()          # cada formulário implementa o seu
        except ErroEstoque as erro:
            self.erros += 1
            self.msg_erro.config(text=str(erro))
            self.bell()
            return
        self.concluido = True
        self.fechar()

    def cancelar(self):
        self.fechar()

    def fechar(self):
        registrar_uso(self.nome_tarefa, time.perf_counter() - self.inicio,
                      self.concluido, self.erros)
        self.grab_release()
        self.destroy()

    def executar(self):
        raise NotImplementedError


class FormCadastro(Formulario):
    def __init__(self, app):
        super().__init__(app.raiz, "Cadastrar item", "cadastrar")
        self.app = app
        self.nome = self.entrada_texto("Nome do item")
        self.categoria = self.lista("Categoria", CATEGORIAS)
        self.quantidade = self.entrada_numero("Quantidade inicial", 0)
        self.minimo = self.entrada_numero("Estoque mínimo", 1)
        self.local = self.entrada_texto("Local (opcional)")
        self.mostrar_pronto(self.nome)

    def executar(self):
        item = self.app.estoque.cadastrar(
            self.nome.get(), self.categoria.get(),
            self.ler_inteiro(self.quantidade, "Quantidade inicial"),
            self.ler_inteiro(self.minimo, "Estoque mínimo"),
            self.local.get())
        self.app.depois_de_alterar(f"Item cadastrado: {item.codigo} - {item.nome}",
                                   selecionar=item.codigo)


class FormMovimento(Formulario):
    def __init__(self, app, tipo: str, codigo_inicial: str | None):
        titulo = "Registrar ENTRADA" if tipo == "ENTRADA" else "Registrar SAÍDA"
        super().__init__(app.raiz, titulo, tipo.lower())
        self.app, self.tipo = app, tipo
        opcoes = [f"{i.codigo} - {i.nome} (saldo {i.quantidade})"
                  for i in app.estoque.itens]
        self.item = self.lista("Item", opcoes)
        if codigo_inicial:
            for indice, texto in enumerate(opcoes):
                if texto.startswith(codigo_inicial + " "):
                    self.item.current(indice)
        self.quantidade = self.entrada_numero("Quantidade", 1)
        rotulo_setor = "Setor de destino" if tipo == "SAIDA" else "Origem / fornecedor"
        self.setor = self.lista(rotulo_setor, SETORES if tipo == "SAIDA" else [],
                                editavel=True)
        self.responsavel = self.entrada_texto("Responsável")
        self.mostrar_pronto(self.quantidade)

    def executar(self):
        if not self.item.get():
            raise ErroEstoque("Escolha um item.")
        codigo = self.item.get().split(" - ")[0]
        qtd = self.ler_inteiro(self.quantidade, "Quantidade")
        acao = self.app.estoque.saida if self.tipo == "SAIDA" else self.app.estoque.entrada
        item = acao(codigo, qtd, self.setor.get().strip(),
                    self.responsavel.get().strip())
        verbo = "Saída" if self.tipo == "SAIDA" else "Entrada"
        self.app.depois_de_alterar(
            f"{verbo} de {qtd} x {item.nome}. Saldo agora: {item.quantidade}",
            selecionar=codigo)


# ---------------------------------------------------------------------------
# Janela de relatório
# ---------------------------------------------------------------------------
class JanelaRelatorio(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.raiz)
        self.title("Relatório do estoque")
        self.geometry("760x560")
        inicio = time.perf_counter()
        estoque = app.estoque
        r = estoque.resumo()

        abas = ttk.Notebook(self)
        abas.pack(fill="both", expand=True, padx=10, pady=10)

        # Aba 1: resumo + itens para repor
        aba = ttk.Frame(abas, padding=12)
        abas.add(aba, text="Resumo")
        linhas = [
            ("Itens cadastrados", r["itens_cadastrados"]),
            ("Unidades em estoque", r["total_unidades"]),
            ("Itens abaixo do mínimo", r["itens_em_alerta"]),
            ("Itens zerados", r["itens_zerados"]),
            ("Total de unidades que saíram", r["total_saidas"]),
            ("Maior saldo", self._item(r["maior_saldo"])),
            ("Menor saldo", self._item(r["menor_saldo"])),
        ]
        for i, (rotulo, valor) in enumerate(linhas):
            ttk.Label(aba, text=rotulo + ":").grid(row=i, column=0, sticky="w")
            ttk.Label(aba, text=str(valor), font=("Segoe UI", 10, "bold")
                      ).grid(row=i, column=1, sticky="w", padx=10)
        ttk.Label(aba, text="Itens para repor (menor saldo primeiro)",
                  font=("Segoe UI", 10, "bold")).grid(row=len(linhas), column=0,
                                                      columnspan=2, sticky="w",
                                                      pady=(16, 4))
        tabela = self._tabela(aba, ["Código", "Item", "Saldo", "Mínimo", "Comprar"])
        tabela.grid(row=len(linhas) + 1, column=0, columnspan=2, sticky="nsew")
        aba.rowconfigure(len(linhas) + 1, weight=1)
        aba.columnconfigure(1, weight=1)
        for item in estoque.itens_abaixo_do_minimo():
            sugestao = item.minimo * 2 - item.quantidade   # repõe até 2x o mínimo
            tabela.insert("", "end", values=(item.codigo, item.nome,
                                             item.quantidade, item.minimo, sugestao))

        # Aba 2: saídas por setor
        aba = ttk.Frame(abas, padding=12)
        abas.add(aba, text="Saídas por setor")
        tabela = self._tabela(aba, ["Setor", "Unidades"])
        tabela.pack(fill="both", expand=True)
        for setor, total in estoque.saidas_por_setor():
            tabela.insert("", "end", values=(setor, total))

        # Aba 3: matriz item x dia da semana
        aba = ttk.Frame(abas, padding=12)
        abas.add(aba, text="Saídas por dia da semana")
        tabela = self._tabela(aba, ["Código"] + DIAS_SEMANA + ["Total"])
        tabela.pack(fill="both", expand=True)
        codigos, matriz = estoque.matriz_saidas_por_dia()
        for codigo, linha in zip(codigos, matriz):
            if sum(linha) > 0:
                tabela.insert("", "end", values=[codigo] + linha + [sum(linha)])

        registrar_uso("relatorio", time.perf_counter() - inicio, True, 0)

    @staticmethod
    def _item(item):
        return f"{item.nome} ({item.quantidade})" if item else "-"

    @staticmethod
    def _tabela(pai, colunas):
        tabela = ttk.Treeview(pai, columns=colunas, show="headings", height=8)
        for c in colunas:
            tabela.heading(c, text=c)
            largura = 260 if c in ("Item", "Setor") else (70 if len(colunas) > 5 else 90)
            tabela.column(c, width=largura, stretch=c in ("Item", "Setor"),
                          anchor="w" if c in ("Item", "Setor") else "center")
        return tabela


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------
class App:
    COLUNAS = ("codigo", "nome", "categoria", "quantidade", "minimo",
               "local", "situacao")
    TITULOS = ("Código", "Item", "Categoria", "Saldo", "Mínimo", "Local", "Situação")
    LARGURAS = (80, 230, 100, 60, 60, 190, 110)

    def __init__(self, raiz: tk.Tk, arquivo: Path = ARQUIVO_DADOS):
        self.raiz = raiz
        self.estoque = Estoque.carregar(arquivo)
        self.ordem = ("codigo", False)          # coluna e direção da ordenação
        raiz.title("Estoque de TI - Hospital")
        raiz.geometry("980x580")
        raiz.minsize(820, 460)
        self._estilos()
        self._montar_tela()
        self._atalhos()

        if not self.estoque.itens and messagebox.askyesno(
                "Primeiro uso", "O estoque está vazio.\n\n"
                "Deseja carregar alguns itens de exemplo para testar?"):
            dados_de_exemplo(self.estoque)
            self.estoque.salvar()
        self.atualizar_tabela()

    # ----- aparência ------------------------------------------------------
    def _estilos(self):
        estilo = ttk.Style()
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
        estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        estilo.configure("TButton", padding=(10, 6))
        estilo.configure("Destaque.TButton", foreground="white",
                         background="#1f5f9e")
        estilo.map("Destaque.TButton", background=[("active", "#174a7c")])

    def _montar_tela(self):
        topo = ttk.Frame(self.raiz, padding=(12, 12, 12, 6))
        topo.pack(fill="x")
        ttk.Label(topo, text="Buscar (nome ou código):").pack(side="left")
        self.busca = tk.StringVar()
        self.busca.trace_add("write", lambda *_: self.atualizar_tabela())
        self.campo_busca = ttk.Entry(topo, textvariable=self.busca, width=30)
        self.campo_busca.pack(side="left", padx=8)
        self.so_alerta = tk.BooleanVar()
        ttk.Checkbutton(topo, text="Só itens para repor", variable=self.so_alerta,
                        command=self.atualizar_tabela).pack(side="left", padx=8)

        botoes = ttk.Frame(self.raiz, padding=(12, 0, 12, 6))
        botoes.pack(fill="x")
        ttk.Button(botoes, text="+ Novo item (Ctrl+N)", style="Destaque.TButton",
                   command=self.novo_item).pack(side="left")
        ttk.Button(botoes, text="↓ Entrada (Ctrl+E)",
                   command=lambda: self.movimentar("ENTRADA")).pack(side="left", padx=6)
        ttk.Button(botoes, text="↑ Saída (Ctrl+S)",
                   command=lambda: self.movimentar("SAIDA")).pack(side="left")
        ttk.Button(botoes, text="Relatório (Ctrl+R)",
                   command=self.relatorio).pack(side="left", padx=6)
        ttk.Button(botoes, text="Excluir item",
                   command=self.excluir).pack(side="right")

        meio = ttk.Frame(self.raiz, padding=(12, 0, 12, 0))
        meio.pack(fill="both", expand=True)
        self.tabela = ttk.Treeview(meio, columns=self.COLUNAS, show="headings")
        for col, titulo, largura in zip(self.COLUNAS, self.TITULOS, self.LARGURAS):
            self.tabela.heading(col, text=titulo,
                                command=lambda c=col: self.ordenar_por(c))
            self.tabela.column(col, width=largura,
                               anchor="w" if col in ("nome", "local") else "center")
        rolagem = ttk.Scrollbar(meio, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=rolagem.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        self.tabela.tag_configure("alerta", background=COR_ALERTA)
        self.tabela.tag_configure("zerado", background=COR_ZERADO)
        self.tabela.bind("<Double-1>", lambda _e: self.movimentar("SAIDA"))

        self.status = ttk.Label(self.raiz, padding=(12, 6), anchor="w")
        self.status.pack(fill="x")
        self.rodape = ttk.Label(self.raiz, padding=(12, 0, 12, 8), anchor="w",
                                foreground="#555")
        self.rodape.pack(fill="x")

    def _atalhos(self):
        self.raiz.bind("<Control-n>", lambda _e: self.novo_item())
        self.raiz.bind("<Control-e>", lambda _e: self.movimentar("ENTRADA"))
        self.raiz.bind("<Control-s>", lambda _e: self.movimentar("SAIDA"))
        self.raiz.bind("<Control-r>", lambda _e: self.relatorio())
        self.raiz.bind("<Control-f>", lambda _e: self.campo_busca.focus_set())

    # ----- tabela ---------------------------------------------------------
    def atualizar_tabela(self, selecionar: str | None = None):
        termo = self.busca.get().strip()
        itens = self.estoque.buscar_por_nome(termo) if termo else self.estoque.itens
        if self.so_alerta.get():
            itens = [i for i in itens if i.quantidade <= i.minimo]
        coluna, decrescente = self.ordem
        itens = ordenar_insercao(itens, coluna, decrescente)

        self.tabela.delete(*self.tabela.get_children())
        for item in itens:
            if item.quantidade == 0:
                situacao, tag = "SEM ESTOQUE", "zerado"
            elif item.quantidade <= item.minimo:
                situacao, tag = "Repor", "alerta"
            else:
                situacao, tag = "OK", ""
            self.tabela.insert("", "end", iid=item.codigo, tags=(tag,), values=(
                item.codigo, item.nome, item.categoria, item.quantidade,
                item.minimo, item.local, situacao))
        if selecionar and self.tabela.exists(selecionar):
            self.tabela.selection_set(selecionar)
            self.tabela.see(selecionar)

        r = self.estoque.resumo()
        self.rodape.config(text=(
            f"{r['itens_cadastrados']} itens  •  {r['total_unidades']} unidades  •  "
            f"{r['itens_em_alerta']} para repor  •  mostrando {len(itens)}"))

    def ordenar_por(self, coluna: str):
        atual, decrescente = self.ordem
        self.ordem = (coluna, not decrescente if coluna == atual else False)
        self.atualizar_tabela()

    def codigo_selecionado(self) -> str | None:
        selecao = self.tabela.selection()
        return selecao[0] if selecao else None

    # ----- ações ----------------------------------------------------------
    def novo_item(self):
        FormCadastro(self)

    def movimentar(self, tipo: str):
        if not self.estoque.itens:
            messagebox.showinfo("Estoque vazio", "Cadastre um item primeiro.")
            return
        FormMovimento(self, tipo, self.codigo_selecionado())

    def relatorio(self):
        JanelaRelatorio(self)

    def excluir(self):
        codigo = self.codigo_selecionado()
        if not codigo:
            messagebox.showinfo("Excluir", "Selecione um item na tabela.")
            return
        item = self.estoque.buscar_por_codigo(codigo)
        if messagebox.askyesno("Excluir item",
                               f"Excluir '{item.nome}' ({codigo})?\n"
                               "O histórico de movimentações é mantido."):
            self.estoque.remover(codigo)
            self.depois_de_alterar(f"Item {codigo} excluído.")

    def depois_de_alterar(self, mensagem: str, selecionar: str | None = None):
        """Toda alteração passa por aqui: salva no arquivo e atualiza a tela."""
        try:
            self.estoque.salvar()
        except OSError as erro:
            messagebox.showerror("Erro ao salvar", f"Não foi possível salvar:\n{erro}")
        self.atualizar_tabela(selecionar)
        self.status.config(text=f"✔ {mensagem}", foreground="#1e7b34")


def main():
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
