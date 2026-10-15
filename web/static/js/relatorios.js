(function () {
  "use strict";
  const { h, api, avisar } = window.SIGMComum;
  const el = {
    tipo: document.getElementById("tipo"),
    resumo: document.getElementById("resumo"),
    tabela: document.getElementById("tabela"),
  };

  async function carregar() {
    let r;
    try { r = await api("/api/relatorios/" + el.tipo.value); }
    catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar("Não foi possível carregar o relatório.", true); return; }
    const d = r.dados;
    el.resumo.textContent = d.total
      ? (d.cortado ? `Mostrando ${d.linhas.length} de ${d.total} registros. A exportação traz todos.` : `${d.total} ${d.total === 1 ? "registro" : "registros"}`)
      : "";
    el.tabela.replaceChildren();
    if (!d.total) {
      el.tabela.append(h("caption", { class: "lista-vazia" }, "Nenhum registro encontrado."));
      return;
    }
    el.tabela.append(
      h("thead", null, h("tr", null, d.colunas.map((c) => h("th", { scope: "col" }, c)))),
      h("tbody", null, d.linhas.map((l) => h("tr", null, l.map((v) => h("td", null, v === "" || v === null ? "-" : v))))));
  }

  for (const botao of document.querySelectorAll("[data-exportar]")) {
    botao.addEventListener("click", async () => {
      const formato = botao.dataset.exportar;
      botao.disabled = true;
      try {
        const resposta = await fetch(`/api/relatorios/${el.tipo.value}/exportar?formato=${formato}`, { headers: { "X-SIGM": "1" } });
        if (resposta.status === 401) { window.location.href = "/login"; return; }
        if (!resposta.ok) { avisar("Não foi possível exportar o relatório.", true); return; }
        const blob = await resposta.blob();
        const disposicao = resposta.headers.get("Content-Disposition") || "";
        const nome = (/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposicao) || [])[1] || `relatorio.${formato}`;
        const link = h("a", { href: URL.createObjectURL(blob), download: decodeURIComponent(nome) });
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 4000);
        const real = resposta.headers.get("X-SIGM-Formato");
        avisar(real && real !== formato ? "Excel indisponível neste computador; exportado em CSV." : "Relatório exportado.");
      } catch (e) { avisar(e.message, true); }
      finally { botao.disabled = false; }
    });
  }

  el.tipo.addEventListener("change", carregar);
  carregar();
})();
