"""
Testes automatizados do núcleo. Rode na pasta do projeto com:

    python -m unittest discover -s testes -v

Cada teste monta um estoque do zero, executa UMA ação e confere o resultado.
Se alguém quebrar uma regra no futuro, o teste correspondente falha.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estoque import (Estoque, ErroEstoque, Item, busca_binaria_recursiva,
                     gerar_codigo, normalizar, ordenar_insercao,
                     soma_recursiva)


def estoque_exemplo() -> Estoque:
    e = Estoque()
    e.cadastrar("Mouse USB", "Periférico", 10, 3)
    e.cadastrar("Teclado ABNT2", "Periférico", 2, 3)
    e.cadastrar("Cabo de rede Cat6 2m", "Cabo", 25, 10)
    e.cadastrar("Toner HP 85A", "Impressão", 0, 2)
    return e


class TestFuncoesAuxiliares(unittest.TestCase):
    def test_normalizar_tira_acento_e_maiuscula(self):
        self.assertEqual(normalizar("  TECLÁDO Ção "), "teclado cao")

    def test_gerar_codigo(self):
        self.assertEqual(gerar_codigo("Periférico", 7), "PER-007")

    def test_soma_recursiva(self):
        self.assertEqual(soma_recursiva([]), 0)
        self.assertEqual(soma_recursiva([7]), 7)
        self.assertEqual(soma_recursiva([1, 2, 3, 4]), 10)

    def test_soma_recursiva_lista_grande_nao_estoura_pilha(self):
        # Bug encontrado pelo teste de carga: com ~1.000 saídas a versão
        # antiga dava RecursionError e o relatório travava.
        valores = list(range(100_000))
        self.assertEqual(soma_recursiva(valores), sum(valores))

    def test_ordenar_insercao_nao_altera_original(self):
        itens = [Item("C", "c", "Outro", 3, 0), Item("A", "a", "Outro", 1, 0),
                 Item("B", "b", "Outro", 2, 0)]
        ordenados = ordenar_insercao(itens, "codigo")
        self.assertEqual([i.codigo for i in ordenados], ["A", "B", "C"])
        self.assertEqual(itens[0].codigo, "C")  # original intacta

    def test_ordenar_insercao_decrescente(self):
        itens = [Item("A", "a", "Outro", q, 0) for q in (5, 1, 9, 3)]
        ordenados = ordenar_insercao(itens, "quantidade", decrescente=True)
        self.assertEqual([i.quantidade for i in ordenados], [9, 5, 3, 1])


class TestCadastro(unittest.TestCase):
    def test_codigos_sequenciais_por_categoria(self):
        e = estoque_exemplo()
        codigos = [i.codigo for i in e.itens]
        self.assertIn("PER-001", codigos)
        self.assertIn("PER-002", codigos)
        self.assertIn("CAB-001", codigos)

    def test_lista_fica_ordenada_por_codigo(self):
        e = estoque_exemplo()
        codigos = [i.codigo for i in e.itens]
        self.assertEqual(codigos, sorted(codigos))

    def test_nao_aceita_nome_duplicado(self):
        e = estoque_exemplo()
        with self.assertRaises(ErroEstoque):
            e.cadastrar("mouse usb", "Periférico", 1, 1)

    def test_nao_aceita_nome_vazio_nem_negativo(self):
        e = Estoque()
        with self.assertRaises(ErroEstoque):
            e.cadastrar("   ", "Cabo", 1, 1)
        with self.assertRaises(ErroEstoque):
            e.cadastrar("Cabo HDMI", "Cabo", -1, 1)

    def test_cadastro_com_saldo_gera_movimentacao(self):
        e = Estoque()
        e.cadastrar("Cabo HDMI", "Cabo", 5, 1)
        self.assertEqual(len(e.movimentacoes), 1)
        self.assertEqual(e.movimentacoes[0].tipo, "ENTRADA")


class TestMovimentacao(unittest.TestCase):
    def test_entrada_soma_no_saldo(self):
        e = estoque_exemplo()
        e.entrada("PER-001", 5)
        self.assertEqual(e.buscar_por_codigo("PER-001").quantidade, 15)

    def test_saida_subtrai_do_saldo(self):
        e = estoque_exemplo()
        e.saida("PER-001", 4, setor="Recepção")
        self.assertEqual(e.buscar_por_codigo("PER-001").quantidade, 6)

    def test_saida_maior_que_saldo_e_bloqueada(self):
        e = estoque_exemplo()
        with self.assertRaises(ErroEstoque):
            e.saida("PER-002", 3)
        self.assertEqual(e.buscar_por_codigo("PER-002").quantidade, 2)

    def test_quantidade_zero_ou_negativa_e_bloqueada(self):
        e = estoque_exemplo()
        for qtd in (0, -2):
            with self.assertRaises(ErroEstoque):
                e.entrada("PER-001", qtd)

    def test_item_inexistente(self):
        with self.assertRaises(ErroEstoque):
            estoque_exemplo().saida("XXX-999", 1)


class TestBuscas(unittest.TestCase):
    def test_busca_sequencial_por_pedaco_do_nome(self):
        nomes = [i.nome for i in estoque_exemplo().buscar_por_nome("CABO")]
        self.assertEqual(nomes, ["Cabo de rede Cat6 2m"])

    def test_busca_binaria_acha_e_nao_acha(self):
        e = estoque_exemplo()
        self.assertEqual(e.buscar_por_codigo("CAB-001").nome,
                         "Cabo de rede Cat6 2m")
        self.assertIsNone(e.buscar_por_codigo("PER-999"))

    def test_busca_binaria_recursiva_concorda_com_iterativa(self):
        e = estoque_exemplo()
        for item in e.itens:
            indice = busca_binaria_recursiva(e.itens, item.codigo)
            self.assertIs(e.itens[indice], item)
        self.assertEqual(busca_binaria_recursiva(e.itens, "ZZZ-000"), -1)


class TestRelatorios(unittest.TestCase):
    def test_alerta_de_estoque_minimo(self):
        alerta = [i.nome for i in estoque_exemplo().itens_abaixo_do_minimo()]
        # Toner (0) vem antes do Teclado (2): ordenado por quantidade
        self.assertEqual(alerta, ["Toner HP 85A", "Teclado ABNT2"])

    def test_resumo(self):
        e = estoque_exemplo()
        e.saida("CAB-001", 5, setor="UTI")
        r = e.resumo()
        self.assertEqual(r["itens_cadastrados"], 4)
        self.assertEqual(r["total_unidades"], 10 + 2 + 20 + 0)
        self.assertEqual(r["itens_em_alerta"], 2)
        self.assertEqual(r["itens_zerados"], 1)
        self.assertEqual(r["maior_saldo"].codigo, "CAB-001")
        self.assertEqual(r["total_saidas"], 5)

    def test_matriz_saidas_por_dia(self):
        e = estoque_exemplo()
        e.saida("PER-001", 3)
        codigos, matriz = e.matriz_saidas_por_dia()
        self.assertEqual(len(matriz), len(codigos))
        self.assertTrue(all(len(linha) == 7 for linha in matriz))
        self.assertEqual(sum(matriz[codigos.index("PER-001")]), 3)

    def test_saidas_por_setor(self):
        e = estoque_exemplo()
        e.saida("CAB-001", 5, setor="UTI")
        e.saida("PER-001", 2, setor="Recepção")
        e.saida("CAB-001", 1, setor="UTI")
        self.assertEqual(e.saidas_por_setor(), [("UTI", 6), ("Recepção", 2)])


class TestPersistencia(unittest.TestCase):
    def test_salvar_e_carregar_preserva_tudo(self):
        e = estoque_exemplo()
        e.saida("PER-001", 1, setor="Farmácia", responsavel="Arthur")
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "dados.json"
            e.salvar(arquivo)
            carregado = Estoque.carregar(arquivo)
        self.assertEqual(carregado.itens, e.itens)
        self.assertEqual(carregado.movimentacoes, e.movimentacoes)

    def test_carregar_arquivo_inexistente_devolve_vazio(self):
        e = Estoque.carregar("/caminho/que/nao/existe.json")
        self.assertEqual(e.itens, [])


if __name__ == "__main__":
    unittest.main()
