// Gera o relatório do Projeto Integrador em .docx (ABNT / modelo do professor).
// Uso: node gerar_relatorio.js [paginas.json]
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, Header, PageNumber, WidthType, BorderStyle,
  PageBreak, ShadingType, PositionalTab, PositionalTabAlignment,
  PositionalTabRelativeTo, PositionalTabLeader, LevelFormat, TabStopType, Tab, VerticalAlign,
} = require("docx");

const PROJ = "/home/claude/estoque-ti";
const RES = `${PROJ}/medicoes/resultados`;
const paginas = process.argv[2] && fs.existsSync(process.argv[2])
  ? JSON.parse(fs.readFileSync(process.argv[2], "utf8")) : {};

// ---------- dados medidos (lidos dos CSV, nada digitado à mão) ----------
function lerCSV(arq) {
  const [cab, ...linhas] = fs.readFileSync(arq, "utf8").trim().split(/\r?\n/);
  const cols = cab.split(";");
  return linhas.map(l => Object.fromEntries(l.split(";").map((v, i) => [cols[i], v])));
}
const num = s => (s === "" || s === undefined ? null : parseFloat(String(s).replace(",", ".")));
const fmt = (v, casas) => v === null ? "–" :
  v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const desemp = lerCSV(`${RES}/desempenho.csv`);
const carga = lerCSV(`${RES}/carga_resumo.csv`);
const klm = lerCSV(`${PROJ}/usabilidade/resultados/klm_tarefas.csv`);
const linhaN = n => desemp.find(r => r.n_itens === String(n));
const d1000 = linhaN(1000), d5000 = linhaN(5000), d20000 = linhaN(20000);
const cTodas = carga.find(r => r.operacao === "TODAS");
const cOp = op => carga.find(r => r.operacao === op);
const ganho1000 = num(d1000.ordenacao_insercao_v1_ms) / num(d1000.ordenacao_insercao_ms);
const ambiente = fs.readFileSync(`${RES}/ambiente.txt`, "utf8");
const pythonVer = ambiente.match(/Python: (.+)/)[1].trim();
const soVer = ambiente.match(/Sistema operacional: (\S+)/)[1].trim();

// ---------- estilo base ----------
const FONTE = "Arial";
const T12 = 24, T10 = 20;
const RECUO = 709;               // 1,25 cm
const LARG_TEXTO = 9070;         // 21 - 3 - 2 = 16 cm em DXA
let nFig = 0, nTab = 0, nQuadro = 0;

// texto com *itálico* e **negrito**
function runs(texto, extra = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let ult = 0, m;
  while ((m = re.exec(texto))) {
    if (m.index > ult) out.push(new TextRun({ text: texto.slice(ult, m.index), font: FONTE, ...extra }));
    const negrito = m[0].startsWith("**");
    out.push(new TextRun({ text: m[0].replace(/\*/g, ""), font: FONTE, bold: negrito || extra.bold,
                           italics: !negrito || extra.italics, ...extra, ...(negrito ? { bold: true } : { italics: true }) }));
    ult = m.index + m[0].length;
  }
  if (ult < texto.length) out.push(new TextRun({ text: texto.slice(ult), font: FONTE, ...extra }));
  return out;
}
const p = (texto) => new Paragraph({
  children: runs(texto, { size: T12 }), alignment: AlignmentType.JUSTIFIED,
  indent: { firstLine: RECUO }, spacing: { line: 360, after: 200 },
});
const vazio = (linhas = 1, line = 360) => Array.from({ length: linhas },
  () => new Paragraph({ children: [new TextRun({ text: "", font: FONTE, size: T12 })], spacing: { line, after: 0 } }));
const marcador = (texto) => new Paragraph({
  children: runs(texto, { size: T12 }), alignment: AlignmentType.JUSTIFIED,
  numbering: { reference: "marcadores", level: 0 }, spacing: { line: 360, after: 80 },
});
const quebra = () => new Paragraph({ children: [new PageBreak()] });

function h1(texto, novaPagina = true) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1, pageBreakBefore: novaPagina,
    children: [new TextRun({ text: texto.toUpperCase(), font: FONTE, size: T12, bold: true })],
    spacing: { line: 360, before: 0, after: 360 },
  });
}
function h2(texto) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text: texto, font: FONTE, size: T12, bold: true })],
    spacing: { line: 360, before: 360, after: 360 }, keepNext: true,
  });
}
const tituloCentral = (texto) => new Paragraph({
  children: [new TextRun({ text: texto, font: FONTE, size: T12, bold: true })],
  alignment: AlignmentType.CENTER, spacing: { line: 360, after: 360 },
});

function legenda(texto) {     // acima da ilustração (Arial 10, negrito, centralizado)
  return new Paragraph({ children: [new TextRun({ text: texto, font: FONTE, size: T10, bold: true })],
    alignment: AlignmentType.CENTER, spacing: { before: 240, after: 80 }, keepNext: true });
}
function fonte(texto) {
  return new Paragraph({ children: runs(`Fonte: ${texto}`, { size: T10 }),
    alignment: AlignmentType.CENTER, spacing: { before: 60, after: 280 } });
}
function figura(titulo, arquivo, larguraPx, fonteTxt) {
  nFig++;
  const img = fs.readFileSync(arquivo);
  const [w, h] = tamanhoPng(img);
  return [
    legenda(`Figura ${nFig} – ${titulo}`),
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, children: [new ImageRun({
      type: "png", data: img, transformation: { width: larguraPx, height: Math.round(larguraPx * h / w) },
      altText: { title: titulo, description: titulo, name: path.basename(arquivo) } })] }),
    fonte(fonteTxt),
  ];
}
function tamanhoPng(buf) { return [buf.readUInt32BE(16), buf.readUInt32BE(20)]; }

// Tabela (padrão IBGE: só bordas horizontais) ou Quadro (fechado)
function grade(tipo, titulo, cabecalho, linhas, largurasCm, fonteTxt, tam = T10) {
  const n = tipo === "Tabela" ? ++nTab : ++nQuadro;
  const largs = largurasCm.map(c => Math.round(c * 567));
  const total = largs.reduce((a, b) => a + b, 0);
  const fino = { style: BorderStyle.SINGLE, size: 6, color: "000000" };
  const nada = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const fechado = tipo === "Quadro";
  const manterJunto = linhas.length <= 12;   // tabela curta não se divide entre páginas
  const celula = (txt, i, ehCab, ultimaLinha) => new TableCell({
    width: { size: largs[i], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    shading: ehCab && fechado ? { type: ShadingType.CLEAR, fill: "E8EEF5", color: "auto" } : undefined,
    borders: fechado ? { top: fino, bottom: fino, left: fino, right: fino } : {
      top: ehCab ? fino : nada, bottom: (ehCab || ultimaLinha) ? fino : nada, left: nada, right: nada },
    children: [new Paragraph({ children: runs(String(txt), { size: tam, bold: ehCab }),
      keepNext: manterJunto && !ultimaLinha,
      alignment: (i === 0 || (fechado && !ehCab)) ? AlignmentType.LEFT : AlignmentType.CENTER })],
  });
  const tabela = new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: largs, alignment: AlignmentType.CENTER,
    rows: [new TableRow({ tableHeader: true, children: cabecalho.map((c, i) => celula(c, i, true, false)) }),
      ...linhas.map((l, j) => new TableRow({ cantSplit: true,
        children: l.map((c, i) => celula(c, i, false, j === linhas.length - 1)) }))],
  });
  return [legenda(`${tipo} ${n} – ${titulo}`), tabela, fonte(fonteTxt)];
}

// ---------- sumário (números de página vêm da 2ª passada) ----------
const ENTRADAS = [];
function sec(nivel, texto) {           // registra no sumário e devolve o título
  ENTRADAS.push({ nivel, texto });
  return nivel === 1 ? h1(texto) : h2(texto);
}
function sumario() {
  return ENTRADAS.map(e => new Paragraph({
    spacing: { line: 360, after: 0 },
    tabStops: [{ type: TabStopType.RIGHT, position: LARG_TEXTO, leader: "dot" }],
    children: [
      new TextRun({ text: e.nivel === 1 ? e.texto.toUpperCase() : e.texto, font: FONTE, size: T12, bold: e.nivel === 1 }),
      new TextRun({ children: [new Tab()], font: FONTE, size: T12 }),
      new TextRun({ text: String(paginas[e.texto] ?? "00"), font: FONTE, size: T12, bold: e.nivel === 1 }),
    ],
  }));
}

// =====================================================================
// CONTEÚDO
// =====================================================================
const AUTOR = "ARTHUR SPARVOLI DE ARAUJO";
const TITULO = "SISTEMA DE CONTROLE DE ESTOQUE DE TI PARA AMBIENTE HOSPITALAR";
const SUBTITULO = "desenvolvimento em Python e avaliação de desempenho e usabilidade";
const REPO = "https://github.com/arthursparvoliwork/estoque-ti";

function realce(texto) {
  return new TextRun({ text: texto, font: FONTE, size: T12, highlight: "yellow" });
}
const centro = (children, extra = {}) => new Paragraph({ alignment: AlignmentType.CENTER, children,
  spacing: { line: 360, after: 0, ...extra } });
const tc = (t, extra = {}) => new TextRun({ text: t, font: FONTE, size: T12, ...extra });

const capa = [
  centro([tc("UNIVERSIDADE SANTO AMARO – UNISA", { bold: true })]),
  centro([tc("CURSO DE ENGENHARIA DE SOFTWARE", { bold: true })]),
  centro([tc("PROJETO INTEGRADOR: LABORATÓRIO DE PROGRAMAÇÃO", { bold: true })]),
  centro([tc(AUTOR)], { before: 1700 }),
  centro([tc("RA: "), realce("[preencher]"), tc("   Turma: "), realce("[preencher]")]),
  centro([tc(`${TITULO}:`, { bold: true })], { before: 2400 }),
  centro([tc(SUBTITULO)]),
  centro([tc("Professor: Danilo Cardenuto Ferreira")], { before: 1200 }),
  centro([tc("Repositório do código-fonte:")], { before: 240 }),
  centro([tc(REPO)]),
  centro([tc("SÃO PAULO", { bold: true })], { before: 2600 }),
  centro([tc("2026", { bold: true })]),
];

const resumoTxt = "O controle de equipamentos e insumos de Tecnologia da Informação (TI) em ambientes hospitalares costuma ser feito de forma informal, o que favorece a falta de itens críticos, como periféricos e suprimentos de impressão, no momento em que os setores assistenciais e administrativos precisam deles. Este trabalho apresenta o desenvolvimento de um sistema desktop de controle de estoque de TI, implementado em Python com interface gráfica Tkinter, que contempla cadastro de itens, registro de entradas e saídas por setor, alerta de estoque mínimo e relatórios. O sistema aplica registros, vetores, matrizes, pesquisa sequencial e binária, ordenação por inserção e funções recursivas. A qualidade foi avaliada segundo as características de eficiência de desempenho e de usabilidade da norma ISO/IEC 25010, por meio de medição de tempos com estoques de 100 a 20.000 itens, teste de carga com 50 usuários simulados executando 10.000 operações, teste automatizado ponta a ponta, avaliação heurística, percurso cognitivo com personas e estimativa de tempo de tarefas pelo modelo Keystroke-Level Model. As medições revelaram dois defeitos, um gargalo na ordenação e um estouro de recursão no relatório, ambos corrigidos. Após as correções, todas as operações do teste de carga responderam em até 100 ms, sem nenhuma inconsistência nos dados. Conclui-se que o sistema atende ao objetivo para o porte de um estoque de TI hospitalar, com limitações de escalabilidade decorrentes do armazenamento em arquivo JSON.";
const abstractTxt = "Inventory control of Information Technology (IT) equipment and supplies in hospital settings is often handled informally, which leads to shortages of critical items, such as peripherals and printing supplies, when clinical and administrative departments need them. This work presents the development of a desktop IT inventory control system, implemented in Python with a Tkinter graphical interface, covering item registration, stock entries and withdrawals by department, minimum stock alerts and reports. The system applies records, arrays, matrices, sequential and binary search, insertion sort and recursive functions. Quality was assessed according to the performance efficiency and usability characteristics of the ISO/IEC 25010 standard, through time measurements with inventories of 100 to 20,000 items, a load test with 50 simulated users performing 10,000 operations, an automated end-to-end test, heuristic evaluation, a cognitive walkthrough with personas and task time estimation with the Keystroke-Level Model. The measurements revealed two defects, a sorting bottleneck and a recursion overflow in the report, both of which were fixed. After the fixes, every operation in the load test responded within 100 ms, with no data inconsistency. It is concluded that the system meets its objective for the size of a hospital IT inventory, with scalability limitations arising from JSON file storage.";

const resumoBloco = (titulo, texto, rotulo, chaves) => [
  tituloCentral(titulo),
  new Paragraph({ children: runs(texto, { size: T12 }), alignment: AlignmentType.JUSTIFIED, spacing: { line: 240, after: 240 } }),
  new Paragraph({ children: [tc(`${rotulo}: `, { bold: true }), tc(chaves)], spacing: { line: 240 } }),
];

// ---------- corpo ----------
const corpo = [];
const add = (...xs) => xs.flat().forEach(x => corpo.push(x));

add(sec(1, "1 Introdução"));
add(p("A operação de um hospital depende cada vez mais de recursos de Tecnologia da Informação. Computadores na recepção e nos consultórios, leitores de código de barras na farmácia, impressoras de etiquetas e pulseiras de identificação e a rede que conecta o prontuário eletrônico fazem parte da rotina assistencial e administrativa. Quando um desses recursos falha e não há peça de reposição disponível, o atendimento é diretamente afetado: uma impressora sem toner pode atrasar a recepção, e um leitor de código de barras defeituoso pode interromper a dispensação de medicamentos."));
add(p("Em instituições de pequeno e médio porte, como um hospital-dia, o estoque de TI costuma ser pequeno, da ordem de dezenas a poucas centenas de itens, e é frequentemente controlado de maneira informal, por anotações ou planilhas sem validação. Esse tipo de controle não impede o registro de saídas maiores do que o saldo existente, não avisa quando um item atinge a quantidade mínima e não registra para qual setor cada item foi entregue, o que dificulta o planejamento de compras e a rastreabilidade."));
add(p("Este trabalho foi motivado pela vivência do autor como assistente de TI em um hospital-dia localizado na zona sul da cidade de São Paulo, onde a reposição de periféricos e suprimentos é uma demanda recorrente do suporte técnico. A questão que orientou o projeto foi: **como controlar o estoque de equipamentos e insumos de TI de um hospital-dia de forma simples, garantindo respostas rápidas e facilidade de uso para a equipe?**"));
add(p("Para responder a essa questão, foi desenvolvido um programa em Python com interface gráfica, aplicando os conteúdos de algoritmos e estruturas de dados estudados no curso, e a qualidade do resultado foi avaliada com base no modelo de qualidade de produto de software da norma ISO/IEC 25010 (INTERNATIONAL ORGANIZATION FOR STANDARDIZATION, 2011), com foco nas características de eficiência de desempenho e de usabilidade."));

add(sec(1, "2 Objetivos"));
add(p("O objetivo geral deste trabalho é desenvolver um sistema de controle de estoque de equipamentos e insumos de TI para um hospital-dia e avaliar a sua qualidade quanto ao desempenho e à usabilidade."));
add(p("Para alcançar o objetivo geral, foram definidos os seguintes objetivos específicos:"));
["implementar o cadastro de itens e o registro de entradas e saídas por setor, impedindo saídas maiores do que o saldo disponível;",
 "sinalizar automaticamente os itens que atingiram o estoque mínimo e gerar relatórios de reposição e de consumo por setor e por dia da semana;",
 "aplicar, na implementação, registros, vetores, matrizes, pesquisa sequencial e binária, ordenação e funções recursivas;",
 "medir o tempo de resposta das operações em diferentes tamanhos de estoque e sob carga de usuários simulados;",
 "avaliar a usabilidade da interface por meio de avaliação heurística e de estimativa de tempo das tarefas;",
 "verificar o funcionamento do sistema por meio de testes automatizados."].forEach(t => add(marcador(t)));

add(sec(1, "3 Justificativa"));
add(p("Existem no mercado sistemas de gestão empresarial e de controle de estoque com recursos amplos, porém essas soluções foram projetadas para atender a um conjunto grande de processos, exigem licenciamento, implantação e treinamento, e costumam estar fora do alcance de uma equipe de suporte para um problema pontual. O estoque de TI de um hospital-dia, por outro lado, exige poucas funções, mas elas precisam estar corretas: impedir saldo negativo, avisar quando é hora de comprar e registrar o destino de cada item."));
add(p("Uma planilha eletrônica, alternativa comum, não oferece essas garantias por padrão, pois aceita valores inconsistentes e depende da disciplina de quem a preenche. Um programa dedicado, simples e sem custo de licença, permite incorporar as regras de negócio diretamente no software, reduzindo erros de registro. Além disso, o histórico de movimentações por setor fornece informação objetiva para o planejamento de compras, contribuindo para que itens críticos não faltem no momento em que o atendimento ao paciente depende deles."));
add(p("Do ponto de vista acadêmico, o projeto permite aplicar em um problema real os conteúdos de algoritmos e estruturas de dados e, principalmente, verificar com medições se as escolhas de implementação produzem um sistema rápido e fácil de usar, em vez de apenas presumir que isso ocorre."));

add(sec(1, "4 Introdução teórica"));
add(sec(2, "4.1 Qualidade de produto de software: ISO 9126, ISO 25010 e ISO 25019"));
add(p("A norma ISO/IEC 9126-1 estabeleceu um modelo de qualidade de produto de software organizado em seis características: funcionalidade, confiabilidade, usabilidade, eficiência, manutenibilidade e portabilidade, cada uma subdividida em subcaracterísticas (INTERNATIONAL ORGANIZATION FOR STANDARDIZATION, 2001). Esse modelo foi substituído pela série SQuaRE (*Systems and software Quality Requirements and Evaluation*), cuja norma ISO/IEC 25010 ampliou o modelo de qualidade de produto para oito características: adequação funcional, eficiência de desempenho, compatibilidade, usabilidade, confiabilidade, segurança, manutenibilidade e portabilidade (INTERNATIONAL ORGANIZATION FOR STANDARDIZATION, 2011)."));
add(p("A versão de 2011 da ISO/IEC 25010 também descrevia um modelo de qualidade em uso, voltado ao resultado obtido pelo usuário ao interagir com o sistema em um contexto real. Na revisão da série publicada em 2023, esse modelo passou a ser tratado em uma norma própria, a ISO/IEC 25019, que considera aspectos como efetividade, eficiência e satisfação dos usuários (INTERNATIONAL ORGANIZATION FOR STANDARDIZATION, 2023). Neste trabalho, a terminologia da ISO/IEC 25010 de 2011 foi adotada para a qualidade do produto, e a ISO/IEC 25019 serve de referência para a qualidade percebida no uso."));
add(sec(2, "4.2 Eficiência de desempenho"));
add(p("Na ISO/IEC 25010, a eficiência de desempenho trata do desempenho do sistema em relação à quantidade de recursos utilizados, e uma de suas subcaracterísticas é o comportamento em relação ao tempo, que se refere aos tempos de resposta e de processamento (INTERNATIONAL ORGANIZATION FOR STANDARDIZATION, 2011). Para definir uma meta, foi adotado o limite proposto por Nielsen (1993), segundo o qual respostas de até cerca de 0,1 segundo são percebidas pelo usuário como instantâneas, sem necessidade de qualquer indicação de espera."));
add(p("O tempo de resposta depende diretamente dos algoritmos empregados. A pesquisa sequencial examina os elementos um a um e tem custo proporcional ao número de elementos, O(n), enquanto a pesquisa binária, aplicável apenas a dados ordenados, descarta metade do intervalo a cada comparação e tem custo O(log n) (CORMEN et al., 2012). Do mesmo modo, a ordenação por inserção tem custo O(n²) no pior caso e O(n) quando os dados já estão ordenados, sendo adequada a conjuntos pequenos, mas não a grandes volumes (CORMEN et al., 2012; MANZANO; OLIVEIRA, 2016)."));
add(sec(2, "4.3 Usabilidade"));
add(p("A usabilidade é definida na ISO/IEC 25010 como o grau em que um produto pode ser usado por usuários específicos para atingir objetivos com efetividade, eficiência e satisfação em um contexto de uso, e se desdobra em subcaracterísticas como apreensibilidade, operabilidade, proteção contra erros do usuário e estética da interface (INTERNATIONAL ORGANIZATION FOR STANDARDIZATION, 2011)."));
add(p("Entre os métodos de avaliação de usabilidade, a avaliação heurística consiste em examinar a interface com base em um conjunto de princípios reconhecidos. Nielsen (1994) propôs dez heurísticas, entre elas a visibilidade do status do sistema, a prevenção de erros e a flexibilidade e eficiência de uso, e classificou a gravidade dos problemas encontrados em uma escala de 0 (não é problema) a 4 (catástrofe) (NIELSEN, 1993)."));
add(p("Outro método que dispensa a participação de usuários é o *Keystroke-Level Model* (KLM), proposto por Card, Moran e Newell (1980). Nele, cada tarefa é descrita como uma sequência de operadores elementares, como pressionar uma tecla, apontar com o mouse, clicar, mover a mão entre mouse e teclado e preparar-se mentalmente, e o tempo de execução de um usuário experiente é estimado pela soma dos tempos-padrão desses operadores. Para medir a satisfação percebida por usuários reais, um instrumento difundido é o *System Usability Scale* (SUS), questionário de dez itens que resulta em uma nota de 0 a 100 (BROOKE, 1996)."));
add(sec(2, "4.4 Linguagem Python e biblioteca padrão"));
add(p("Python é uma linguagem de alto nível com sintaxe legível e ampla biblioteca padrão, adequada ao ensino de programação e ao desenvolvimento de aplicações (PERKOVIC, 2016). A biblioteca padrão inclui o módulo *tkinter*, para interfaces gráficas, o módulo *json*, para leitura e gravação de dados estruturados em texto, e o módulo *unittest*, para testes automatizados (PYTHON SOFTWARE FOUNDATION, 2026). O uso exclusivo da biblioteca padrão no programa principal dispensa a instalação de pacotes adicionais no computador do hospital."));

add(sec(1, "5 Programa e metodologia"));
add(sec(2, "5.1 Descrição do programa"));
add(p("O sistema foi organizado em duas camadas. O módulo *estoque.py* concentra as regras de negócio, as estruturas de dados e a gravação dos dados, sem nenhuma dependência da interface. O módulo *app.py* implementa a interface gráfica em Tkinter e apenas exibe informações e repassa as ações do usuário ao núcleo. Essa separação permitiu testar e medir as regras de negócio de forma automatizada, sem a necessidade de operar a janela manualmente."));
add(p("A tela principal, apresentada na Figura 1, exibe os itens em uma tabela com código, nome, categoria, saldo, estoque mínimo, local e situação. Itens abaixo do mínimo são destacados em vermelho claro e itens zerados em vermelho mais intenso. A busca filtra a tabela a cada tecla digitada, ignorando acentos e diferenças entre maiúsculas e minúsculas, e qualquer coluna pode ser ordenada com um clique no cabeçalho."));
add(figura("Tela principal do sistema", `${PROJ}/docs/tela_principal.png`, 560, "Autor, 2026."));
add(p("As entradas e saídas são registradas em formulários que informam o item, a quantidade, o setor e o responsável. As regras de negócio recusam quantidades nulas ou negativas, nomes duplicados e saídas maiores do que o saldo; nesse caso, a mensagem informa o saldo disponível e o formulário permanece aberto para correção, como mostra a Figura 2. Cada alteração é gravada imediatamente em um arquivo JSON por meio de escrita atômica: os dados são gravados primeiro em um arquivo temporário, que só então substitui o arquivo definitivo, de modo que uma interrupção durante a gravação não corrompe o estoque."));
add(figura("Formulário de saída recusando quantidade maior que o saldo", `${PROJ}/docs/tela_erro_saida.png`, 560, "Autor, 2026."));
add(p("O relatório, apresentado na Figura 3, reúne um resumo do estoque, a lista de itens a repor com sugestão de compra, o total de saídas por setor e uma matriz de saídas por item e por dia da semana."));
add(figura("Janela de relatório", `${PROJ}/docs/tela_relatorio.png`, 440, "Autor, 2026."));
add(p("O Quadro 1 relaciona os conteúdos programáticos da disciplina à sua aplicação no programa."));
add(grade("Quadro", "Conteúdos da disciplina aplicados no programa",
  ["Conteúdo", "Aplicação no programa"],
  [["Registros", "Tipos *Item* e *Movimentacao*, declarados como *dataclasses*"],
   ["Vetores e arranjos de registros", "Lista de itens e histórico de movimentações"],
   ["Pesquisa sequencial", "Busca por parte do nome, que exige examinar todos os itens"],
   ["Pesquisa binária", "Busca por código, versões iterativa e recursiva, sobre a lista mantida sempre ordenada por código"],
   ["Ordenação", "Ordenação por inserção implementada manualmente, usada na tabela e no relatório"],
   ["Matrizes", "Matriz de saídas com uma linha por item e uma coluna por dia da semana"],
   ["Cadeias de caracteres", "Remoção de acentos para a busca e geração de códigos como PER-001"],
   ["Funções recursivas", "Pesquisa binária recursiva e soma recursiva por divisão e conquista"],
   ["Acumuladores, contadores e sinalizadores", "Cálculo de totais, itens em alerta, itens zerados, maior e menor saldo"]],
  [5.0, 11.0], "Autor, 2026."));
add(p("Para que a pesquisa binária funcione sem reordenar a lista a cada consulta, o sistema mantém a seguinte invariante: a lista de itens está sempre ordenada por código. Cada novo item é inserido diretamente na posição correta, localizada também por pesquisa binária, e a lista é verificada ao ser carregada do arquivo. Em uma versão preliminar, a busca reordenava a lista a cada chamada, o que anulava o ganho da pesquisa binária; o defeito foi identificado na revisão do código e corrigido com a invariante."));

add(sec(2, "5.2 Metodologia de avaliação de desempenho"));
add(p("O desempenho foi avaliado pela subcaracterística comportamento em relação ao tempo, com a meta de que cada operação responda em até 100 ms (NIELSEN, 1993). Foram realizados dois experimentos automatizados, com os scripts *benchmark.py* e *teste_carga.py*, disponíveis no repositório."));
add(p("No primeiro experimento, foram gerados estoques com 100, 500, 1.000, 5.000, 10.000 e 20.000 itens e medidos os tempos de pesquisa binária por código, pesquisa sequencial por nome no pior caso (termo inexistente), ordenação por nome com a ordenação por inserção e com a função *sorted* da linguagem, e gravação e leitura do arquivo. Cada medição foi repetida de três a sete vezes e registrou-se a mediana, menos sensível a interferências pontuais do sistema operacional do que a média. Os dados foram gerados com semente aleatória fixa, para que o experimento seja reprodutível. A ordenação por inserção foi medida apenas até 5.000 itens, pois acima disso o tempo de execução tornou-se impraticável."));
add(p(`No segundo experimento, um teste de carga, 50 usuários simulados executaram 200 operações cada, em ordem intercalada e aleatória, totalizando 10.000 operações sobre um estoque inicial de 300 itens. As operações seguiram proporções que imitam o uso real: busca por nome (30%), saída (25%), entrada (15%), busca por código (10%), relatório (10%) e cadastro (10%). Assim como na interface, cada operação que altera dados gravou o arquivo. Parte das saídas solicitava quantidades maiores que o saldo, para verificar se as regras de negócio as recusariam. Foram registrados os percentis 50, 95 e 99 do tempo de resposta e, ao final, verificadas cinco invariantes: ausência de saldo negativo, coerência entre saldo e histórico de movimentações, ordenação da lista por código, unicidade dos códigos e igualdade entre os dados em memória e os gravados em arquivo. Os experimentos foram executados em computador com sistema ${soVer} (arquitetura x86_64) e Python ${pythonVer}.`));

add(sec(2, "5.3 Metodologia de avaliação de usabilidade"));
add(p("Foram definidas cinco tarefas representativas do uso cotidiano: T1, cadastrar um item novo; T2, registrar a saída de dois mouses para a recepção; T3, consultar o saldo de cabos HDMI; T4, registrar a entrada de cinco toners; e T5, identificar no relatório o item de compra mais urgente. Sobre essas tarefas, foram aplicados três procedimentos."));
add(p("O primeiro foi um teste automatizado ponta a ponta, no qual um programa abre a interface real, preenche os mesmos campos e aciona os mesmos comandos que um usuário e verifica se o resultado de cada tarefa está correto, além de testar a recusa de uma saída acima do saldo e a gravação dos dados. Esse teste avalia a adequação funcional e a operabilidade, mas não substitui a percepção de usuários."));
add(p("O segundo foi uma avaliação heurística da interface com base nas dez heurísticas de Nielsen (1994), registrando para cada uma o grau de atendimento e a gravidade dos problemas encontrados, na escala de 0 a 4 (NIELSEN, 1993). O terceiro foi a estimativa do tempo de execução de cada tarefa por um usuário experiente pelo modelo KLM, com os tempos-padrão de Card, Moran e Newell (1980): 0,28 s por tecla, 1,10 s para apontar, 0,10 s para pressionar ou soltar o botão do mouse, 0,40 s para mover a mão entre mouse e teclado e 1,35 s de preparação mental."));
add(p("Por fim, para antecipar como diferentes perfis de funcionários do hospital interagiriam com o sistema, foi aplicado o percurso cognitivo (WHARTON *et al*., 1994) com base em personas, isto é, usuários fictícios construídos a partir dos perfis reais que utilizariam o sistema (COOPER, 1999). Em cada passo das tarefas, avaliou-se se o usuário saberia o que fazer, se encontraria o comando correto e se compreenderia a resposta do sistema. Os relatos resultantes são **simulados**: foram elaborados pelo autor a partir do funcionamento do sistema e não foram coletados com participantes reais."));
add(p("Complementarmente, a interface registra em arquivo o tempo gasto e os erros de validação de cada formulário, e foi preparado um roteiro de teste com usuários acompanhado do questionário SUS (BROOKE, 1996), para aplicação com a equipe do hospital."));
add(sec(2, "5.4 Testes automatizados"));
add(p("As regras de negócio foram cobertas por 25 testes unitários escritos com o módulo *unittest*. Cada teste monta um cenário, executa uma única ação e verifica o resultado, incluindo tanto os casos de sucesso quanto os casos que devem ser recusados, como saídas acima do saldo, quantidades negativas e nomes duplicados. Os testes foram executados após cada alteração no código, o que permitiu realizar as otimizações descritas na seção de resultados sem introduzir novos defeitos."));

add(sec(1, "6 Resultados"));
add(sec(2, "6.1 Testes funcionais"));
add(p("Os 25 testes unitários foram executados com sucesso. No teste automatizado ponta a ponta, as sete verificações foram aprovadas: as cinco tarefas produziram o resultado esperado, a saída acima do saldo foi recusada com a mensagem correta e os dados gravados em arquivo coincidiram com os exibidos na tela."));
add(sec(2, "6.2 Desempenho por tamanho de estoque"));
add(p("A Tabela 1 apresenta os tempos medianos obtidos no primeiro experimento."));
add(grade("Tabela", "Tempo mediano das operações por tamanho do estoque (ms)",
  ["Itens", "Pesquisa binária", "Pesquisa sequencial", "Inserção v1", "Inserção v2", "sorted()", "Gravar", "Ler"],
  desemp.map(r => [Number(r.n_itens).toLocaleString("pt-BR"), fmt(num(r.busca_binaria_ms), 4),
    fmt(num(r.busca_sequencial_ms), 2), fmt(num(r.ordenacao_insercao_v1_ms), 1), fmt(num(r.ordenacao_insercao_ms), 1),
    fmt(num(r.ordenacao_sorted_ms), 2), fmt(num(r.salvar_ms), 1), fmt(num(r.carregar_ms), 1)]),
  [1.6, 2.0, 2.2, 2.0, 2.0, 1.8, 1.7, 1.7], "Autor, 2026.", 18));
add(p(`A pesquisa binária manteve-se praticamente constante, abaixo de 0,01 ms mesmo com 20.000 itens, enquanto a pesquisa sequencial cresceu de forma linear até ${fmt(num(d20000.busca_sequencial_ms), 1)} ms, comportamento coerente com as complexidades O(log n) e O(n), como mostra a Figura 4. Ambas permaneceram dentro da meta de 100 ms em todos os tamanhos testados.`));
add(figura("Tempo por busca: pesquisa sequencial e pesquisa binária", `${RES}/grafico_buscas.png`, 540, "Autor, 2026."));
add(p(`O resultado mais relevante foi obtido na ordenação. Na primeira versão do programa (v1), a ordenação por nome com 1.000 itens levou ${fmt(num(d1000.ordenacao_insercao_v1_ms), 0)} ms, acima da meta. Como a tabela da interface é reordenada a cada tecla digitada na busca, esse tempo tornaria a tela lenta. A análise do código mostrou que a função que remove acentos dos nomes era executada dentro do laço interno, uma vez a cada comparação. Na segunda versão (v2), a chave de ordenação de cada item passou a ser calculada uma única vez, antes do laço, sem alterar o algoritmo. O tempo com 1.000 itens caiu para ${fmt(num(d1000.ordenacao_insercao_ms), 1)} ms, uma redução de aproximadamente ${Math.round(ganho1000)} vezes, como mostra a Figura 5.`));
add(figura("Ordenação por inserção antes (v1) e depois (v2) da otimização", `${RES}/grafico_otimizacao.png`, 540, "Autor, 2026."));
add(p(`A otimização reduziu o custo por comparação, mas não alterou a complexidade O(n²): com 5.000 itens, a ordenação por inserção ainda levou ${fmt(num(d5000.ordenacao_insercao_ms), 0)} ms, contra ${fmt(num(d5000.ordenacao_sorted_ms), 1)} ms da função *sorted*, que utiliza um algoritmo O(n log n). Pela tendência quadrática observada, a ordenação por inserção atende à meta até aproximadamente 1.500 itens, quantidade superior ao porte de um estoque de TI de hospital-dia. A gravação e a leitura do arquivo permaneceram abaixo de 100 ms até 10.000 itens e chegaram a ${fmt(num(d20000.salvar_ms), 0)} ms e ${fmt(num(d20000.carregar_ms), 0)} ms, respectivamente, com 20.000 itens.`));

add(sec(2, "6.3 Teste de carga com usuários simulados"));
add(p("Na primeira execução do teste de carga, 484 das 10.000 operações terminaram com erro inesperado. A investigação mostrou que a função de soma recursiva, usada no relatório para totalizar as saídas, fazia uma chamada recursiva por elemento; quando o histórico ultrapassou cerca de mil saídas, o limite de profundidade de recursão da linguagem foi excedido e o relatório deixou de funcionar. Esse defeito não se manifestaria nos testes com poucos dados e só seria percebido após meses de uso. A função foi reescrita com a estratégia de divisão e conquista, somando recursivamente as duas metades da lista, o que reduz a profundidade de recursão de n para log₂ n, e foi criado um teste unitário com 100.000 elementos para impedir que o defeito retorne."));
add(p(`Após a correção, o teste foi executado novamente. A Tabela 2 apresenta os resultados por tipo de operação.`));
const nomesOp = { buscar_nome: "Busca por nome", buscar_codigo: "Busca por código", saida: "Saída", entrada: "Entrada",
  relatorio: "Relatório", cadastrar: "Cadastro", TODAS: "Todas" };
add(grade("Tabela", "Tempo de resposta no teste de carga com 50 usuários simulados (ms)",
  ["Operação", "Qtd.", "Recusadas", "P50", "P95", "P99", "Máximo", "Até 100 ms"],
  carga.map(r => [nomesOp[r.operacao], Number(r.quantidade).toLocaleString("pt-BR"), r.recusadas_pela_regra,
    fmt(num(r.p50_ms), 2), fmt(num(r.p95_ms), 2), fmt(num(r.p99_ms), 2), fmt(num(r.max_ms), 2),
    `${fmt(num(r["dentro_meta_%"]), 0)}%`]),
  [2.8, 1.5, 1.8, 1.6, 1.6, 1.6, 1.8, 2.0], "Autor, 2026.", 18));
add(p(`Todas as 10.000 operações responderam em até 100 ms; 95% delas foram concluídas em até ${fmt(num(cTodas.p95_ms), 1)} ms e o maior tempo registrado foi de ${fmt(num(cTodas.max_ms), 1)} ms. Não houve erros inesperados e as cinco invariantes foram confirmadas ao final. As ${cOp("saida").recusadas_pela_regra} saídas recusadas correspondem às solicitações acima do saldo, que foram corretamente bloqueadas pelas regras de negócio. A Figura 6 mostra a distribuição dos tempos de resposta.`));
add(figura("Distribuição dos tempos de resposta no teste de carga", `${RES}/grafico_carga_latencia.png`, 520, "Autor, 2026."));
add(p("A Figura 7 revela uma limitação da forma de armazenamento. Como o arquivo JSON é regravado por inteiro a cada alteração e o histórico de movimentações cresce continuamente, o tempo mediano de uma saída aumentou de cerca de 3 ms no início para cerca de 24 ms ao final do teste, enquanto a busca, que não grava o arquivo, permaneceu praticamente estável. Os tempos continuam dentro da meta, mas a tendência indica que, em um horizonte de anos de uso, o histórico precisará ser arquivado ou o armazenamento substituído por um banco de dados."));
add(figura("Tempo mediano das operações ao longo do teste de carga", `${RES}/grafico_carga_tempo.png`, 520, "Autor, 2026."));

add(sec(2, "6.4 Usabilidade"));
add(p("O Quadro 2 apresenta o resultado da avaliação heurística."));
add(grade("Quadro", "Avaliação heurística da interface",
  ["Heurística (NIELSEN, 1994)", "Avaliação", "Gravidade"],
  [["Visibilidade do status do sistema", "Atende: mensagem de confirmação após cada ação, cores de situação e contadores no rodapé", "0"],
   ["Correspondência com o mundo real", "Atende: termos do almoxarifado (entrada, saída, setor, repor)", "0"],
   ["Controle e liberdade do usuário", "Parcial: há cancelamento e confirmação de exclusão, mas não é possível estornar uma movimentação registrada por engano nem editar os dados de um item", "3"],
   ["Consistência e padrões", "Parcial: o atalho Ctrl+S registra saída, embora seja associado a salvar na maioria dos programas", "2"],
   ["Prevenção de erros", "Atende: bloqueia saída acima do saldo, nomes duplicados e valores negativos; categorias e setores em listas", "0"],
   ["Reconhecimento em vez de memorização", "Atende: formulário lista os itens com o saldo; atalhos indicados nos próprios botões", "0"],
   ["Flexibilidade e eficiência de uso", "Atende: atalhos de teclado, duplo clique para saída, busca em tempo real e ordenação por coluna", "0"],
   ["Estética e design minimalista", "Atende: tela única com poucas ações visíveis", "0"],
   ["Reconhecer, diagnosticar e recuperar erros", "Atende: mensagens em linguagem simples informando o saldo disponível", "0"],
   ["Ajuda e documentação", "Não atende: não há ajuda dentro do sistema", "2"]],
  [4.2, 9.4, 2.4], "Autor, 2026. Gravidade: 0 = não é problema; 2 = problema menor; 3 = problema maior; 4 = catástrofe."));
add(p("A avaliação indicou que as heurísticas ligadas à prevenção e à recuperação de erros, ponto central para um estoque, são atendidas. O problema mais grave é a ausência de estorno de movimentações: um lançamento errado só pode ser compensado com um lançamento inverso, o que distorce o histórico por setor. Também foram identificados a ambiguidade do atalho Ctrl+S e a falta de ajuda integrada."));
add(p("A Tabela 3 e a Figura 8 apresentam as estimativas de tempo obtidas pelo modelo KLM."));
add(grade("Tabela", "Estimativa de tempo das tarefas pelo modelo KLM",
  ["Tarefa", "Teclas", "Cliques", "Preparações mentais", "Tempo estimado (s)"],
  klm.map(r => [r.tarefa, r.n_teclas, r.n_cliques, r.n_mentais, fmt(num(r.tempo_estimado_s), 1)]),
  [5.2, 2.0, 2.0, 3.6, 3.2], "Autor, 2026."));
add(figura("Tempo estimado das tarefas para usuário experiente", `${PROJ}/usabilidade/resultados/grafico_klm.png`, 520, "Autor, 2026."));
add(p("Todas as tarefas foram estimadas em menos de 12 segundos. A tarefa mais longa, o cadastro, é dominada pela digitação do nome do item, que é inevitável. A saída, a tarefa mais frequente no dia a dia, beneficia-se do duplo clique na linha da tabela, que abre o formulário com o item já selecionado e com a recepção como setor padrão, eliminando passos de navegação. Consultar um saldo exige apenas digitar parte do nome na busca, sem abrir nenhuma outra janela."));

add(sec(2, "6.5 Percurso cognitivo com personas (relatos simulados)"));
add(p("Foram definidas três personas, apresentadas no Quadro 3, representando os perfis que usariam o sistema no hospital-dia. Os relatos a seguir descrevem, de forma simulada, a execução das tarefas por cada persona, destacando as dificuldades que o percurso cognitivo permitiu antecipar."));
add(grade("Quadro", "Personas utilizadas no percurso cognitivo",
  ["Persona", "Perfil", "Tarefas avaliadas"],
  [["Carla, 34 anos", "Técnica de TI; usa o sistema todos os dias e tem muita familiaridade com computadores e atalhos de teclado", "T1, T2, T4"],
   ["Jorge, 52 anos", "Auxiliar de almoxarifado; pouca familiaridade com computadores, digita devagar e prefere usar o mouse", "T2, T3, T4"],
   ["Fernanda, 27 anos", "Analista administrativa; consulta o estoque para planejar compras, sem registrar movimentações", "T3, T5"]],
  [3.2, 9.8, 3.0], "Autor, 2026. Personas fictícias, elaboradas a partir dos perfis reais de usuários."));
add(p("**Relato simulado de Carla.** Por já conhecer o sistema, Carla cadastraria o headset e registraria a entrada dos toners rapidamente, usando a tecla Tab entre os campos e Enter para confirmar. Para a saída dos mouses, o duplo clique na linha da tabela a levaria direto ao formulário com o item escolhido. O percurso, no entanto, revelou duas situações de dificuldade. Primeiro, ao perceber que registrou uma saída com a quantidade errada, Carla não encontraria uma opção para desfazer ou estornar o lançamento e teria de registrar uma entrada para compensar, deixando duas movimentações no histórico do setor. Segundo, acostumada a pressionar Ctrl+S para salvar em outros programas, ela abriria sem querer o formulário de saída."));
add(p("**Relato simulado de Jorge.** Jorge usaria o mouse e os botões rotulados, sem recorrer a atalhos. Na saída dos mouses, ele clicaria no item e em seguida no botão de saída. No formulário, o campo de quantidade já vinha preenchido com o valor 1; ao digitar 2 sem apagar o valor anterior, Jorge poderia registrar 12 ou 21 unidades sem perceber, porque o número resultante continua válido e, havendo saldo, a saída seria aceita. Esse foi o problema mais grave identificado no percurso, pois produz um erro silencioso no estoque. Ao tentar uma saída maior que o saldo, por outro lado, a mensagem que informa a quantidade disponível seria suficiente para que ele corrigisse o valor sozinho. Os símbolos de seta nos botões de entrada e saída poderiam gerar uma breve hesitação, compensada pelos rótulos escritos."));
add(p("**Relato simulado de Fernanda.** Fernanda usaria apenas a busca e o relatório. Ao digitar cabo hdmi sem acento e em letras minúsculas, a tabela seria filtrada corretamente, pois a busca ignora acentos e diferenças entre maiúsculas e minúsculas. Para planejar a compra, a caixa Só itens para repor e a coluna Comprar do relatório responderiam diretamente à tarefa T5. A dificuldade antecipada foi a ausência de uma opção para exportar ou imprimir o relatório, o que a obrigaria a copiar os dados manualmente para enviar ao setor de compras."));
add(p("O Quadro 4 consolida os problemas identificados no percurso. O preenchimento do campo de quantidade foi corrigido ainda durante o projeto: ao abrir o formulário, o valor inicial passa a vir selecionado, de modo que o valor digitado o substitui. Com isso, as tarefas T2 e T4 passaram a exigir uma tecla a menos, o que já está considerado na Tabela 3."));
add(grade("Quadro", "Problemas identificados no percurso cognitivo",
  ["Problema", "Persona", "Gravidade", "Situação"],
  [["Valor inicial do campo de quantidade não é substituído ao digitar", "Jorge", "3", "Corrigido"],
   ["Não há estorno de movimentação lançada por engano", "Carla", "3", "Trabalho futuro"],
   ["Atalho Ctrl+S registra saída, contrariando a convenção de salvar", "Carla", "2", "Trabalho futuro"],
   ["Relatório não pode ser exportado nem impresso", "Fernanda", "1", "Trabalho futuro"],
   ["Setas nos botões de entrada e saída podem gerar hesitação", "Jorge", "1", "Trabalho futuro"]],
  [7.6, 2.4, 2.2, 3.8], "Autor, 2026. Gravidade conforme Nielsen (1993)."));

add(sec(1, "7 Conclusão"));
add(p("O objetivo deste trabalho foi alcançado: foi desenvolvido um sistema de controle de estoque de TI que impede saídas acima do saldo, sinaliza os itens a repor, registra o destino de cada item e gera relatórios de consumo, aplicando os conteúdos de algoritmos e estruturas de dados da disciplina. A avaliação mostrou que todas as operações respondem dentro da meta de 100 ms para estoques muito maiores do que o de um hospital-dia, inclusive sob uma carga de 10.000 operações, sem nenhuma inconsistência nos dados, e que a interface atende às heurísticas mais importantes para o contexto, em especial a prevenção de erros."));
add(p("O principal aprendizado foi o valor da medição. Os dois defeitos mais sérios encontrados, o gargalo na ordenação e o estouro de recursão no relatório, não apareciam com os poucos itens usados durante o desenvolvimento e só foram revelados pelos experimentos com volumes maiores de dados. Os testes automatizados, por sua vez, permitiram corrigi-los com segurança."));
add(p("O trabalho apresenta limitações. A ordenação por inserção, mantida por ser objeto de estudo da disciplina, tem complexidade quadrática e deixaria de atender à meta acima de aproximadamente 1.500 itens. O armazenamento em arquivo JSON, regravado a cada alteração, torna as operações progressivamente mais lentas à medida que o histórico cresce e não permite o uso simultâneo por mais de um computador. Por fim, a avaliação de usabilidade foi analítica, baseada em heurísticas, no modelo KLM e em relatos simulados com personas, e não mediu a percepção de usuários reais; os problemas antecipados nos relatos precisam ser confirmados com a equipe do hospital."));
add(p("Como continuidade, propõe-se: aplicar o roteiro de teste com usuários e o questionário SUS com a equipe do hospital, interpretando as notas pelas faixas de Bangor, Kortum e Miller (2009), com ao menos cinco participantes, número que segundo Nielsen e Landauer (1993) já revela a maior parte dos problemas de usabilidade; substituir o arquivo JSON por um banco de dados SQLite; implementar o estorno de movimentações, a edição de itens, a exportação do relatório e uma ajuda integrada, corrigindo os problemas da avaliação heurística e do percurso cognitivo; e, futuramente, disponibilizar uma versão web, reaproveitando o núcleo de regras de negócio já separado da interface."));

// ---------- referências ----------
const REFS = [
  "BANGOR, A.; KORTUM, P.; MILLER, J. Determining what individual SUS scores mean: adding an adjective rating scale. **Journal of Usability Studies**, [*s. l.*], v. 4, n. 3, p. 114-123, 2009.",
  "BROOKE, J. SUS: a quick and dirty usability scale. *In*: JORDAN, P. W. *et al*. (ed.). **Usability evaluation in industry**. London: Taylor & Francis, 1996. p. 189-194.",
  "CARD, S. K.; MORAN, T. P.; NEWELL, A. The keystroke-level model for user performance time with interactive systems. **Communications of the ACM**, New York, v. 23, n. 7, p. 396-410, 1980.",
  "COOPER, A. **The inmates are running the asylum**: why high-tech products drive us crazy and how to restore the sanity. Indianapolis: Sams, 1999.",
  "CORMEN, T. H. *et al*. **Algoritmos**: teoria e prática. 3. ed. Rio de Janeiro: Elsevier, 2012.",
  "INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO/IEC 9126-1**: software engineering: product quality: part 1: quality model. Geneva: ISO, 2001.",
  "INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO/IEC 25010**: systems and software engineering: systems and software quality requirements and evaluation (SQuaRE): system and software quality models. Geneva: ISO, 2011.",
  "INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO/IEC 25019**: systems and software engineering: systems and software quality requirements and evaluation (SQuaRE): quality-in-use model. Geneva: ISO, 2023.",
  "MANZANO, J. A. N. G.; OLIVEIRA, J. F. **Algoritmos**: lógica para desenvolvimento de programação de computadores. 28. ed. São Paulo: Érica, 2016.",
  "NIELSEN, J. **Usability engineering**. Boston: Academic Press, 1993.",
  "NIELSEN, J. **10 usability heuristics for user interface design**. Fremont: Nielsen Norman Group, 1994. Disponível em: https://www.nngroup.com/articles/ten-usability-heuristics/. Acesso em: 15 out. 2026.",
  "NIELSEN, J.; LANDAUER, T. K. A mathematical model of the finding of usability problems. *In*: CONFERENCE ON HUMAN FACTORS IN COMPUTING SYSTEMS, 1993, Amsterdam. **Proceedings** [...]. New York: ACM, 1993. p. 206-213.",
  "PERKOVIC, L. **Introdução à computação usando Python**: um foco no desenvolvimento de aplicações. Rio de Janeiro: LTC, 2016.",
  "PYTHON SOFTWARE FOUNDATION. **The Python standard library**. [*S. l.*]: PSF, 2026. Disponível em: https://docs.python.org/3/library/. Acesso em: 15 out. 2026.",
  "WHARTON, C. *et al*. The cognitive walkthrough method: a practitioner's guide. *In*: NIELSEN, J.; MACK, R. L. (ed.). **Usability inspection methods**. New York: John Wiley & Sons, 1994. p. 105-140.",
];
ENTRADAS.push({ nivel: 1, texto: "Referências" });
add(new Paragraph({ pageBreakBefore: true, heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER,
  children: [tc("REFERÊNCIAS", { bold: true })], spacing: { line: 360, after: 360 } }));
REFS.forEach(r => add(new Paragraph({ children: runs(r, { size: T12 }), alignment: AlignmentType.LEFT,
  spacing: { line: 240, after: 240 } })));

// ---------- anexo: código do núcleo ----------
const ANEXO = "Anexo A – Código-fonte do núcleo do sistema (estoque.py)";
ENTRADAS.push({ nivel: 1, texto: ANEXO });
add(new Paragraph({ pageBreakBefore: true, heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER,
  children: [tc("ANEXO A – CÓDIGO-FONTE DO NÚCLEO DO SISTEMA (ESTOQUE.PY)", { bold: true })], spacing: { line: 360, after: 240 } }));
add(new Paragraph({ children: runs(`O código completo, incluindo a interface (*app.py*), os testes e os scripts de medição, está disponível em ${REPO}.`, { size: T10 }),
  spacing: { after: 240 }, alignment: AlignmentType.JUSTIFIED }));
fs.readFileSync(`${PROJ}/estoque.py`, "utf8").replace(/\n$/, "").split("\n").forEach(linha => add(new Paragraph({
  spacing: { line: 220, after: 0 },
  children: [new TextRun({ text: linha.length ? linha : " ", font: "Courier New", size: 15 })] })));

// =====================================================================
// MONTAGEM
// =====================================================================
const pagina = { size: { width: 11906, height: 16838 },
  margin: { top: 1701, left: 1701, bottom: 1134, right: 1134, header: 709 } };   // 3/3/2/2 cm
const cabecalhoNumerado = new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
  children: [new TextRun({ children: [PageNumber.CURRENT], font: FONTE, size: T10 })] })] });
const semCabecalho = new Header({ children: [new Paragraph({ children: [] })] });

const pre = [
  ...resumoBloco("RESUMO", resumoTxt, "Palavras-chave", "Controle de estoque. Python. Qualidade de software. Desempenho. Usabilidade."),
  quebra(),
  ...resumoBloco("ABSTRACT", abstractTxt, "Keywords", "Inventory control. Python. Software quality. Performance. Usability."),
  new Paragraph({ pageBreakBefore: true, alignment: AlignmentType.CENTER, spacing: { line: 360, after: 360 },
    children: [tc("SUMÁRIO", { bold: true })] }),
  ...sumario(),
];

const doc = new Document({
  creator: "Arthur Sparvoli de Araujo", title: TITULO, description: "Projeto Integrador - UNISA 2026/2",
  styles: {
    default: { document: { run: { font: FONTE, size: T12 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONTE, size: T12, bold: true, color: "000000" }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONTE, size: T12, bold: true, color: "000000" }, paragraph: { outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "marcadores", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
    alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 709, hanging: 357 } } } }] }] },
  sections: [
    { properties: { page: pagina }, headers: { default: semCabecalho }, children: capa },
    { properties: { page: pagina }, headers: { default: semCabecalho }, children: pre },
    { properties: { page: pagina }, headers: { default: cabecalhoNumerado }, children: corpo },
  ],
});

const saida = process.env.SAIDA || "/home/claude/relatorio/Relatorio_Projeto_Integrador.docx";
Packer.toBuffer(doc).then(b => { fs.writeFileSync(saida, b);
  fs.writeFileSync("/home/claude/relatorio/titulos.json", JSON.stringify(ENTRADAS.map(e => e.texto)));
  console.log("ok:", saida, `${nFig} figuras, ${nTab} tabelas, ${nQuadro} quadros`); });
