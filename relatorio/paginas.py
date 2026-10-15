"""Descobre em que página cada título caiu no PDF renderizado (para o sumário)."""
import json, subprocess, sys, unicodedata

pdf, titulos_json, saida = sys.argv[1:4]
titulos = json.load(open(titulos_json, encoding="utf-8"))
n = int([l for l in subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout.splitlines()
         if l.startswith("Pages")][0].split()[-1])

def norm(s):
    s = unicodedata.normalize("NFKD", s)
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).upper().split())

paginas_txt = []
for i in range(1, n + 1):
    txt = subprocess.run(["pdftotext", "-layout", "-f", str(i), "-l", str(i), pdf, "-"],
                         capture_output=True, text=True).stdout
    paginas_txt.append([norm(l) for l in txt.splitlines()])

inicio = next(i for i, linhas in enumerate(paginas_txt) if any(l == "SUMARIO" for l in linhas)) + 1
resultado, faltando = {}, []
for t in titulos:
    alvo = norm(t)[:40]
    achou = next((i + 1 for i in range(inicio, n) if any(l.startswith(alvo) for l in paginas_txt[i])), None)
    if achou is None:
        faltando.append(t)
    else:
        resultado[t] = achou
        inicio = achou - 1
json.dump(resultado, open(saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(resultado)
print("NÃO ENCONTRADOS:", faltando)
