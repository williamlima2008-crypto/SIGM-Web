(function () {
  "use strict";
  const { h, api, avisar, formulario } = window.SIGMComum;
  const form = document.getElementById("filtros");
  const corpo = document.getElementById("corpo-tabela");
  const resumo = document.getElementById("resumo");

  function parametros() {
    const p = new URLSearchParams();
    for (const [k, v] of new FormData(form)) if (String(v).trim()) p.set(k, String(v).trim());
    return p;
  }

  async function carregar() {
    let r;
    try { r = await api("/api/auditoria?" + parametros()); } catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar(r.dados.erro || "Não foi possível carregar o log.", true); return; }
    const d = r.dados;
    resumo.textContent = d.itens.length + " registro(s)" + (d.truncado ? ` (mostrando os ${d.limite} mais recentes; use os filtros)` : "");
    corpo.replaceChildren();
    if (!d.itens.length) { corpo.append(h("tr", null, h("td", { colspan: "5", class: "lista-vazia" }, "Nenhum registro encontrado."))); return; }
    for (const l of d.itens) {
      corpo.append(h("tr", { class: "linha-clicavel", tabindex: "0", onclick: () => detalhes(l.id),
        onkeydown: (e) => { if (e.key === "Enter") detalhes(l.id); } },
        h("td", null, l.data), h("td", null, l.usuario), h("td", null, l.acao), h("td", null, l.modulo), h("td", null, l.descricao)));
    }
  }

  async function detalhes(id) {
    let r;
    try { r = await api("/api/auditoria/" + id); } catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar("Registro não encontrado.", true); return; }
    const l = r.dados;
    const dialogo = h("dialog", { class: "dialogo-dinamico dialogo-largo" },
      h("div", { class: "dialogo-form" },
        h("h2", null, "Detalhes do registro"),
        h("dl", { class: "dados" }, [
          ["ID", l.id], ["Data e hora", l.data], ["Usuário", l.usuario], ["Login", l.login || "-"],
          ["Ação", l.acao], ["Módulo", l.modulo || "-"], ["Descrição", l.descricao],
          ["Registro relacionado", l.registro_id || "-"], ["Detalhes técnicos", l.detalhes || "-"],
        ].map(([k, v]) => h("div", { class: "dado largo" }, h("dt", null, k), h("dd", null, String(v))))),
        h("div", { class: "dialogo-botoes" }, h("button", { type: "button", class: "btn btn-secundario", onclick: () => dialogo.close() }, "Fechar"))));
    dialogo.addEventListener("close", () => dialogo.remove());
    document.body.append(dialogo);
    dialogo.showModal();
  }

  let t;
  form.addEventListener("input", () => { clearTimeout(t); t = setTimeout(carregar, 300); });
  form.addEventListener("submit", (e) => e.preventDefault());
  document.getElementById("btn-limpar").addEventListener("click", () => { form.reset(); carregar(); });
  document.getElementById("btn-pdf").addEventListener("click", async () => {
    const url = "/api/auditoria/exportar?" + parametros();
    const resposta = await fetch(url, { headers: { "X-SIGM": "1" } });
    if (!resposta.ok) {
      const e = await resposta.json().catch(() => ({}));
      avisar(e.mensagem || "Não foi possível exportar.", true); return;
    }
    const blob = await resposta.blob();
    const a = h("a", { href: URL.createObjectURL(blob), download: "log_auditoria.pdf" });
    document.body.append(a); a.click(); a.remove();
    avisar("PDF exportado.");
  });
  document.getElementById("btn-limpeza").addEventListener("click", async () => {
    const v = await formulario({
      titulo: "Limpar registros antigos", botao: "Apagar registros",
      texto: "Apaga do log os registros mais antigos que o período escolhido. Recomendado: exporte o PDF antes. Esta ação não pode ser desfeita e fica registrada.",
      campos: [{ nome: "dias", rotulo: "Manter os últimos", valor: "365",
        opcoes: [["90", "90 dias"], ["180", "6 meses"], ["365", "1 ano"], ["730", "2 anos"]] }],
    });
    if (!v) return;
    let r;
    try { r = await api("/api/auditoria/limpar", { method: "POST", json: { dias: Number(v.dias) } }); }
    catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível limpar.", true); return; }
    avisar(`${r.dados.removidos} registro(s) removido(s).`);
    carregar();
  });
  carregar();
})();
